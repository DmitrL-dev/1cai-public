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
MAX_COMPANION_DELTA_ENTRIES = 32
PHASE_FLAGS = {
    "first": {"opened_project", "metadata_search", "manual_draft_saved", "real_bsl", "problems_exact_revision",
              "concurrent_cli", "stale_refused", "revoked_write_refused", "forged_handle_refused",
              "crash_stage_committed", "snapshot_pinned_before_restart"},
    "restart": {"fresh_extension_host", "persisted_context_restored", "pinned_snapshot_restored",
                "historical_draft_restored", "reconciled_unobserved_commit", "inspect_did_not_repeat_save",
                "historical_bsl_bound", "source_unchanged"},
}
PHASE_CHECKPOINTS = {"environment", "activation", "initial-inventories", "final-inventories", "complete",
    "first.snapshot", "first.metadata", "first.forged-handle", "first.manual-draft", "first.bsl",
    "first.concurrent-edit", "first.revocation", "first.unobserved-commit", "first.advance-head",
    "first.persist-selection", "first.handoff", "restart.handoff", "restart.process", "restart.snapshot",
    "restart.selection", "restart.current-head", "restart.historical-draft", "restart.intent-recovery",
    "restart.receipt-replay", "restart.historical-bsl", "restart.source"}
PHASE_ERROR_CODES = {"ERR_ASSERTION", "ETIMEDOUT", "PROJECT_FORBIDDEN", "DRAFT_CONFLICT",
    "WORKBENCH_STATE_INVALID", "WORKBENCH_PROFILE_MISMATCH", "UNKNOWN_VIEW_HANDLE",
    "TRUST_REQUIRED", "EDITOR_PROFILE_REQUIRED", "WINDOWS_PROFILE_REQUIRED"}
PHASE_OPERATORS = {"strictEqual", "notStrictEqual", "deepStrictEqual", "notDeepStrictEqual", "==",
                   "rejects", "match", "doesNotReject"}


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


def companion_delta(actual, expected, changed, allowed_package_rewrites):
    def entries(names):
        records = []
        for name in sorted(names)[:MAX_COMPANION_DELTA_ENTRIES]:
            encoded = name.encode("utf-8", "surrogatepass")
            printable = (len(encoded) <= 256 and not name.startswith("/") and "\\" not in name
                         and ":" not in name and all(part not in {"", ".", ".."} for part in name.split("/"))
                         and all(char.isprintable() for char in name))
            record = {"relative_path": name} if printable else {
                "relative_path_sha256": hashlib.sha256(encoded).hexdigest(), "relative_path_omitted": True}
            record.update(expected=expected.get(name), actual=actual.get(name))
            if name in allowed_package_rewrites:
                record["allowed_package_json_rewrite"] = True
            records.append(record)
        return {"count": len(names), "truncated": len(names) > MAX_COMPANION_DELTA_ENTRIES, "entries": records}

    missing, unexpected = set(expected) - set(actual), set(actual) - set(expected)
    return {"schema": 1, "scope": "owned synthetic editor attempt; relative filenames and hashes only",
            "accepted": not missing and not unexpected and not (changed - allowed_package_rewrites),
            "expected_files": len(expected), "actual_files": len(actual),
            "entry_limit_per_category": MAX_COMPANION_DELTA_ENTRIES,
            "missing": entries(missing), "unexpected": entries(unexpected), "content_changed": entries(changed)}


def companion_files(extension, vsix, diagnostic=None):
    actual = tree(extension)
    with ZipFile(vsix) as archive:
        expected = {name.removeprefix("extension/"): archive.read(name) for name in archive.namelist()
                    if name.startswith("extension/") and not name.endswith("/")}
        # The pinned installer removes the prefix /^extension/, so the outer
        # extension.vsixmanifest is installed as .vsixmanifest as well.
        require(".vsixmanifest" not in expected, "VSIX payload shadows installed manifest")
        expected[".vsixmanifest"] = archive.read("extension.vsixmanifest")
    expected_inventory = {name: {"sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
                          for name, raw in expected.items()}
    changed, allowed_package_rewrites = set(), set()
    for name in sorted(set(actual) & set(expected)):
        raw, installed = expected[name], (extension / name).read_bytes()
        if installed == raw:
            continue
        changed.add(name)
        if name == "package.json":
            # Only installation metadata and JSON serialization may differ;
            # executable/configuration properties must match the exact VSIX.
            try:
                value, original = json.loads(installed), json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and isinstance(original, dict):
                value.pop("__metadata", None)
                if value == original:
                    allowed_package_rewrites.add(name)
    if diagnostic is not None:
        diagnostic.update(companion_delta(actual, expected_inventory, changed, allowed_package_rewrites))
    require(set(actual) == set(expected), "Installed Companion file inventory differs from VSIX")
    rejected = sorted(changed - allowed_package_rewrites)
    if rejected:
        name = rejected[0]
        raise RuntimeError("Installed extension manifest differs" if name == "package.json"
                           else "Installed extension bytes differ: " + name)
    return actual


def reduce_phase(value):
    allowed = {"schema", "accepted", "phase", "runtime", "process_id", "editor_api_version", "app_name", "scope",
               "fault_model", "model_calls", "live_1c_apply", "bsl", "opened_project", "metadata_search",
               "manual_draft_saved", "real_bsl", "problems_exact_revision", "concurrent_cli", "stale_refused",
               "revoked_write_refused", "forged_handle_refused", "crash_stage_committed", "snapshot_pinned_before_restart",
               "fresh_extension_host", "persisted_context_restored", "pinned_snapshot_restored", "historical_draft_restored",
               "reconciled_unobserved_commit", "inspect_did_not_repeat_save", "historical_bsl_bound", "source_unchanged",
               "checkpoint"}
    require(value.get("accepted") is True and value.get("runtime") == "actual_windows_electron_extension_host", "No positive real editor receipt")
    required = PHASE_FLAGS
    require(value.get("phase") in required and all(value.get(key) is True for key in required[value["phase"]]), "Incomplete real editor phase receipt")
    require(value.get("schema") == 1 and type(value.get("process_id")) is int and value["process_id"] > 0
            and value.get("model_calls") == 0 and value.get("live_1c_apply") is False
            and value.get("fault_model") == "durable_intent_commit_unobserved", "Editor scope/provenance differs")
    return {k: v for k, v in value.items() if k in allowed}


def read_phase_file(profile, phase):
    require(phase in PHASE_FLAGS, "Unknown editor phase")
    file = profile / ("phase-" + phase + ".json")
    info = file.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not file.is_symlink()
            and not getattr(info, "st_file_attributes", 0) & 0x400, "Unsafe editor phase receipt")
    with file.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        require((opened.st_dev, opened.st_ino, opened.st_size) == (info.st_dev, info.st_ino, info.st_size)
                and 0 < opened.st_size <= 1024**2, "Editor receipt bound or identity differs")
        raw = stream.read(1024**2 + 1)
        require(len(raw) == opened.st_size, "Editor receipt changed or exceeds bound")
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "Duplicate editor receipt field")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs)


def _phase_value(value):
    require(type(value) is dict and type(value.get("type")) is str, "Invalid assertion projection")
    kind = value["type"]
    if kind in {"null", "undefined", "object", "number", "other"}:
        require(set(value) == {"type"}, "Unexpected assertion data")
    elif kind == "boolean":
        require(set(value) == {"type", "value"} and type(value["value"]) is bool, "Invalid boolean projection")
    elif kind == "integer":
        require(set(value) == {"type", "value"} and type(value["value"]) is int
                and abs(value["value"]) <= 2**53 - 1, "Invalid integer projection")
    elif kind == "array":
        require(set(value) == {"type", "length"} and type(value["length"]) is int
                and 0 <= value["length"] <= 2**32 - 1, "Invalid array projection")
    elif kind == "string":
        require(set(value) == {"type", "size_bytes", "sha256"} and type(value["size_bytes"]) is int
                and 0 <= value["size_bytes"] <= 2**32 - 1, "Invalid string projection")
        require((value["size_bytes"] > 1024**2 and value["sha256"] is None)
                or (value["size_bytes"] <= 1024**2 and type(value["sha256"]) is str
                    and re.fullmatch(r"[a-f0-9]{64}", value["sha256"])), "Invalid assertion digest")
    else:
        require(False, "Unknown assertion projection")
    return dict(value)


def reduce_phase_failure(value, phase):
    require(type(value) is dict and phase in PHASE_FLAGS, "Invalid failed editor phase")
    flags = set().union(*PHASE_FLAGS.values())
    metadata = {"schema", "accepted", "phase", "runtime", "process_id", "editor_api_version", "app_name", "scope",
                "fault_model", "model_calls", "live_1c_apply", "bsl", "checkpoint", "error"}
    require(set(value) <= metadata | flags and value.get("schema") == 1 and type(value["schema"]) is int
            and value.get("accepted") is False and value.get("phase") == phase
            and value.get("runtime") == "actual_windows_electron_extension_host"
            and type(value.get("process_id")) is int and 0 < value["process_id"] <= 2**31 - 1
            and type(value.get("model_calls")) is int and value["model_calls"] == 0
            and value.get("live_1c_apply") is False
            and value.get("fault_model") == "durable_intent_commit_unobserved", "Failed phase provenance differs")
    point = value.get("checkpoint")
    require(type(point) is str and point in PHASE_CHECKPOINTS
            and ("." not in point or point.startswith(phase + ".")), "Unknown failed editor checkpoint")
    error = value.get("error")
    require(type(error) is dict and set(error) == {"category", "code", "operator", "actual", "expected"},
            "Raw editor exception data refused")
    require(error["category"] in {"assertion", "timeout", "error"}
            and (error["code"] is None or error["code"] in PHASE_ERROR_CODES)
            and (error["operator"] is None or error["operator"] in PHASE_OPERATORS), "Unknown editor error category")
    reduced = {k: value[k] for k in ("schema", "accepted", "phase", "runtime", "process_id", "checkpoint",
                                     "fault_model", "model_calls", "live_1c_apply")}
    for key in flags & value.keys():
        require(type(value[key]) is bool, "Invalid editor progress flag")
        reduced[key] = value[key]
    reduced["error"] = {**{k: error[k] for k in ("category", "code", "operator")},
                        "actual": _phase_value(error["actual"]), "expected": _phase_value(error["expected"])}
    return reduced


class AcceptanceReceipt:
    """Update only this attempt's original bounded receipt; other saves stay exclusive."""
    def __init__(self, path):
        self.path = path
        self._identity = None

    def _check(self, info):
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and not getattr(info, "st_file_attributes", 0) & 0x400,
                "Unsafe acceptance receipt")
        identity = info.st_dev, info.st_ino
        require(self._identity is None or identity == self._identity,
                "Acceptance receipt identity changed")
        return identity

    def save(self, value):
        data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
        require(len(data) <= 2 * 1024**2, "Receipt exceeds 2 MiB")
        if self._identity is not None:
            self._check(self.path.lstat())
        with self.path.open("x+b" if self._identity is None else "r+b") as stream:
            self._identity = self._check(os.fstat(stream.fileno()))
            self._check(self.path.lstat())
            stream.write(data)
            stream.truncate()
            stream.flush()
            os.fsync(stream.fileno())
            self._check(os.fstat(stream.fileno()))
            self._check(self.path.lstat())


def finish_receipt(acceptance, receipt, primary_error):
    try:
        acceptance.save(receipt)
    except Exception:
        if primary_error is None:
            raise


def phase_attempt(command_args, *, output, evidence, profile, phase, receipt, acceptance):
    """Preserve validated earlier phases and reduce a failed host before rethrow."""
    phases = receipt.setdefault("phases", {})
    try:
        command(command_args, output, evidence, "host-" + phase, timeout=390)
        reduced = reduce_phase(read_phase_file(profile, phase))
        supervisor = json.loads((evidence / ("supervisor-" + phase + ".json")).read_text("utf-8"))
        require(supervisor["accepted"] is True and supervisor["cleanup_complete"] is True, "Editor descendants not proved closed")
    except Exception:
        try:
            reduced = reduce_phase_failure(read_phase_file(profile, phase), phase)
        except Exception:
            reduced = {"schema": 1, "accepted": False, "phase": phase,
                       "diagnostic": "failed-phase-receipt-unavailable-or-invalid"}
        receipt.setdefault("phase_failures", {})[phase] = reduced
        raise
    reduced["owned_process_cleanup"] = True
    phases[phase] = reduced
    acceptance.save(receipt)


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
    acceptance = AcceptanceReceipt(evidence / "acceptance.json")
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
        receipt["companion_inventory"] = {"installed": {}}
        extension_inventory = companion_files(extension, vsix, receipt["companion_inventory"]["installed"])
        launch["extension_path"] = str(extension)
        # This controlled supervisor descriptor gains its installed path once;
        # extension workspaceState and product inputs are never patched here.
        launch_file.write_text(json.dumps(launch, indent=2) + "\n", "utf-8")
        native_before = tree(profile / "local-app-data/Rentgen/runtimes")
        phases = receipt["phases"] = {}
        for phase in ("first", "restart"):
            phase_attempt([python, "-I", "-B", HERE / "supervisor.py", "--launch", launch_file, "--mode", phase],
                          output=output, evidence=evidence, profile=profile, phase=phase, receipt=receipt,
                          acceptance=acceptance)
        require(phases["first"]["process_id"] != phases["restart"]["process_id"], "Fresh Host not observed")
        require(tree(output / "editor") == editor_inventory, "Pinned editor files changed")
        require(tree(output / "java") == java_inventory, "Pinned JDK input files changed")
        require(tree(profile / "local-app-data/Rentgen/runtimes") == native_before, "Installed BSL runtime files changed")
        receipt["companion_inventory"]["after_hosts"] = {}
        require(companion_files(extension, vsix, receipt["companion_inventory"]["after_hosts"]) == extension_inventory,
                "Installed Companion changed")
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
        receipt["error"] = {"type": type(error).__name__ if type(error).__name__ in {
            "RuntimeError", "ValueError", "TypeError", "KeyError", "OSError", "FileNotFoundError",
            "TimeoutExpired", "JSONDecodeError"} else "Error"}
        raise
    finally:
        finish_receipt(acceptance, receipt, sys.exc_info()[1])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkout", "kit", "build-receipt", "vsix", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    for name in ("expected-commit", "trigger-head"):
        parser.add_argument("--" + name, required=True)
    verify(parser.parse_args())
