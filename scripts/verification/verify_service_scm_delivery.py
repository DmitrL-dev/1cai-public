"""Prepare a new owned Windows runtime; optionally run its native SCM acceptance."""
if not __debug__:
    raise RuntimeError("Acceptance requires assertions; do not use Python -O")

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")


def regular_tree(root):
    items = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for path in [Path(directory), *(Path(directory) / n for n in dirs + files)]:
            value = path.lstat()
            require(not getattr(value, "st_file_attributes", 0) & 0x400
                    and not path.is_symlink(), "Reparse point in input tree")
            require(path.is_dir() or value.st_nlink == 1, "Hardlink in input tree")
            require(path.resolve().is_relative_to(root), "Path escapes input tree")
        items.extend(Path(directory) / n for n in files)
        require(len(items) <= 20000, "Input tree exceeds file bound")
    return items


def validate_output(output, parent):
    output, parent = Path(output).absolute(), Path(parent).resolve(strict=True)
    require(output.parent == parent and output.resolve() == output,
            "Workspace must be a direct child of the temporary parent")
    require(re.fullmatch(r"rg-scm-[a-f0-9]{12}", output.name), "Invalid workspace name")
    require(not output.exists(), "Workspace must be new")
    return output


def validate_provenance(kit, receipt, commit):
    require(re.fullmatch(r"[a-f0-9]{40}", commit)
            and receipt.get("source_commit") == commit, "Kit source commit differs")
    require(receipt.get("builds_identical") is True, "Reproducible build not accepted")
    require(receipt.get("offline_install", {}).get("accepted") is True,
            "Kit offline installation not accepted")
    digest = sha(kit)
    require(digest == receipt["kit"]["archive_sha256"]
            == receipt["offline_install"]["archive_sha256"], "Kit archive hash differs")
    return digest


def unpack(kit, destination, expected_commit, receipt):
    spec = importlib.util.spec_from_file_location(
        "scm_kit_inputs", Path(__file__).with_name("kit_inputs.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.extract(kit, destination)
    manifests = list(destination.glob("*/SHA256SUMS.json"))
    require(len(manifests) == 1, "Expected one kit manifest")
    root = manifests[0].parent
    manifest = json.loads(manifests[0].read_text("utf-8"))
    files = {p.relative_to(root).as_posix(): p for p in regular_tree(root)
             if p != manifests[0]}
    require(set(files) == set(manifest["files"]), "Kit inventory differs")
    for name, path in files.items():
        require({"sha256": sha(path), "size_bytes": path.stat().st_size}
                == manifest["files"][name], "Kit file hash differs: " + name)
    provenance = json.loads((root / "build-input-hashes.json").read_text("utf-8"))
    require(provenance["source_commit"] == expected_commit, "Manifest source commit differs")
    wheels = list(root.glob("rentgen_core-*-py3-none-any.whl"))
    require(len(wheels) == 1 and sha(wheels[0]) == receipt["kit"]["wheel_sha256"],
            "Expected the accepted Core wheel")
    require((root / "bsl-scan.exe").is_file(), "Scanner missing")
    return root, wheels[0], manifest


def copy_interpreter(target):
    source = Path(sys.base_prefix).resolve(strict=True)
    require(sys.platform == "win32" and sys.version_info[:2] == (3, 11), "Windows CPython 3.11 required")
    target.mkdir()
    copied = {}

    def copy(path):
        value = path.lstat()
        require(not value.st_file_attributes & 0x400 and value.st_nlink == 1,
                "Alias in CPython input")
        name = path.relative_to(source).as_posix()
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        require(sha(path) == sha(destination), "CPython copy changed")
        copied[name] = sha(destination)
        require(len(copied) <= 20000, "CPython inventory exceeds bound")

    for name in ("python.exe", "pythonw.exe", "python3.dll", "python311.dll",
                 "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        copy(source / name)
    for folder in ("DLLs", "Lib", "tcl"):
        for directory, dirs, files in os.walk(source / folder, followlinks=False):
            dirs[:] = [n for n in dirs if n not in {"site-packages", "__pycache__"}]
            require(not Path(directory).lstat().st_file_attributes & 0x400,
                    "Reparse directory in CPython input")
            for name in files:
                copy(Path(directory) / name)
    return copied


def run(python, args, output, label, timeout=180):
    log = output / (label + ".log")
    env = {k: v for k, v in os.environ.items()
           if k.upper() not in {"PYTHONHOME", "PYTHONPATH", "PYTEST_ADDOPTS"}
           and not k.upper().startswith("PIP_")}
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONUTF8="1")
    with log.open("xb") as stream:
        result = subprocess.run([str(python), "-I", "-B", "-X", "utf8", *map(str, args)],
                                cwd=output, env=env, stdin=subprocess.DEVNULL,
                                stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, label + " failed; inspect " + str(log))


def direct_probe(python):
    code = ('import os,sys,json,rentgen_core,importlib.metadata;print(json.dumps(dict('
            'pid=os.getpid(),prefix=sys.prefix,base_prefix=sys.base_prefix,path=sys.path,'
            'core_file=rentgen_core.__file__,version=importlib.metadata.version("rentgen-core"))))')
    process = subprocess.Popen([str(python), "-I", "-B", "-c", code],
                               stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(timeout=30)
    require(process.returncode == 0 and not err and len(out) < 32768, "Direct runtime probe failed")
    data = json.loads(out)
    require(data["pid"] == process.pid, "Runtime is a child launcher")
    root = python.parent
    require(Path(data["prefix"]) == Path(data["base_prefix"]) == root,
            "Runtime prefix escaped owned copy")
    require(all(Path(p).is_relative_to(root) for p in data["path"]), "Foreign runtime import path")
    require(Path(data["core_file"]).is_relative_to(root / "Lib/site-packages"), "Foreign Core import")
    return data


def prepare(kit, build_receipt, commit, output):
    receipt = json.loads(build_receipt.read_text("utf-8"))
    digest = validate_provenance(kit, receipt, commit)
    require(shutil.disk_usage(output.parent).free >= 3 * 1024**3, "At least 3 GiB free required")
    output.mkdir()
    evidence = output / "evidence"
    evidence.mkdir()
    root, wheel, manifest = unpack(kit, output / "unpacked", commit, receipt)
    runtime = output / "runtime"
    copied = copy_interpreter(runtime)
    python = runtime / "python.exe"
    run(python, ["-m", "ensurepip", "--default-pip"], evidence, "ensurepip")
    run(python, ["-m", "pip", "install", "--no-index", "--no-deps", "--only-binary=:all:", wheel], evidence, "install")
    run(python, ["-m", "pip", "check"], evidence, "pip-check")
    probe = direct_probe(python)
    require(probe["version"] == manifest["version"], "Installed version differs")
    with ZipFile(wheel) as archive:
        members = [n for n in archive.namelist() if n.startswith(
            ("rentgen_core/", "rentgen_graph/", "rentgen_diagnostics/")) and not n.endswith("/")]
        require(members and all((runtime / "Lib/site-packages" / n).read_bytes() == archive.read(n)
                                for n in members), "Installed Core bytes differ")
    require(all(sha(runtime / n) == h for n, h in copied.items()), "Copied CPython files changed")
    fixture = output / "fixture"
    fixture.mkdir()
    shutil.copyfile(root / "bsl-scan.exe", fixture / "bsl-scan.exe")
    scripts = {n: sha(Path(__file__).with_name(n)) for n in
               ("verify_service_scm_delivery.py", "scm_acceptance_worker.py", "scm_native_evidence.py")}
    document = {"schema": 1, "workdir": str(output), "service_name": "Rentgen.CI." + output.name[7:],
                "source_commit": commit, "kit_sha256": digest, "wheel": str(wheel),
                "wheel_sha256": sha(wheel), "scanner_sha256": sha(fixture / "bsl-scan.exe"),
                "runtime_files": copied, "installed_core_files": len(members),
                "direct_process": probe, "scripts": scripts, "scm_exercised": False,
                "recorded_utc": datetime.now(timezone.utc).isoformat()}
    save(evidence / "preparation.json", document)
    worker = Path(__file__).with_name("scm_acceptance_worker.py")
    run(python, [worker, "--workdir", output, "prepare"], evidence, "prepare-fixture")
    run(python, [worker, "--workdir", output, "inspect"], evidence, "inspect")
    return python, worker


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Run the privileged disposable-fixture lifecycle")
    args = parser.parse_args()
    parent = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    output = validate_output(args.output, parent)
    python, worker = prepare(args.kit.resolve(strict=True), args.build_receipt.resolve(strict=True),
                             args.expected_commit, output)
    if args.run:
        run(python, [worker, "--workdir", output, "run"], output / "evidence", "lifecycle", timeout=1260)
    print(json.dumps({"output": str(output), "prepared": True, "scm_requested": args.run}))


if __name__ == "__main__":
    main()
