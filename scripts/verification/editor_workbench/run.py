"""Qualify one installed Windows workbench slice in two real editor processes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
from zipfile import ZipFile

from archive import extract_verified
from inputs import PINS, bind_checkout, digest, download, load, require, save

HERE = Path(__file__).resolve().parent


def tree(root):
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in [None, *dirs, *files]:
            path = Path(directory) if name is None else Path(directory) / name
            info = path.lstat()
            require(not path.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400, "Reparse point in runtime tree")
            require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "Runtime alias or special file")
        for name in files:
            path = Path(directory) / name
            result[path.relative_to(root).as_posix()] = {"sha256": digest(path), "size_bytes": path.stat().st_size}
            require(len(result) <= 50000, "Runtime inventory exceeds bound")
    return result


def clean_env():
    allowed = {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATHEXT", "PATH", "TEMP", "TMP",
               "USERPROFILE", "APPDATA", "LOCALAPPDATA", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE"}
    return {k: v for k, v in os.environ.items() if k.upper() in allowed} | {"PYTHONUTF8": "1", "PIP_CONFIG_FILE": os.devnull}


def command(args, cwd, evidence, name, timeout=180, env=None):
    with (evidence / (name + ".log")).open("xb") as stream:
        result = subprocess.run(list(map(str, args)), cwd=cwd, env=clean_env() if env is None else env,
                                stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    require(result.returncode == 0, name + " failed; inspect private CI log")


def installed_files(wheel, runtime, binding):
    result = {}
    with ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.endswith("/") or not name.startswith(("rentgen_core/", "rentgen_graph/", "rentgen_diagnostics/")):
                continue
            raw = archive.read(name)
            require(name in binding["files"], "Wheel contains unbound product file")
            expected = {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
            require(binding["files"][name] == expected, "Wheel source bytes differ from checkout")
            target = runtime / "Lib/site-packages" / name
            require(not target.is_symlink() and target.read_bytes() == raw, "Installed product bytes differ from wheel")
            result[name] = expected
    require(result, "No installed product files verified")
    return result


def companion_files(extension, vsix):
    actual = tree(extension)
    with ZipFile(vsix) as archive:
        expected = {name.removeprefix("extension/"): archive.read(name) for name in archive.namelist()
                    if name.startswith("extension/") and not name.endswith("/")}
    require(set(actual) == set(expected), "Installed Companion file inventory differs from VSIX")
    for name, raw in expected.items():
        installed = (extension / name).read_bytes()
        if name == "package.json":
            # VS Code may add installation metadata; executable/configuration
            # properties must remain byte-derived from the exact VSIX manifest.
            value, original = json.loads(installed), json.loads(raw)
            value.pop("__metadata", None)
            require(value == original, "Installed extension manifest differs")
        else:
            require(installed == raw, "Installed extension bytes differ: " + name)
    return actual


def reduce_phase(value):
    allowed = {"schema", "accepted", "phase", "runtime", "process_id", "editor_api_version", "app_name", "scope",
               "fault_model", "model_calls", "live_1c_apply", "bsl", "opened_project", "metadata_search",
               "manual_draft_saved", "real_bsl", "problems_exact_revision", "concurrent_cli", "stale_refused",
               "revoked_write_refused", "forged_handle_refused", "crash_stage_committed", "snapshot_pinned_before_restart",
               "fresh_extension_host", "persisted_context_restored", "pinned_snapshot_restored", "historical_draft_restored",
               "reconciled_unobserved_commit", "inspect_did_not_repeat_save", "historical_bsl_bound", "source_unchanged"}
    require(value.get("accepted") is True and value.get("runtime") == "actual_windows_electron_extension_host", "No positive real editor receipt")
    required = {
        "first": {"opened_project", "metadata_search", "manual_draft_saved", "real_bsl", "problems_exact_revision",
                  "concurrent_cli", "stale_refused", "revoked_write_refused", "forged_handle_refused",
                  "crash_stage_committed", "snapshot_pinned_before_restart"},
        "restart": {"fresh_extension_host", "persisted_context_restored", "pinned_snapshot_restored",
                    "historical_draft_restored", "reconciled_unobserved_commit", "inspect_did_not_repeat_save",
                    "historical_bsl_bound", "source_unchanged"},
    }
    require(value.get("phase") in required and all(value.get(key) is True for key in required[value["phase"]]), "Incomplete real editor phase receipt")
    require(value.get("schema") == 1 and type(value.get("process_id")) is int and value["process_id"] > 0
            and value.get("model_calls") == 0 and value.get("live_1c_apply") is False
            and value.get("fault_model") == "durable_intent_commit_unobserved", "Editor scope/provenance differs")
    return {k: v for k, v in value.items() if k in allowed}


def verify(args):
    require(sys.platform == "win32" and sys.version_info[:2] == (3, 11), "Real Windows CPython3.11 required; no skipped success")
    parent = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    output = args.output.absolute()
    require(output.parent == parent and output.resolve() == output and re.fullmatch(r"rg-editor-[a-f0-9]{12}", output.name), "Expected new owned RUNNER_TEMP child")
    require(not output.exists() and shutil.disk_usage(parent).free >= 6 * 1024**3, "New workspace and6GiB free required")
    output.mkdir()
    evidence = output / "evidence"; evidence.mkdir()
    receipt = {"schema": 1, "accepted": False, "source_commit": args.expected_commit,
               "trigger_head": args.trigger_head, "scope": "installed Windows editor API workbench slice",
               "human_gui_accessibility": "NOT_RUN", "full_product_ready": False,
               "model_calls": 0, "live_1c_apply": False, "fault_model": "durable_intent_commit_unobserved"}
    try:
        checkout = args.checkout.resolve(strict=True)
        vsix = args.vsix.resolve(strict=True)
        binding = bind_checkout(checkout, args.expected_commit, args.trigger_head, vsix)
        save(evidence / "source-binding.json", binding)
        delivery = load(HERE.parent / "verify_service_scm_delivery.py", "editor_workbench_kit_delivery")
        build = json.loads(args.build_receipt.read_text("utf-8"))
        kit_sha = delivery.validate_provenance(args.kit, build, args.expected_commit)
        kit, wheel, manifest = delivery.unpack(args.kit.resolve(strict=True), output / "kit", args.expected_commit, build)
        runtime = output / "python"
        copied = delivery.copy_interpreter(runtime)
        python = runtime / "python.exe"
        command([python, "-I", "-B", "-m", "ensurepip", "--default-pip"], output, evidence, "ensurepip")
        command([python, "-I", "-B", "-m", "pip", "install", "--no-index", "--no-deps", "--only-binary=:all:", wheel], output, evidence, "install-core")
        command([python, "-I", "-B", "-m", "pip", "check"], output, evidence, "pip-check")
        probe = delivery.direct_probe(python)
        require(probe["version"] == manifest["version"], "Installed Core version differs")
        installed = installed_files(wheel, runtime, binding)
        downloads = output / "downloads"; downloads.mkdir()
        pins = {}
        for name in ("editor", "java", "bsl"):
            pins[name] = download(name, downloads / (name + (".jar" if name == "bsl" else ".zip")))
        editor_inventory = extract_verified(downloads / "editor.zip", output / "editor", **{k: PINS["editor"][k] for k in ("sha256", "size_bytes")})
        java_inventory = extract_verified(downloads / "java.zip", output / "java", **{k: PINS["java"][k] for k in ("sha256", "size_bytes")})
        roots = list((output / "java").iterdir())
        require(len(roots) == 1 and (roots[0] / "bin/java.exe").is_file(), "Expected exact pinned JDK root")
        editor = output / "editor/VSCodium.exe"
        require(editor.is_file() and (editor.parent / "resources/app/out/cli.js").is_file(), "Pinned editor CLI missing")
        require(any("license" in name.casefold() for name in editor_inventory), "Editor license notice missing")
        require(any("thirdpartynotices" in name.casefold() for name in editor_inventory), "Editor third-party notices missing")
        profile = output / "profile"; profile.mkdir()
        command([python, "-I", "-B", HERE / "fixture.py", "--root", profile, "--scanner", kit / "bsl-scan.exe",
                 "--java-home", roots[0], "--jar", downloads / "bsl.jar"], output, evidence, "prepare-fixture", timeout=240)
        settings = output / "editor-user/User"; settings.mkdir(parents=True)
        save(settings / "settings.json", {"update.mode": "none", "extensions.autoCheckUpdates": False,
            "extensions.autoUpdate": False, "extensions.ignoreRecommendations": True,
            "telemetry.telemetryLevel": "off", "files.autoSave": "off", "window.restoreWindows": "none",
            "workbench.startupEditor": "none", "security.workspace.trust.enabled": False})
        launch = {"schema": 1, "editor": str(editor), "editor_exe_sha256": digest(editor),
                  "editor_api_version": PINS["editor"]["api_version"], "vsix": str(vsix),
                  "harness": str(HERE), "companion_id": binding["companion_id"], "companion_version": binding["companion_version"]}
        launch_file = output / "launch.json"
        save(launch_file, launch)
        command([python, "-I", "-B", HERE / "supervisor.py", "--launch", launch_file, "--mode", "install"], output, evidence, "install-vsix", timeout=150)
        extensions = list((output / "extensions").glob(binding["companion_id"] + "-*/package.json"))
        require(len(extensions) == 1, "Expected only the installed exact Companion")
        extension = extensions[0].parent
        extension_inventory = companion_files(extension, vsix)
        launch["extension_path"] = str(extension)
        # This controlled supervisor descriptor gains its installed path once;
        # extension workspaceState and product inputs are never patched here.
        launch_file.write_text(json.dumps(launch, indent=2) + "\n", "utf-8")
        native_before = tree(profile / "local-app-data/Rentgen/runtimes")
        phases = {}
        for phase in ("first", "restart"):
            command([python, "-I", "-B", HERE / "supervisor.py", "--launch", launch_file, "--mode", phase], output, evidence, "host-" + phase, timeout=390)
            report_file = profile / ("phase-" + phase + ".json")
            require(report_file.stat().st_size <= 1024**2, "Editor receipt bound")
            phases[phase] = reduce_phase(json.loads(report_file.read_text("utf-8")))
            supervisor = json.loads((evidence / ("supervisor-" + phase + ".json")).read_text("utf-8"))
            require(supervisor["accepted"] is True and supervisor["cleanup_complete"] is True, "Editor descendants not proved closed")
            phases[phase]["owned_process_cleanup"] = True
        require(phases["first"]["process_id"] != phases["restart"]["process_id"], "Fresh Host not observed")
        require(tree(output / "editor") == editor_inventory, "Pinned editor files changed")
        require(tree(output / "java") == java_inventory, "Pinned JDK input files changed")
        require(tree(profile / "local-app-data/Rentgen/runtimes") == native_before, "Installed BSL runtime files changed")
        require(companion_files(extension, vsix) == extension_inventory, "Installed Companion changed")
        require(installed_files(wheel, runtime, binding) == installed, "Installed Core files changed")
        require(all(digest(runtime / name) == value for name, value in copied.items()), "Copied Python files changed")
        require(bind_checkout(checkout, args.expected_commit, args.trigger_head, vsix)["files"] == binding["files"], "Checkout changed during editor run")
        runtime_binding = {"schema": 1, "downloads": pins, "editor_files": len(editor_inventory),
            "editor_exe_sha256": digest(editor), "jdk_input_files": len(java_inventory), "native_runtime_files": len(native_before),
            "kit_sha256": kit_sha, "wheel_sha256": digest(wheel), "scanner_sha256": digest(kit / "bsl-scan.exe"),
            "vsix_sha256": digest(vsix), "companion_files": len(extension_inventory), "installed_product_files": len(installed),
            "python_runtime_files": len(copied), "source_inventory_sha256": hashlib.sha256(json.dumps(binding["files"], sort_keys=True).encode()).hexdigest(),
            "files_unchanged": True, "licenses_and_notices_retained": True}
        save(evidence / "runtime-binding.json", runtime_binding)
        receipt.update(accepted=True, phases=phases, artifact_bindings=runtime_binding,
                       all_editor_process_trees_closed=True, exact_source_and_installed_bytes_verified=True)
    except Exception as error:
        receipt["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        save(evidence / "acceptance.json", receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkout", "kit", "build-receipt", "vsix", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("expected-commit", "trigger-head"):
        parser.add_argument("--" + name, required=True)
    verify(parser.parse_args())
