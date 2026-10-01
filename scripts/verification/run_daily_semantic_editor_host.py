"""Run one frozen daily attempt or read-only recovery in an isolated editor."""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import subprocess

if __package__:
    from .daily_frozen_inputs import file_record, require_separate_output, verify_frozen
    from .kit_inputs import extract
    from .run_open_editor_host import wait_owned
else:
    from daily_frozen_inputs import file_record, require_separate_output, verify_frozen
    from kit_inputs import extract
    from run_open_editor_host import wait_owned


def _error_record(error):
    return {"type": type(error).__name__, "message": str(error)}


def _observed_inputs(before):
    """Retain readable drift identities even when the frozen verifier refuses."""
    def observed(pin):
        try:
            return file_record(Path(pin["path"]))
        except Exception as error:
            return {"path": pin["path"], "error": _error_record(error)}

    return {"manifest": observed(before["manifest"]),
            "files": {name: observed(pin) for name, pin in before["files"].items()}}


def _daily_profile_files(root):
    records = {}
    for role, name in (("profile", "profile.json"), ("scenario", "daily-scenario.json")):
        path = root / name
        try:
            records[role] = file_record(path)
        except Exception as error:
            records[role] = {"path": str(path), "error": _error_record(error)}
    return records


def _read_daily_profile(root):
    records, values = {}, {}
    for role, name, limit in (("profile", "profile.json", 65536), ("scenario", "daily-scenario.json", 2097152)):
        path = root / name
        pin = file_record(path)
        if pin["size"] > limit:
            raise ValueError("INPUT_BINDING_MISMATCH")
        with path.open("rb") as stream:
            raw = stream.read(limit + 1)
        if len(raw) != pin["size"] or hashlib.sha256(raw).hexdigest() != pin["sha256"]:
            raise ValueError("INPUT_BINDING_MISMATCH")
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("INPUT_BINDING_MISMATCH")
        context = value.get("context_tokens", 32768)
        if type(context) is not int or context not in (8192, 16384, 32768):
            raise ValueError("INPUT_BINDING_MISMATCH")
        records[role], values[role] = pin, value
    context = values["profile"].get("context_tokens", 32768)
    if context != values["scenario"].get("context_tokens", 32768):
        raise ValueError("INPUT_BINDING_MISMATCH")
    return values["profile"], values["scenario"], context, records


def run(args):
    if (args.mode == "recovery") != (args.prior is not None):
        raise ValueError("Recovery requires --prior; attempt does not accept --prior")
    binding, checked = verify_frozen(args.frozen_inputs)
    frozen_before = dict(checked)
    root = args.profile.resolve(strict=True)
    config, scenario, context_tokens, daily_before = _read_daily_profile(root)
    if scenario["frozen_inputs"] != checked["manifest"]:
        raise ValueError("INPUT_BINDING_MISMATCH")
    for role, value in (("vsix", args.vsix), ("editor", args.editor)):
        if str(value.resolve(strict=True)) != checked["files"][role]["path"]:
            raise ValueError("INPUT_BINDING_MISMATCH")
    if config["python"] != checked["files"]["python"]["path"] or config["core_version"] != binding["core_version"] or scenario["companion_version"] != binding["companion_version"]:
        raise ValueError("INPUT_BINDING_MISMATCH")
    metadata = BytesParser().parsebytes(Path(checked["files"]["core_metadata"]["path"]).read_bytes())
    if metadata.get("Name") != "rentgen-core" or metadata.get("Version") != binding["core_version"]:
        raise ValueError("INPUT_BINDING_MISMATCH")
    prior = args.prior.resolve(strict=True) if args.prior else None
    if prior:
        if prior.stat().st_size > 4 * 1024**2:
            raise ValueError("Prior daily result exceeds limit")
        previous = json.loads(prior.read_text("utf-8"))
        if previous.get("schema") != "rentgen-daily-semantic/1" or previous.get("profile_root") != str(root):
            raise ValueError("INPUT_BINDING_MISMATCH")
    protected = {**checked, "directories": {**checked["directories"], "daily_profile": {"path": str(root)}},
                 "files": {**checked["files"], **({"daily_prior": {"path": str(prior)}} if prior else {})}}
    output = require_separate_output(args.output, protected)
    output.mkdir(parents=True, exist_ok=False)
    extract(args.vsix.resolve(strict=True), output / "unpacked")
    extension = output / "unpacked/extension"
    manifest = json.loads((extension / "package.json").read_text("utf-8"))
    if manifest.get("version") != binding["companion_version"] or manifest.get("publisher") != "rentgen" or manifest.get("name") != "project-companion":
        raise ValueError("INPUT_BINDING_MISMATCH")
    host = Path(__file__).with_name("companion_host")
    script = host / ("daily.cjs" if args.mode == "attempt" else "daily_semantic_recovery.cjs")
    checked.update(mode=args.mode, context_tokens=context_tokens, daily_profile_files=daily_before, core_version=binding["core_version"], companion_version=binding["companion_version"], validator=file_record(extension / "lib/tests-result.cjs"), source_validator=file_record(extension / "lib/core.cjs"), harness={name: file_record(host / name) for name in ("daily.cjs", "daily_semantic.cjs", "daily_semantic_recovery.cjs")})
    inputs = output / "inputs.json"
    inputs.write_text(json.dumps(checked, ensure_ascii=False, indent=2), "utf-8")
    env = os.environ.copy()
    for name in ("ELECTRON_RUN_AS_NODE", "RENTGEN_DAILY_PRIOR", "RENTGEN_TESTS_ACCEPTANCE_PRIOR"):
        env.pop(name, None)
    env.update(RENTGEN_EDITOR_PROFILE=str(root), RENTGEN_DAILY_OUTPUT=str(output / "acceptance.json"), RENTGEN_DAILY_INPUTS=str(inputs))
    if prior:
        env["RENTGEN_DAILY_PRIOR"] = str(prior)
    command = [str(args.editor.resolve(strict=True)), "--user-data-dir", str(output / "user"), "--extensions-dir", str(output / "extensions"), "--extensionDevelopmentPath=" + str(extension), "--extensionTestsPath=" + str(script.resolve()), "--disable-workspace-trust", "--skip-welcome", "--skip-release-notes", str(root / "workspace")]
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    code, failure, execution_error, recheck_error, after = None, None, None, None, None
    try:
        if _daily_profile_files(root) != daily_before:
            raise ValueError("INPUT_BINDING_MISMATCH")
        with (output / "host.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(command, env=env, stdout=log, stderr=log, startupinfo=startup)
            code = wait_owned(process, log, timeout=1550 if args.mode == "attempt" else 120)
    except Exception as error:
        failure, execution_error = error, _error_record(error)
    try:
        _, after = verify_frozen(args.frozen_inputs)
    except Exception as error:
        recheck_error = _error_record(error)
        if failure is None:
            failure = error
    daily_after = _daily_profile_files(root)
    preserved = after is not None and after == frozen_before and daily_after == daily_before
    receipt = {"input_bytes_preserved": preserved, "editor_exit_code": code,
               "before": frozen_before, "after": after, "execution_error": execution_error,
               "context_tokens": context_tokens, "daily_profile_before": daily_before,
               "daily_profile_after": daily_after,
               "input_recheck_error": recheck_error, "source_ci_qualified_by_this_check": False}
    if not preserved:
        receipt["observed_inputs"] = _observed_inputs(frozen_before)
    (output / "input-preservation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), "utf-8")
    if failure is not None:
        raise failure
    if not preserved:
        raise ValueError("INPUT_BINDING_MISMATCH")
    print(json.dumps({"exit_code": code, "mode": args.mode, "report": str(output / "acceptance.json"), "input_bytes_preserved": preserved, "source_ci_qualified_by_this_check": False}))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("attempt", "recovery"), required=True)
    for name in ("profile", "output", "vsix", "editor", "frozen-inputs"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prior", type=Path)
    raise SystemExit(run(parser.parse_args()))
