"""Verify an exact installed wheel with owned handwritten source-fact inputs.

Linux-only delivery mechanics, not Designer, compiler, runtime or accuracy
acceptance. All generated files stay under a new explicit output directory.
No customer profile, live 1C, model, network download or native probe is used.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from uuid import UUID
import zipfile


if sys.flags.optimize:
    raise RuntimeError("Delivery verification requires unoptimized Python")

HASH = re.compile(r"[0-9a-f]{64}\Z")
ROLES = ("input_core", "source_scanner", "source_kernel")
CALLER = "CommonModules/DeliveryCaller/Ext/Module.bsl"
CANDIDATE = "CommonModules/DeliveryCandidate/Ext/Module.bsl"
METADATA = "CommonModules/DeliveryCandidate.xml"
SCOPE = "experimental Linux installed-wheel handwritten source-fact mechanics only"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def parse_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, "Duplicate JSON object key")
            value[key] = item
        return value

    def reject_constant(_):
        raise RuntimeError("Nonstandard JSON constant")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject_constant)


def check_disclosure(value, raw, output):
    encoded = json.dumps(value, ensure_ascii=False)
    require(b"SYNTH_" not in raw and "SYNTH_" not in encoded
            and str(output).encode("utf-8") not in raw and str(output) not in encoded,
            "Source text or host path escaped into output")


def pinned_bytes(path, expected):
    require(HASH.fullmatch(expected or "") is not None, "An explicit expected SHA-256 is required")
    raw = path.resolve(strict=True).read_bytes()
    require(sha(raw) == expected, "Input does not match its reviewed SHA-256")
    return raw


def empty_children():
    """ECHILD, rather than a procfs scan, proves no owned children remain."""
    try:
        os.waitid(os.P_ALL, 0, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError as error:
        if error.errno == errno.ECHILD:
            return True
        raise
    return False


def proc_identity(path):
    raw = path.read_bytes()
    prefix, delimiter, suffix = raw.rpartition(b")")
    fields = suffix.split()
    require(bool(delimiter) and b" (" in prefix and len(fields) > 19, "Invalid procfs identity")
    return int(prefix.split(b" ", 1)[0]), int(fields[1]), int(fields[19])


def verify_proc_namespace():
    own = proc_identity(Path("/proc/self/stat"))
    require(own == proc_identity(Path(f"/proc/{os.getpid()}/stat"))
            and own[:2] == (os.getpid(), os.getppid()), "Procfs and kernel PID namespaces differ")


def cleanup_adopted():
    """Only for this standalone, empty-baseline subreaper; never kill by name.

    A timeout can kill a CLI before it reaps its helper. Adopt, verify exact
    direct-child authority, terminate and reap those children as safety cleanup.
    Such cleanup makes the smoke fail; it is never product-cleanup evidence.
    """
    deadline = time.monotonic() + 3
    observed = set()
    while time.monotonic() < deadline:
        if empty_children():
            return sorted(observed)
        verify_proc_namespace()
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                pid, parent, started = proc_identity(entry / "stat")
                require(pid == int(entry.name), "Numeric procfs PID mismatch")
                if parent != os.getpid():
                    continue
                observed.add(pid)
                require(proc_identity(entry / "stat") == (pid, parent, started), "Owned child identity changed")
                # An unreaped child cannot have its PID recycled between this
                # non-destructive kernel authority check and our signal/reap.
                exited = os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if exited is None:
                    os.kill(pid, signal.SIGKILL)
                else:
                    os.waitpid(pid, os.WNOHANG)
            except (ChildProcessError, FileNotFoundError, ProcessLookupError):
                continue
        time.sleep(0.01)
    require(empty_children(), "Owned-child cleanup unconfirmed")
    return sorted(observed)


def run(argv, output, label, *, cwd, env, timeout):
    """Bound a single fixed-purpose command and preserve its exact streams."""
    directory = output / "commands" / label
    directory.mkdir()
    record = {"argv": list(map(str, argv)), "timeout_seconds": timeout,
              "exit_code": None, "timed_out": False, "safety_cleanup_pids": []}
    process = None
    started = time.monotonic()
    try:
        with (directory / "stdout.bin").open("xb") as stdout, (directory / "stderr.bin").open("xb") as stderr:
            process = subprocess.Popen(record["argv"], cwd=cwd, env=env,
                                       stdin=subprocess.DEVNULL, stdout=stdout,
                                       stderr=stderr, close_fds=True)
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                raise
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                record["exit_code"] = process.returncode
    finally:
        try:
            record["safety_cleanup_pids"] = cleanup_adopted()
            require(not record["safety_cleanup_pids"], "Command left adopted children; safety cleanup was required")
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 6)
            record["cleanup_confirmed"] = empty_children()
            for stream in ("stdout", "stderr"):
                path = directory / (stream + ".bin")
                if path.exists():
                    record[stream + "_sha256"] = sha(path.read_bytes())
            save_json(directory / "command.json", record)
    require(not record["timed_out"], "Command exceeded its deadline")
    return record, (directory / "stdout.bin").read_bytes(), (directory / "stderr.bin").read_bytes()


def owned_archive(path):
    caller = (b'Procedure Run()\n// SYNTH_PRIVATE_COMMENT\n'
              b'Value = "SYNTH_PRIVATE_LITERAL";\n'
              b'DeliveryCandidate.SYNTH_DeliveryTarget();\nEndProcedure\n')
    files = {
        CALLER: caller,
        CANDIDATE: b"Procedure SYNTH_DeliveryTarget() Export\nEndProcedure\n",
        METADATA: (b'<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
                   b'<CommonModule><Properties><Name>DeliveryCandidate</Name>'
                   b'<Server>false</Server></Properties></CommonModule></MetaDataObject>'),
        "Configuration.xml": b"SYNTH_ROOT_METADATA_NOT_READ",
        "unrelated.bin": b"SYNTH_UNRELATED_CONTENT",
    }
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as target:
        for name, raw in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o600 << 16
            target.writestr(info, raw)
    start = caller.index(b"DeliveryCandidate.SYNTH_DeliveryTarget")
    return files, {"start": start, "end": start + len(b"DeliveryCandidate.SYNTH_DeliveryTarget")}


def fingerprint(paths):
    result = {}
    for label, root in paths.items():
        candidates = [root, *sorted(root.rglob("*"))] if root.is_dir() else [root]
        for path in candidates:
            require(not path.is_symlink(), "Unexpected symlink in owned state")
            key = label + "/" + (str(path.relative_to(root)) if root.is_dir() else "")
            result[key] = {"kind": "directory"} if path.is_dir() else {"kind": "file", "sha256": sha(path.read_bytes())}
    return result


def validate_result(value, files, selection, archive_hash, images):
    require(value["schema"] == 1 and value["scope"] == "submitted_source_facts"
            and value["workflow"] == "verified_bytes_to_source_facts_v1", "Unexpected source workflow")
    require(value["configuration_membership"] == value["configuration_completeness"] == "unverified"
            and value["xml_profile"] == "handwritten_common_module_properties_v1", "Scope was strengthened")
    require(value["input_sha256"] == archive_hash and value["images"] == images, "Accepted image/input pins differ")
    kernel = value["kernel"]
    require(kernel["receiver_binding"] == kernel["runtime_relation"] == "unknown", "Relation was strengthened")
    require(kernel["assurance"] == "source_facts_host_asserted_no_binding_no_runtime", "Unexpected assurance")
    facts = kernel["observations"]
    require(facts["selector"]["state"] == facts["export"]["state"] == facts["server"]["state"] == "observed", "Expected observation is unavailable")
    require(facts["selector"]["value"] == "qualified_selector", "Unexpected selector observation")
    require(facts["export"]["value"] is True and facts["server"]["value"] is False, "Explicit Boolean facts differ")
    require(value["admission"] == {"caller": {"state": "admitted"}, "candidate": {"state": "admitted"}}, "Unexpected BSL admission")
    require(value["locations"]["selector"]["selector_span"] == selection, "Selector span differs")
    require(value["locations"]["export"]["export"] is True, "Export span not observed")
    for role, relative in (("caller", CALLER), ("candidate", CANDIDATE), ("metadata", METADATA)):
        reference = value["references"][role]
        require(reference["relative_path"] == relative and reference["raw_sha256"] == sha(files[relative])
                and reference["size_bytes"] == len(files[relative]), "Reference not bound to owned raw bytes")
    encoded = json.dumps(value)
    require("SYNTH_" not in encoded, "Source text escaped into the report")


def validate_success(value, raw, output):
    check_disclosure(value, raw, output)
    require(set(value) == {"result", "request_id"}, "Success disclosed another payload")
    require(str(UUID(value["request_id"])) == value["request_id"], "Invalid success request ID")
    require(len(raw) <= 65_537 and raw.endswith(b"\n") and raw.count(b"\n") == 1, "Unexpected success framing")


def validate_error(value, raw, output):
    check_disclosure(value, raw, output)
    require(set(value) == {"error"}, "Rejection disclosed another payload")
    error = value["error"]
    require(set(error) == {"code", "message", "request_id", "details"}, "Unexpected error fields")
    require(error["code"] == "SOURCE_FACTS_INPUT_REJECTED"
            and error["message"] == "Submitted source facts could not be completed"
            and error["details"] == {}, "Rejection was not fixed and non-echoing")
    require(str(UUID(error["request_id"])) == error["request_id"], "Invalid rejection request ID")
    require(raw.endswith(b"\n") and raw.count(b"\n") == 1, "Unexpected rejection framing")


def verify(args):
    require(sys.platform == "linux", "This smoke is Linux-only")
    # Check supplied immutable artifact bytes before creating anything or starting
    # a process. Hashes are required inputs, never learned from arbitrary images.
    artifacts = {"wheel": pinned_bytes(args.wheel, args.wheel_sha256)}
    images = {role: getattr(args, role + "_sha256") for role in ROLES}
    artifacts.update({role: pinned_bytes(getattr(args, role), images[role]) for role in ROLES})
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    output.chmod(0o700)
    for name in ("commands", "artifacts", "home", "tmp", "work"):
        (output / name).mkdir(mode=0o700)
    wheel = output / "artifacts" / args.wheel.name
    wheel.write_bytes(artifacts.pop("wheel"))
    image_paths = {}
    for role, raw in artifacts.items():
        path = output / "artifacts" / role
        path.write_bytes(raw)
        path.chmod(0o700)
        image_paths[role] = path
    workspace = output / "work"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(output / "home"), "TMPDIR": str(output / "tmp"),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PIP_CONFIG_FILE": "/dev/null",
           "PIP_DISABLE_PIP_VERSION_CHECK": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    receipt = {"schema": 1, "scope": SCOPE, "status": "running", "version": args.expected_version,
               "verifier_sha256": sha(Path(__file__).read_bytes()), "wheel_sha256": args.wheel_sha256,
               "images": images, "checks": [], "designer_acceptance": False,
               "native_runtime_exercised": False, "accuracy_acceptance": False}

    def command(label, argv, *, timeout=30, expected=0, json_output=True):
        record, stdout, stderr = run(argv, output, label, cwd=workspace, env=env, timeout=timeout)
        receipt["checks"].append({"label": label, "exit_code": record["exit_code"],
                                  "evidence": "commands/" + label + "/command.json"})
        require(record["exit_code"] == expected, "Unexpected exit status: " + label)
        require(not stderr, "Unexpected stderr: " + label)
        return (parse_json(stdout), stdout) if json_output else (None, stdout)

    verify_proc_namespace()
    require(empty_children(), "Preexisting children: refusing cleanup authority")
    libc = ctypes.CDLL(None, use_errno=True)
    require(libc.prctl(36, 1, 0, 0, 0) == 0, "Could not establish isolated subreaper")
    try:
        environment = output / "environment"
        command("01-create-venv", [sys.executable, "-I", "-m", "venv", str(environment)], timeout=60, json_output=False)
        python = environment / "bin/python"
        command("02-install-wheel", [python, "-I", "-m", "pip", "--isolated", "install", "--no-index",
                                     "--no-deps", "--no-cache-dir", "--only-binary=:all:", wheel], timeout=60, json_output=False)
        probe = ('import importlib.metadata,json,rentgen_core,sys;from pathlib import Path;'
                 'print(json.dumps({"version":importlib.metadata.version("rentgen-core"),'
                 '"installed":Path(rentgen_core.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()),'
                 '"isolated":sys.flags.isolated,"module":str(Path(rentgen_core.__file__).resolve()),'
                 '"prefix":str(Path(sys.prefix).resolve())}))')
        identity, _ = command("03-installed-identity", [python, "-I", "-B", "-c", probe], timeout=15)
        require(identity["version"] == args.expected_version and identity["installed"] is True
                and identity["isolated"] == 1 and identity["prefix"] == str(environment), "Wrong installed Core")
        receipt["installed_identity"] = identity

        def cli(label, *argv, expected=0, timeout=30):
            return command(label, [python, "-I", "-B", "-m", "rentgen_core", *argv], expected=expected, timeout=timeout)

        profile, registry = workspace / "private/identity.json", workspace / "registry.sqlite3"
        source, state = workspace / "source", workspace / "state"
        source.mkdir()
        (source / "untouched.bsl").write_bytes(b"Unchanged();\n")
        cli("04-identity-init", "identity-init", "--identity-profile", profile)
        common = ["--registry", registry, "--identity-profile", profile]
        cli("05-registry-init", "registry-init", *common)
        registered, _ = cli("06-project-register", "project-register", *common, "--source-root", source,
                            "--state-root", state, "--name", "Owned handwritten delivery mechanics")
        project = registered["result"]["project_id"]
        head, _ = cli("07-head-before", "project-head", *common, "--project", project)
        require(head["result"]["snapshot"] is None, "New project already has a snapshot")
        archive = workspace / "SYNTH_OWNED_HANDWRITTEN.zip"
        files, selection = owned_archive(archive)
        archive_hash = sha(archive.read_bytes())
        receipt["archive_sha256"] = archive_hash
        # Include the whole private workspace, including new root residue or
        # registry SQLite sidecars. Command streams live outside this tree.
        tracked = {"work": workspace}
        before = fingerprint(tracked)
        save_json(output / "before.json", before)
        argv = ["source-facts", *common, "--project", project, "--archive", archive,
                "--archive-sha256", archive_hash, "--caller-entry", CALLER, "--candidate-entry", CANDIDATE,
                "--selector-start", str(selection["start"]), "--selector-end", str(selection["end"])]
        for role in ROLES:
            flag = role.replace("_", "-")
            argv += ["--" + flag, image_paths[role], "--" + flag + "-sha256", images[role]]
        report, raw = cli("08-source-facts", *argv, timeout=70)
        validate_success(report, raw, output)
        validate_result(report["result"], files, selection, archive_hash, images)
        require(fingerprint(tracked) == before, "Successful source-facts changed source/state")
        repeated, raw = cli("09-source-facts-repeat", *argv, timeout=70)
        validate_success(repeated, raw, output)
        require(repeated["result"] == report["result"], "Source-fact result is nondeterministic")
        require(fingerprint(tracked) == before, "Repeated source-facts changed source/state")
        bad_argv = list(argv)
        bad_argv[bad_argv.index("--archive-sha256") + 1] = "0" * 64
        require(archive_hash != "0" * 64, "Negative hash unexpectedly matches")
        rejected, raw = cli("10-wrong-archive-hash", *bad_argv, expected=2, timeout=70)
        validate_error(rejected, raw, output)
        require(fingerprint(tracked) == before, "Rejected source-facts changed source/state")
        after_head, _ = cli("11-head-after", "project-head", *common, "--project", project)
        require(after_head["result"] == head["result"], "Project head changed")
        after = fingerprint(tracked)
        save_json(output / "after.json", after)
        require(after == before, "Final source/state fingerprint differs")
        receipt.update(status="passed", deterministic_result=True, fixed_non_echo_rejection=True,
                       source_and_state_unchanged=True, project_head_unchanged=True,
                       observations=report["result"]["kernel"]["observations"],
                       receiver_binding="unknown", runtime_relation="unknown")
    except BaseException as error:
        receipt.update(status="failed", failure_type=type(error).__name__)
        raise
    finally:
        try:
            adopted = cleanup_adopted()
            require(not adopted, "Final safety cleanup was required")
            receipt["owned_children_reaped"] = empty_children()
        except BaseException:
            receipt.update(status="failed", owned_children_reaped=False)
            raise
        finally:
            save_json(output / "receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=True, indent=2))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--wheel-sha256", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    for role in ROLES:
        flag = role.replace("_", "-")
        parser.add_argument("--" + flag, required=True, type=Path)
        parser.add_argument("--" + flag + "-sha256", required=True)
    args = parser.parse_args()

    def interrupt_once(*_):
        # A repeated Ctrl-C must not interrupt exact-child termination/reap.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGINT, interrupt_once)
    try:
        verify(args)
    finally:
        signal.signal(signal.SIGINT, previous)


if __name__ == "__main__":
    main()
