"""Create only owned synthetic inputs using the actual installed Core CLI."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys

MODULE = "CommonModules/WorkbenchProbe/Ext/Module.bsl"
ORIGINAL = 'Procedure Probe() Export\r\n    Value = 1;\r\nEndProcedure\r\n'
EDITED = 'Procedure Probe() Export\r\n    Message("saved revision");\r\nEndProcedure\r\n'
LATER = 'Procedure Probe() Export\r\n    Value = 2;\r\nEndProcedure\r\n'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return path


def cli(registry, project, command, *extra):
    args = [sys.executable, "-I", "-m", "rentgen_core", command, "--registry", str(registry)]
    if project:
        args += ["--project", project]
    result = subprocess.run(args + list(map(str, extra)), stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=90, check=False)
    if len(result.stdout) > 2 * 1024**2 + 1 or len(result.stderr) > 64 * 1024:
        raise RuntimeError("Installed fixture CLI output bound")
    value = json.loads(result.stdout)
    if result.returncode or "error" in value:
        raise RuntimeError("Installed fixture CLI refused: " + value.get("error", {}).get("code", "CLI_FAILED"))
    return value["result"]


def install_bsl(java_home, jar, local_app_data):
    from rentgen_diagnostics._runtime_pins import RuntimePins
    from rentgen_diagnostics.bsl_language_server import _runtime_descriptor

    descriptor, expected = _runtime_descriptor()
    runtime = local_app_data / "Rentgen" / "runtimes" / descriptor["profile_id"]
    runtime.mkdir(parents=True, exist_ok=False)
    (runtime / "jdk").mkdir()
    pins = RuntimePins()
    try:
        pins.tree(java_home, expected)
        pins.file(jar, expected_size=descriptor["bsl"]["jar_size_bytes"],
                  expected_sha256=descriptor["bsl"]["jar_sha256"])
        for name in sorted(expected):
            target = runtime / "jdk" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(java_home / name, target)
        shutil.copyfile(jar, runtime / "bsl-language-server.jar")
        pins.verify()
    finally:
        pins.close()
    pins = RuntimePins()
    try:
        pins.tree(runtime / "jdk", expected)
        pins.file(runtime / "bsl-language-server.jar", expected_size=descriptor["bsl"]["jar_size_bytes"],
                  expected_sha256=descriptor["bsl"]["jar_sha256"])
        pins.verify()
    finally:
        pins.close()
    return {"profile_id": descriptor["profile_id"], "java_files": len(expected),
            "java_manifest_sha256": descriptor["java"]["manifest_sha256"],
            "jar_sha256": descriptor["bsl"]["jar_sha256"],
            "java_version": descriptor["java"]["version"], "bsl_version": descriptor["bsl"]["version"]}


def prepare(args):
    import rentgen_core
    from rentgen_core.local_identity import current_local_principal

    if sys.platform != "win32" or sys.version_info[:2] != (3, 11):
        raise RuntimeError("Actual Windows CPython3.11 required; no skipped acceptance")
    package = Path(rentgen_core.__file__).resolve()
    if not package.is_relative_to(Path(sys.prefix).resolve() / "Lib/site-packages"):
        raise RuntimeError("Core must be installed in the isolated runtime")
    root = args.root.resolve(strict=True)
    source = root / "source"
    source.mkdir()
    module = source / MODULE
    module.parent.mkdir(parents=True)
    module.write_bytes(ORIGINAL.encode("utf-8"))
    descriptor = source / "CommonModules/WorkbenchProbe.xml"
    descriptor.write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses" version="2.20">'
        '<CommonModule uuid="6d493a08-e8f2-4c4b-a94b-0e5ef9e61333"><Properties>'
        '<Name>WorkbenchProbe</Name><Synonym/></Properties></CommonModule></MetaDataObject>\n', "utf-8")
    registry = root / "registry.sqlite3"
    cli(registry, None, "registry-init")
    project = cli(registry, None, "project-register", "--source-root", source,
                  "--state-root", root / "state", "--name", "Owned editor workbench acceptance")["project_id"]
    layers = write(root / "layers.json", [{"layer_id": "base", "ordinal": 0,
        "kind": "base", "root_relative_path": ".", "source_format": "designer_xml"}])
    cli(registry, project, "layers-set", "--expected-revision", 1, "--layers-json", layers)
    cli(registry, project, "capture", "--scanner", args.scanner.resolve(strict=True))
    head = cli(registry, project, "project-head")
    rows = cli(registry, project, "source-list", "--snapshot", head["snapshot"]["snapshot_id"], "--kind", "module")
    ref = next(row["ref"] for row in rows["entries"] if row["ref"]["relative_path"] == MODULE)
    if ref["raw_sha256"] != hashlib.sha256(ORIGINAL.encode()).hexdigest():
        raise RuntimeError("Fixture retained bytes differ")
    local = root / "local-app-data"
    local.mkdir()
    runtime = install_bsl(args.java_home.resolve(strict=True), args.jar.resolve(strict=True), local)
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "README.txt").write_text("Owned synthetic workbench acceptance. No AI or live1C apply.\n", "utf-8")
    profile = {"schema": 1, "core_version": importlib.metadata.version("rentgen-core"),
               "python": sys.executable, "registry": str(registry), "project_id": project}
    write(root / "profile.json", profile)
    write(root / "principal.json", asdict(current_local_principal()))
    from rentgen_core.authorization import OWNER_PERMISSIONS
    write(root / "owner-permissions.json", sorted(OWNER_PERMISSIONS))
    write(root / "read-admin-permissions.json", ["project:admin", "project:read"])
    scenario = {"schema": 1, "head": head, "snapshot": head["snapshot"], "ref": ref,
                "module": MODULE, "source": str(source), "original_sha256": ref["raw_sha256"],
                "scanner": str(args.scanner.resolve(strict=True)),
                "edited": EDITED, "later": LATER, "runtime": runtime,
                "local_app_data": str(local), "workspace": str(workspace)}
    write(root / "scenario.json", scenario)
    return {"prepared": True, "project_id": project, "snapshot_id": ref["snapshot"]["snapshot_id"], "runtime": runtime}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "scanner", "java-home", "jar"):
        parser.add_argument("--" + name, required=True, type=Path)
    try:
        result = prepare(parser.parse_args())
    except Exception as error:
        print(json.dumps({"fixture_error": type(error).__name__, "message": str(error)}))
        raise SystemExit(1)
    print(json.dumps(result))
