"""Install a trusted exported kit offline in a fresh test profile and exercise it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import venv
from kit_inputs import extract

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify(archive_path, output, expected_sha256):
    if digest(archive_path) != expected_sha256:
        raise ValueError("Archive hash differs from the expected release hash")
    output = output.resolve()
    output.mkdir()
    unpacked = output / "unpacked"
    extract(archive_path, unpacked)
    manifests = list(unpacked.glob("*/SHA256SUMS.json"))
    if len(manifests) != 1:
        raise ValueError("Expected one kit manifest")
    kit = manifests[0].parent
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    paths = {
        p.relative_to(kit).as_posix(): p
        for p in kit.rglob("*")
        if p.is_file() and p != manifests[0]
    }
    if set(paths) != set(manifest["files"]):
        raise ValueError("Kit inventory differs from its manifest")
    for name, path in paths.items():
        if {"sha256": digest(path), "size_bytes": path.stat().st_size} != manifest[
            "files"
        ][name]:
            raise ValueError(f"Kit file failed integrity verification: {name}")
    environment = output / "environment"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "Scripts/python.exe"
    profile = output / "profile"
    profile.mkdir()
    env = dict(
        ((k, v) for k, v in os.environ.items() if not k.upper().startswith("PIP_")),
        PYTHONUTF8="1",
        PYTHONNOUSERSITE="1",
        PIP_CONFIG_FILE=os.devnull,
        USERPROFILE=str(profile),
        APPDATA=str(profile / "Roaming"),
        LOCALAPPDATA=str(profile / "Local"),
    )
    for key in ("PYTHONPATH", "PYTHONHOME", "PYTEST_ADDOPTS"):
        env.pop(key, None)

    def run(name, args, cwd):
        process = subprocess.Popen(
            list(map(str, args)),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        try:
            stdout, stderr = process.communicate(timeout=180)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
            process.communicate(timeout=15)
            raise
        (output / f"{name}.log").write_text(stdout + stderr, encoding="utf-8")
        if process.returncode != 0:
            raise RuntimeError(f"{name} failed; inspect its log in {output}")
        return stdout

    run(
        "install",
        [
            python,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--only-binary=:all:",
            "--require-hashes",
            "--find-links",
            kit,
            "--find-links",
            kit / "wheels",
            "-r",
            kit / "mcp-requirements.lock",
        ],
        kit,
    )
    run("pip-check", [python, "-m", "pip", "check"], kit)
    working = output / "working"
    working.mkdir()
    client = working / "client.py"
    shutil.copyfile(Path(__file__).with_name("core_kit_client.py"), client)
    wheel = next(kit.glob("*.whl"))
    body = run(
        "workflow",
        [
            python,
            "-I",
            client,
            environment / "Scripts/rentgen.exe",
            environment / "Scripts/rentgen-mcp.exe",
            kit / "bsl-scan.exe",
            environment,
            ROOT,
            digest(wheel),
            manifest["version"],
        ],
        working,
    )
    evidence = {
        "archive_sha256": digest(archive_path),
        "verified_files": len(paths),
        "offline_require_hashes": True,
        "workflow": json.loads(body),
    }
    (output / "acceptance.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "accepted": True,
        "evidence": str(output / "acceptance.json"),
        "archive_sha256": evidence["archive_sha256"],
        "tools": len(evidence["workflow"]["tools"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.kit.resolve(strict=True), args.output, args.expected_sha256),
            ensure_ascii=False,
        )
    )
