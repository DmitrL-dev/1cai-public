"""Build a committed core twice, compare bytes, package and verify offline."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/verification"))
from kit_inputs import extract  # noqa: E402 -- sibling standalone verification tools
from export_core_kit import digest, export, metadata  # noqa: E402
from verify_core_kit import verify  # noqa: E402


def build(output, wheelhouse, go, build_wheelhouse=None):
    if (
        sys.platform != "win32"
        or sys.version_info[:2] != (3, 11)
        or sys.maxsize <= 2**32
    ):
        raise ValueError("Use Windows x64 and CPython 3.11")
    if subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT):
        raise ValueError("Commit the source inputs before building the kit")
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    go = Path(go).resolve(strict=True)
    wheelhouse = wheelhouse.resolve(strict=True)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.upper().startswith(("PYTHON", "PIP_", "HATCH_"))
    }
    env.update(
        PYTHONUTF8="1",
        PYTHONNOUSERSITE="1",
        PIP_CONFIG_FILE=os.devnull,
        SOURCE_DATE_EPOCH="315532800",
        GOENV="off",
        GOWORK="off",
        GOFLAGS="",
        GOTOOLCHAIN="local",
        GOPROXY="off",
        GOSUMDB="off",
        CGO_ENABLED="0",
    )

    def run(name, args, cwd=ROOT, extra=None):
        process = subprocess.Popen(
            list(map(str, args)),
            cwd=cwd,
            env={**env, **(extra or {})},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
            process.communicate(timeout=15)
            raise
        (output / (name + ".log")).write_bytes(stdout + stderr)
        if process.returncode:
            raise RuntimeError(f"{name} failed; inspect its log")
        return stdout.decode("utf-8").strip()

    go_version = run("go-version", [go, "version"])
    if go_version != "go version go1.25.5 windows/amd64":
        raise ValueError("The kit build requires Go 1.25.5 windows/amd64")
    goroot = Path(run("go-root", [go, "env", "GOROOT"]))
    source_archive = output / "committed-source.zip"
    run(
        "source-export",
        ["git", "archive", "--format=zip", "--output", source_archive, commit],
    )
    first = output / "first"
    first.mkdir()
    checkout = first / "checkout"
    extract(source_archive, checkout)
    environment = output / "build-environment"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "Scripts/python.exe"
    install = [
        python,
        "-m",
        "pip",
        "install",
        "--require-hashes",
        "--only-binary=:all:",
        "-r",
        checkout / "requirements/locks/product-build-py311-windows.txt",
    ]
    if build_wheelhouse:
        install += ["--no-index", "--find-links", build_wheelhouse.resolve(strict=True)]
    run("build-tools", install)
    run(
        "first-build",
        [python, "-I", "-m", "build", "--no-isolation", "--outdir", first / "dist"],
        checkout,
    )
    second = output / "second"
    second.mkdir()
    extract(next((first / "dist").glob("*.tar.gz")), second / "extracted")
    extracted = list((second / "extracted").iterdir())
    if len(extracted) != 1 or not extracted[0].is_dir():
        raise ValueError("Expected one sdist root")
    # Keep the source layout expected by the exporter; copy only our own extracted tree.
    shutil.copytree(extracted[0], second / "checkout")
    run(
        "second-build",
        [python, "-I", "-m", "build", "--no-isolation", "--outdir", second / "dist"],
        second / "checkout",
    )
    for name, folder in (("first", first), ("second", second)):
        run(
            name + "-scanner",
            [
                go,
                "build",
                "-buildvcs=false",
                "-trimpath",
                "-ldflags=-buildid=",
                "-o",
                folder / "bsl-scan.exe",
                "./cmd/bsl-scan",
            ],
            folder / "checkout/go",
            {"GOCACHE": str(output / (name + "-go-cache"))},
        )
    inputs = {
        "source_commit": commit,
        "source_archive_sha256": digest(source_archive),
        "python": sys.version.split()[0],
        "go": go_version,
        "go_executable_sha256": digest(go),
        "build_lock_sha256": digest(
            checkout / "requirements/locks/product-build-py311-windows.txt"
        ),
        "runtime_lock_sha256": digest(
            checkout / "requirements/locks/product-py311-windows.txt"
        ),
        "mcp_lock_sha256": digest(
            checkout / "requirements/locks/mcp-py311-windows.txt"
        ),
    }
    (second / "build-input-hashes.json").write_text(
        json.dumps(inputs, indent=2) + "\n", "utf-8"
    )
    version = metadata(next((first / "dist").glob("*.whl")))["Version"]
    kit_name = f"rentgen-core-{version}-windows-py311"
    packaged = export(first, second, wheelhouse, goroot / "LICENSE", output / kit_name)
    (output / "repeat").mkdir()
    repeated = export(
        first, second, wheelhouse, goroot / "LICENSE", output / "repeat" / kit_name
    )
    if repeated["archive_sha256"] != packaged["archive_sha256"]:
        raise ValueError("Kit archive is not reproducible")
    accepted = verify(
        Path(packaged["archive"]),
        output / "offline-install",
        packaged["archive_sha256"],
    )
    result = {
        "source_commit": commit,
        "builds_identical": True,
        "kit": packaged,
        "offline_install": accepted,
    }
    (output / "acceptance.json").write_text(
        json.dumps(result, indent=2) + "\n", "utf-8"
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime-wheelhouse", type=Path, required=True)
    parser.add_argument("--build-wheelhouse", type=Path)
    parser.add_argument("--go", default=shutil.which("go"))
    args = parser.parse_args()
    if not args.go:
        parser.error("Specify --go pointing to Go 1.25.5")
    print(
        json.dumps(
            build(args.output, args.runtime_wheelhouse, args.go, args.build_wheelhouse)
        )
    )
