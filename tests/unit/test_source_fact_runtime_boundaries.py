"""Public, isolated Linux source-fact acceptance adapters.

Real-pipeline cases use pinned input-core, Go and Rust builds. Native fault probe
cases qualify transport only. No withheld fixture, label, customer file, live
profile, native 1C, or external endpoint is accessed. Compile the probe separately
only after review; this module never compiles software during collection.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time
from uuid import UUID
import zipfile

import pytest

from rentgen_core import cli, source_fact_cli, source_fact_process as process
from rentgen_core import submitted_source_facts as workflow
from rentgen_core.errors import CoreError
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import current_local_principal
from rentgen_core.rust_input import RustInputSession
from test_portable_local_workflow import portable_project, ROOT
from test_source_fact_host import scan_fixture, validate_fixture, source_argv

SUPPORT = Path(__file__).resolve().parents[1] / "fixtures/source_facts"
sys.path.insert(0, str(SUPPORT))
from boundary_supervisor import checked_pins, close_streams, stop_owned, signal_owned

MESSAGE = "Submitted source facts could not be completed"


@pytest.fixture(scope="session", autouse=True)
def qualification_preflight():
    assert sys.platform == "linux", "Required Linux qualification unavailable"
    assert Path(cli.__file__).resolve().parent == ROOT / "rentgen_core", "Wrong imported candidate"
    supervisor = os.environ.get("RENTGEN_SOURCE_SUPERVISOR_PID")
    assert supervisor == str(os.getppid()), "Use the reviewed qualification supervisor"
    assert os.getpgrp() == os.getpid(), "Qualification session anchor is missing"
    path = os.environ.get("RENTGEN_SOURCE_TEST_PINS")
    expected = os.environ.get("RENTGEN_SOURCE_TEST_PINS_SHA256")
    assert path and expected, "Missing independently reviewed build pins"
    return checked_pins(Path(path), expected, ROOT)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def images(tmp_path_factory, qualification_preflight):
    folder = tmp_path_factory.mktemp("source-fact-images")
    result = {}
    for role, item in qualification_preflight["images"].items():
        assert digest(item["path"]) == item["sha256"]
        path = folder / role
        shutil.copyfile(item["path"], path); path.chmod(0o700)
        assert digest(path) == item["sha256"], "Copied image changed"
        result[role] = path
        result[role + "_sha256"] = item["sha256"]
    return result


@pytest.fixture(scope="module")
def probe(tmp_path_factory, qualification_preflight):
    item = qualification_preflight["probe"]
    assert digest(item["path"]) == item["sha256"]
    path = tmp_path_factory.mktemp("source-fact-probe") / "owned-probe"
    shutil.copyfile(item["path"], path); path.chmod(0o700)
    assert digest(path) == item["sha256"]
    return path, item["sha256"]


class LaunchAudit:
    """Assert production reap first; always run independent safety cleanup later."""
    def __init__(self, request, monkeypatch, *, probe_role=None, probe_mode=None):
        self.children, self.waits, self.events, self.launches = [], [], [], []
        request.addfinalizer(self.close)
        real = subprocess.Popen
        def launch(argv, **kwargs):
            assert argv[1:2] == ["--parent-pid"]
            assert argv[2] == str(os.getpid())
            assert argv[0].startswith("/proc/self/fd/")
            assert kwargs["shell"] is False and kwargs["close_fds"] is True
            assert kwargs["pass_fds"] == (int(argv[0].rsplit("/", 1)[1]),)
            assert set(kwargs["env"]) <= {"LANG", "LC_ALL", "RUST_BACKTRACE", "GOMAXPROCS"}
            assert all("SYNTH" not in value for value in argv)
            self.launches.append((list(argv), copy.deepcopy(kwargs["env"])))
            reader = writer = child = None
            try:
                if probe_mode is not None:
                    reader, writer = os.pipe()
                    self.events.append(reader)
                    os.set_blocking(reader, False)
                    argv = [*argv, "--probe", probe_role, probe_mode, str(writer)]
                    kwargs["pass_fds"] += (writer,)
                child = real(argv, **kwargs)
                self.children.append(child)
            finally:
                try:
                    if writer is not None: os.close(writer)
                finally:
                    if child is None and reader is not None:
                        self.events.remove(reader)
                        os.close(reader)
            wait = child.wait
            def confirmed_wait(*args, **kw):
                status = wait(*args, **kw)
                self.waits.append((child.pid, status))
                return status
            child.wait = confirmed_wait
            return child
        monkeypatch.setattr(subprocess, "Popen", launch)

    def close(self):
        errors = []; deadline = time.monotonic() + 2
        for child in self.children:
            try:
                errors.extend(stop_owned(child, deadline))
            except BaseException as error:
                errors.append(type(error).__name__)
        while self.events:
            fd = self.events.pop()
            try: os.close(fd)
            except OSError as error: errors.append(type(error).__name__)
        if errors:
            pytest.fail("Independent safety cleanup unconfirmed: " + repr(errors))

    def trace(self):
        chunks = []
        while self.events:
            fd = self.events.pop()
            try:
                while True:
                    try: value = os.read(fd, 4096)
                    except BlockingIOError: break
                    if not value: break
                    chunks.append(value)
            finally:
                os.close(fd)
        return b"".join(chunks)

    def reaped(self):
        # These assertions precede the fixture's independent safety finalizer.
        for child in self.children:
            assert child.returncode is not None
            assert any(pid == child.pid for pid, _ in self.waits)
            assert all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr))
            with pytest.raises(ChildProcessError):
                os.waitpid(child.pid, os.WNOHANG)


def own_command(request, argv, **kwargs):
    owned = []
    def close():
        errors = []
        for child in owned:
            errors.extend(stop_owned(child, time.monotonic() + 2))
        if errors: pytest.fail("Independent command cleanup unconfirmed: " + repr(errors))
    request.addfinalizer(close)
    child = subprocess.Popen(argv, **kwargs)
    owned.append(child)
    return child


def collect_output(child, seconds, cap=131072):
    """Simultaneous bounded stdout/stderr drain and exact direct-child wait."""
    output = {"stdout": bytearray(), "stderr": bytearray()}
    end = time.monotonic() + seconds
    with selectors.DefaultSelector() as selector:
        for name in output:
            stream = getattr(child, name)
            if stream is not None and not stream.closed:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
        while selector.get_map():
            left = end - time.monotonic()
            if left <= 0: raise TimeoutError("Test process pipe deadline")
            for key, _ in selector.select(min(.1, left)):
                try: value = os.read(key.fileobj.fileno(), 8192)
                except BlockingIOError: continue
                if not value: selector.unregister(key.fileobj); continue
                output[key.data].extend(value)
                if len(output[key.data]) > cap: raise ValueError("Test process output cap")
    child.wait(timeout=max(.001, end - time.monotonic()))
    return bytes(output["stdout"]), bytes(output["stderr"])


def exchange(probe, role, *, authorize=lambda: None, cancelled=None, deadline=None):
    return process.run_owned_helper(*probe, role=role, request=b'{"SYNTH_REQUEST":true}',
                                    authorize=authorize, cancelled=cancelled,
                                    deadline=time.monotonic() + 18 if deadline is None else deadline)


@pytest.mark.parametrize("role", ["scanner", "kernel"])
@pytest.mark.parametrize("mode", ["normal", "hello_limit", "stderr_limit", "response_limit"])
def test_probe_complete_exchange_inclusive_limits_reaps(request, probe, monkeypatch, role, mode):
    audit = LaunchAudit(request, monkeypatch, probe_role=role, probe_mode=mode)
    result = exchange(probe, role)
    assert result == (b"X" * 65536 if mode == "response_limit" else b'{"probe":true}')
    audit.reaped()
    assert audit.trace() == b"SHIERX"


FAULTS = [
    ("hello_oversize", "OUTPUT_LIMIT"), ("hello_protocol", "HANDSHAKE_INVALID"),
    ("hello_ownership", "HANDSHAKE_INVALID"), ("hello_shape", "HANDSHAKE_INVALID"),
    ("hello_duplicate", "HANDSHAKE_INVALID"), ("hello_delay", "TIMEOUT"),
    ("response_oversize", "OUTPUT_LIMIT"), ("stderr_over", "OUTPUT_LIMIT"),
    ("trailing", "PROTOCOL_INVALID"), ("nonzero", "CHILD_FAILED"),
    ("partial", "CHILD_FAILED"), ("empty", "CHILD_FAILED"),
    ("stdout_open", "TIMEOUT"), ("stderr_open", "TIMEOUT"),
    ("unexited", "TIMEOUT"), ("exchange_delay", "TIMEOUT"),
]


@pytest.mark.parametrize("role", ["scanner", "kernel"])
@pytest.mark.parametrize("mode,code", FAULTS)
def test_probe_faults_never_release_response(request, probe, monkeypatch, role, mode, code):
    # Per-variant admitted complete-exchange control precedes fault injection.
    with monkeypatch.context() as control_patch:
        control = LaunchAudit(request, control_patch, probe_role=role, probe_mode="normal")
        assert exchange(probe, role) == b'{"probe":true}'
        control.reaped(); assert control.trace() == b"SHIERX"
    audit = LaunchAudit(request, monkeypatch, probe_role=role, probe_mode=mode)
    began = time.monotonic()
    with pytest.raises(CoreError) as error:
        exchange(probe, role)
    elapsed = time.monotonic() - began
    assert error.value.code == "SOURCE_FACTS_" + code
    assert str(error.value) == MESSAGE and error.value.details == {}
    audit.reaped()
    events = audit.trace()
    if mode.startswith("hello_"):
        assert b"I" not in events, "Source bytes were sent before an exact hello"
        assert elapsed < 7.5
        if mode == "hello_delay": assert elapsed >= 4.5
    else:
        assert b"E" in events, "The fault probe must actually observe stdin EOF"
        assert elapsed < (12.5 if role == "scanner" else 7.5)
        if code == "TIMEOUT": assert elapsed >= (9.5 if role == "scanner" else 4.5)


@pytest.mark.parametrize("role", ["scanner", "kernel"])
@pytest.mark.parametrize("action", ["cancel", "revoke"])
def test_wait_cancellation_acl_and_bounded_polling(request, probe, portable_project, monkeypatch, role, action):
    ctx = project_context(portable_project)
    audit = LaunchAudit(request, monkeypatch, probe_role=role, probe_mode="exchange_delay")
    selects = []
    real_select = selectors.EpollSelector.select
    def observed_select(self, timeout=None):
        selects.append(timeout)
        return real_select(self, timeout)
    monkeypatch.setattr(selectors.EpollSelector, "select", observed_select)
    stop = [False]
    calls = []
    def authorize():
        calls.append(time.monotonic())
        if audit.children and len(calls) > 2 and not stop[0]:
            # Wait for the probe to be blocked after it has consumed request EOF.
            fd = audit.events[0]
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                chunk = b""
            consumed.extend(chunk)
            if b"E" in consumed:
                stop[0] = True
                if action == "revoke":
                    revoke(ctx)
        workflow.authorize(ctx)
    consumed = bytearray()
    began = time.monotonic()
    with pytest.raises(CoreError) as error:
        exchange(probe, role, authorize=authorize, cancelled=lambda: stop[0] and action == "cancel")
    assert error.value.code == "SOURCE_FACTS_" + ("CANCELLED" if action == "cancel" else "PERMISSION_DENIED")
    assert stop[0] and time.monotonic() - began < 2
    assert selects and all(0 <= value <= 0.1 for value in selects)
    audit.reaped(); audit.trace()


def test_cleanup_failure_overrides_complete_response(request, probe, monkeypatch):
    audit = LaunchAudit(request, monkeypatch, probe_role="scanner", probe_mode="normal")
    real = process._cleanup
    def unconfirmed(*args, **kwargs):
        real(*args, **kwargs)  # Keep this harness safe and actually reap.
        raise process.failure("CLEANUP_UNCONFIRMED")
    monkeypatch.setattr(process, "_cleanup", unconfirmed)
    with pytest.raises(CoreError) as error:
        exchange(probe, "scanner")
    assert error.value.code == "SOURCE_FACTS_CLEANUP_UNCONFIRMED"
    audit.reaped(); audit.trace()


def project_context(project):
    profile, registry, project_id, _, _ = project
    principal = current_local_principal(identity_profile=profile)
    return LocalRuntime(registry).state_context(principal, project_id)


def revoke(ctx):
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        tx._connection.execute("DELETE FROM membership_permissions WHERE permission='analysis:run'")


def archive_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_STORED) as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return output.getvalue()


@pytest.fixture
def source_case(tmp_path):
    method = b"SYNTH_Method"
    caller = (b'Procedure Run()\n// SYNTH_COMMENT_CANARY\nX = "SYNTH_LITERAL_CANARY";\n'
              b'Candidate.' + method + b'();\nEndProcedure\n')
    candidate = b'Procedure ' + method + b'() Export\nEndProcedure\n'
    files = {
        "CommonModules/SYNTH_Caller/Ext/Module.bsl": caller,
        "CommonModules/Candidate/Ext/Module.bsl": candidate,
        "CommonModules/Candidate.xml": b'<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses"><CommonModule><Properties><Name>Candidate</Name><Server>false</Server></Properties></CommonModule></MetaDataObject>',
        "SYNTH_UNRELATED.bin": b"SYNTH_UNRELATED_CONTENT",
        "Configuration.xml": b"SYNTH_ROOT_METADATA_NOT_READ",
    }
    archive = tmp_path / "SYNTH_ABSOLUTE_ARCHIVE.zip"
    archive.write_bytes(archive_bytes(files))
    start = caller.index(b"Candidate." + method)
    return {"archive": archive, "archive_sha256": digest(archive),
            "caller_entry": next(iter(files)), "candidate_entry": "CommonModules/Candidate/Ext/Module.bsl",
            "selector_start": start, "selector_end": start + len(b"Candidate." + method)}, files


def argv(project, images, case):
    _, _, project_id, _, common = project
    result = ["source-facts", *map(str, common), "--project", project_id]
    for key, value in {**images, **case}.items():
        result += ["--" + key.replace("_", "-"), str(value)]
    return result


def fixed_error(output, code):
    assert not output.err
    value = json.loads(output.out)
    assert set(value) == {"error"}
    error = value["error"]
    assert set(error) == {"code", "message", "request_id", "details"}
    assert error["code"] == "SOURCE_FACTS_" + code
    assert error["message"] == MESSAGE and error["details"] == {}
    assert str(UUID(error["request_id"])) == error["request_id"]
    assert output.out.endswith("\n") and output.out.count("\n") == 1
    assert "SYNTH" not in output.out


@pytest.mark.parametrize("alias", [False, True])
def test_real_pipeline_read_once_no_unrelated_disclosure_or_persistence(request, images, source_case, portable_project, monkeypatch, alias):
    case, files = source_case
    if alias:
        path = case["candidate_entry"]
        combined = files[case["caller_entry"]] + files[path]
        files[path] = combined
        case["caller_entry"] = path
        case["archive"].write_bytes(archive_bytes(files)); case["archive_sha256"] = digest(case["archive"])
    root = portable_project[1].parent
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    # Input-core hashes the whole bounded ZIP. Count host semantic requests only.
    reads = []
    real_read = RustInputSession.read_entry
    def read(session, entry):
        reads.append(entry["path"])
        return real_read(session, entry)
    monkeypatch.setattr(RustInputSession, "read_entry", read)
    audit = LaunchAudit(request, monkeypatch)
    result = workflow.source_facts(project_context(portable_project), **images, **case)
    audit.reaped()
    assert len(audit.children) == 3 and all(p.returncode == 0 for p in audit.children)
    expected = {case["caller_entry"], case["candidate_entry"], "CommonModules/Candidate.xml"}
    assert set(reads) == expected and len(reads) == len(expected)
    assert result["kernel"]["receiver_binding"] == result["kernel"]["runtime_relation"] == "unknown"
    assert result["kernel"]["observations"]["selector"]["state"] == "observed"
    assert result["kernel"]["observations"]["export"]["value"] is True
    assert result["kernel"]["observations"]["server"]["value"] is False
    encoded = json.dumps(result)
    for secret in ("SYNTH_Method", "SYNTH_LITERAL", "SYNTH_COMMENT", "SYNTH_UNRELATED", "SYNTH_ROOT", str(root)):
        assert secret not in encoded
    without_refs = copy.deepcopy(result); del without_refs["references"]
    assert "SYNTH_Caller" not in json.dumps(without_refs)
    assert result["references"]["caller"]["relative_path"] == case["caller_entry"]
    for reference in result["references"].values():
        raw = files[reference["relative_path"]]
        assert reference["raw_sha256"] == hashlib.sha256(raw).hexdigest()
        assert reference["size_bytes"] == len(raw)
    # This is post-run residue/source preservation evidence, not syscall auditing.
    after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert after == before


def test_real_pipeline_archive_replacement_keeps_accepted_bytes(request, images, source_case, portable_project, monkeypatch):
    case, files = source_case
    original = RustInputSession.open_import
    replaced = []
    def opened(session, path, expected):
        result = original(session, path, expected)
        replacement = path.with_suffix(".replacement")
        replacement.write_bytes(archive_bytes({"SYNTH_REPLACEMENT": b"wrong"}))
        os.replace(replacement, path); replaced.append(True)
        return result
    monkeypatch.setattr(RustInputSession, "open_import", opened)
    audit = LaunchAudit(request, monkeypatch)
    result = workflow.source_facts(project_context(portable_project), **images, **case)
    assert replaced and digest(case["archive"]) != case["archive_sha256"]
    assert result["input_sha256"] == case["archive_sha256"]
    assert result["references"]["caller"]["raw_sha256"] == hashlib.sha256(files[case["caller_entry"]]).hexdigest()
    audit.reaped()


@pytest.mark.parametrize("role", ["scanner", "kernel"])
def test_real_helper_executes_sealed_image_after_locator_replacement(request, images, source_case, portable_project, monkeypatch, tmp_path, role):
    key = "source_" + role
    options = dict(images)
    options[key] = tmp_path / ("SYNTH_REPLACED_" + role)
    shutil.copyfile(images[key], options[key]); options[key].chmod(0o700)
    original = process._executable
    replaced = []
    def sealed(path, expected, stack, **kwargs):
        fd = original(path, expected, stack, **kwargs)
        if path == options[key]:
            replacement = path.with_suffix(".new")
            replacement.write_bytes(b"SYNTH_INVALID_REPLACEMENT"); replacement.chmod(0o700)
            os.replace(replacement, path); replaced.append(True)
        return fd
    monkeypatch.setattr(process, "_executable", sealed)
    audit = LaunchAudit(request, monkeypatch)
    result = workflow.source_facts(project_context(portable_project), **options, **source_case[0])
    assert replaced and result["images"][key] == options[key + "_sha256"]
    assert digest(options[key]) != options[key + "_sha256"]
    audit.reaped()


PHASES = ["before_input_read", "before_scanner_launch", "after_source_read",
          "after_scan_parse", "after_xml_parse", "after_kernel_evaluation"]


@pytest.mark.parametrize("phase", PHASES)
@pytest.mark.parametrize("action", ["cancel", "revoke"])
def test_real_pipeline_phase_cancellation_or_actual_acl_revocation(request, images, source_case, portable_project, monkeypatch, phase, action):
    ctx = project_context(portable_project)
    stopped = []
    def trigger():
        if not stopped:
            stopped.append(True)
            if action == "revoke": revoke(ctx)
    if phase == "before_input_read":
        target, name, before = RustInputSession, "open_import", True
    elif phase == "before_scanner_launch":
        target, name, before = workflow, "run_owned_helper", True
    else:
        target, name, before = {
            "after_source_read": (RustInputSession, "read_entry", False),
            "after_scan_parse": (workflow, "validate_scan", False),
            "after_xml_parse": (workflow, "xml_observations", False),
            "after_kernel_evaluation": (workflow, "validate_kernel", False),
        }[phase]
    original = getattr(target, name)
    def wrapped(*args, **kwargs):
        if before: trigger()
        result = original(*args, **kwargs)
        if not before: trigger()
        return result
    monkeypatch.setattr(target, name, wrapped)
    audit = LaunchAudit(request, monkeypatch)
    with pytest.raises(CoreError) as error:
        workflow.source_facts(ctx, **images, **source_case[0], cancelled=lambda: bool(stopped) and action == "cancel")
    assert stopped
    assert error.value.code == "SOURCE_FACTS_" + ("CANCELLED" if action == "cancel" else "PERMISSION_DENIED")
    assert str(error.value) == MESSAGE
    audit.reaped()


@pytest.mark.parametrize("action", ["cancel", "revoke", "exception"])
def test_real_final_serialization_replaces_result(request, images, source_case, portable_project, monkeypatch, capsys, action):
    ctx = project_context(portable_project)
    original = json.dumps
    completed = []
    real_authorize = workflow.authorize
    def current_authorize(current):
        if completed and action == "exception":
            raise OSError("SYNTH_FINAL_EXCEPTION")
        return real_authorize(current)
    monkeypatch.setattr(workflow, "authorize", current_authorize)
    def serialize(value, *args, **kwargs):
        encoded = original(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value and value["result"].get("scope") == "submitted_source_facts":
            completed.append(True)
            if action == "revoke": revoke(ctx)
            elif action == "cancel": signal.raise_signal(signal.SIGINT)
        return encoded
    monkeypatch.setattr(json, "dumps", serialize)
    audit = LaunchAudit(request, monkeypatch)
    assert cli.main(argv(portable_project, images, source_case[0])) == 2
    fixed_error(capsys.readouterr(), {"cancel": "CANCELLED", "revoke": "PERMISSION_DENIED", "exception": "ACCESS_UNAVAILABLE"}[action])
    assert completed
    audit.reaped()


@pytest.mark.parametrize("change", ["unknown", "repeat", "missing", "signed", "space", "exponent", "leading_zero", "placement", "abbreviated"])
def test_closed_cli_argument_variants(request, tmp_path, capsys, change):
    args = source_argv(tmp_path)
    if change == "unknown": args += ["--SYNTH_UNKNOWN", "SYNTH_VALUE"]
    elif change == "repeat": args += ["--caller-entry", "SYNTH_REPEAT"]
    elif change == "missing": args = args[:-1]
    elif change == "placement": args = ["SYNTH_WRONG_PLACEMENT", *args]
    elif change == "abbreviated": args[args.index("--archive")] = "--arch"
    else:
        args[-1] = {"signed": "+1", "space": " 1", "exponent": "1e0", "leading_zero": "01"}[change]
    assert cli.main(args) == 2
    fixed_error(capsys.readouterr(), "INVALID_ARGUMENT")


@pytest.mark.parametrize("phase", ["identity", "registry", "entry", "input", "image", "launch", "internal"])
def test_closed_cli_runtime_failures(request, images, source_case, portable_project, monkeypatch, capsys, phase, tmp_path):
    audit = LaunchAudit(request, monkeypatch)
    case = dict(source_case[0]); options = dict(images)
    args = argv(portable_project, options, case)
    if phase == "identity": args[args.index("--identity-profile") + 1] = str(tmp_path / "SYNTH_IDENTITY")
    elif phase == "registry": args[args.index("--registry") + 1] = str(tmp_path / "SYNTH_REGISTRY")
    elif phase == "entry": args[args.index("--caller-entry") + 1] = "SYNTH_MISSING.bsl"
    elif phase == "input": args[args.index("--archive-sha256") + 1] = "0" * 64
    elif phase == "image": args[args.index("--source-scanner-sha256") + 1] = "0" * 64
    elif phase == "launch":
        real_launch = subprocess.Popen
        def failed(*args, **kwargs):
            if "GOMAXPROCS" in kwargs.get("env", {}):
                raise OSError("SYNTH_LAUNCH_EXCEPTION")
            return real_launch(*args, **kwargs)
        monkeypatch.setattr(process.subprocess, "Popen", failed)
    else:
        def failed(*args, **kwargs): raise RuntimeError("SYNTH_INTERNAL_EXCEPTION")
        monkeypatch.setattr(workflow, "validate_scan", failed)
    assert cli.main(args) == 2
    fixed_error(capsys.readouterr(), {"identity": "ACCESS_UNAVAILABLE", "registry": "ACCESS_UNAVAILABLE", "entry": "ENTRY_NOT_FOUND", "input": "INPUT_REJECTED", "image": "EXECUTABLE_INVALID", "launch": "LAUNCH_FAILED", "internal": "INTERNAL_ERROR"}[phase])
    audit.reaped()


@pytest.mark.parametrize("value", [0, 1])
def test_host_export_does_not_coerce_numeric_boolean(request, value):
    control = scan_fixture()
    admitted, receiver = validate_fixture(copy.deepcopy(control))
    assert admitted == control[4] and receiver == "Candidate"
    fixture = copy.deepcopy(control)
    fixture[4]["header"]["export"] = value
    with pytest.raises(CoreError) as error: validate_fixture(fixture)
    assert error.value.code in {"SOURCE_FACTS_PROTOCOL_INVALID", "SOURCE_FACTS_RECEIPT_INVALID"}


@pytest.mark.parametrize("mutation", ["caller_size", "candidate_size", "candidate_hash", "selector_extent", "receiver_span", "method_span", "header_outside", "export_false_span", "candidate_unadmitted", "candidate_reason"])
def test_host_rejects_forged_scan_evidence(request, mutation):
    control = scan_fixture()
    admitted, receiver = validate_fixture(copy.deepcopy(control))
    assert admitted == control[4] and receiver == "Candidate"
    fixture = copy.deepcopy(control); response = fixture[4]
    if mutation == "caller_size": response["caller"]["size_bytes"] += 1
    elif mutation == "candidate_size": response["candidate"]["size_bytes"] += 1
    elif mutation == "candidate_hash": response["candidate"]["raw_sha256"] = "0" * 64
    elif mutation == "selector_extent": response["selector"]["selector_span"]["end"] -= 1
    elif mutation == "receiver_span": response["selector"]["receiver_span"]["end"] -= 1
    elif mutation == "method_span": response["selector"]["method_span"]["start"] += 1
    elif mutation == "header_outside": response["header"]["routine_span"]["end"] -= 15
    elif mutation == "export_false_span": response["header"]["export"] = False
    elif mutation == "candidate_unadmitted": response["candidate"]["admission"] = {"state": "unavailable", "reason": "invalid_header"}
    elif mutation == "candidate_reason": response["header"] = {"state": "unavailable", "reason": "candidate_not_admitted"}
    with pytest.raises(CoreError) as error: validate_fixture(fixture)
    assert error.value.code in {"SOURCE_FACTS_PROTOCOL_INVALID", "SOURCE_FACTS_RECEIPT_INVALID"}


def test_legacy_first_command_keeps_legacy_boundary(request, tmp_path, capsys):
    assert cli.main(["project-head", "--registry", str(tmp_path / "SYNTH_REGISTRY"), "--project", "source-facts", "--identity-profile", str(tmp_path / "SYNTH_PROFILE")]) == 2
    out = capsys.readouterr()
    assert not json.loads(out.out)["error"]["code"].startswith("SOURCE_FACTS_")


@pytest.mark.parametrize("variant", ["success", "argument_error"])
def test_real_broken_stdout_is_quiet(request, images, source_case, portable_project, variant):
    args = argv(portable_project, images, source_case[0]) if variant == "success" else ["source-facts", "--SYNTH_UNKNOWN"]
    child = own_command(request, [sys.executable, "-m", "rentgen_core", *args], cwd=ROOT,
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    child.stdout.close()
    out, err = collect_output(child, 20)
    assert child.returncode == 2 and out == err == b""


@pytest.mark.parametrize("size", [65536, 65537])
def test_exact_serialized_budget_does_not_truncate(request, tmp_path, portable_project, monkeypatch, capsys, size):
    ctx = project_context(portable_project)
    empty = {"result": {"payload": ""}, "request_id": "0" * 36}
    overhead = len(json.dumps(empty, separators=(",", ":")).encode())
    def execute(args, proposal_scope):
        proposal_scope.context = ctx
        return cli._ProposalCommandResult({"payload": "x" * (size - overhead)}, ctx, output_limit=65536)
    monkeypatch.setattr(cli, "_execute", execute)
    code = cli.main(source_argv(tmp_path)); output = capsys.readouterr()
    if size == 65536:
        assert code == 0 and not output.err
        assert len(output.out.encode()) == 65537 and output.out.endswith("\n")
        assert len(json.loads(output.out)["result"]["payload"]) == size - overhead
    else:
        assert code == 2
        fixed_error(output, "OUTPUT_LIMIT")


@pytest.mark.parametrize("action", ["cancel", "revoke", "exception"])
def test_error_boundary_final_authority_replaces_private_error(request, tmp_path, portable_project, monkeypatch, capsys, action):
    ctx = project_context(portable_project)
    triggered = []
    real_authorize = workflow.authorize
    def authorize(current):
        if triggered and action == "exception": raise OSError("SYNTH_ACCESS_EXCEPTION")
        return real_authorize(current)
    def execute(args, proposal_scope):
        proposal_scope.context = ctx
        triggered.append(True)
        if action == "revoke": revoke(ctx)
        elif action == "cancel": signal.raise_signal(signal.SIGINT)
        raise CoreError("SOURCE_FACTS_PROTOCOL_INVALID", "SYNTH_PRIVATE_ERROR", details={"path": "SYNTH_PRIVATE_PATH"})
    monkeypatch.setattr(workflow, "authorize", authorize)
    monkeypatch.setattr(cli, "_execute", execute)
    assert cli.main(source_argv(tmp_path)) == 2
    fixed_error(capsys.readouterr(), {"cancel": "CANCELLED", "revoke": "PERMISSION_DENIED", "exception": "ACCESS_UNAVAILABLE"}[action])


@pytest.mark.parametrize("role", ["source_scanner", "source_kernel"])
@pytest.mark.parametrize("pid", ["0", "1", "2147483647"])
def test_real_ownership_setup_failure_is_silent(request, images, role, pid):
    child = own_command(request, [str(images[role]), "--parent-pid", pid],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = collect_output(child, 3, 1024)
    assert child.returncode == 2 and out == err == b""


@pytest.mark.parametrize("role,protocol", [("source_scanner", "source_fact_scan_v1"), ("source_kernel", "submitted_source_facts_v1")])
def test_real_after_hello_parent_death_reaps_exact_child_with_stdin_retained(request, images, role, protocol):
    # No nested session/group is created: all descendants remain accounted for
    # by the qualification supervisor, even if this inner driver itself fails.
    driver = own_command(request, [sys.executable, str(SUPPORT / "boundary_supervisor.py"),
                                   "parent-death", str(images[role]), protocol],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = collect_output(driver, 18)
    assert driver.returncode == 0 and not err, (out, err)
    assert json.loads(out) == {"hello": True, "core_limit_zero": True, "retained_stdin": True, "owned_child_reaped": True, "signal": "SIGKILL"}


DOUBLE_INTERRUPT_DRIVER = r'''
import os,signal,subprocess,sys,time
sys.path.insert(0,sys.argv[1])
from boundary_supervisor import subreaper,stop_owned,cleanup_adopted
from rentgen_core import cli,source_fact_process
subreaper()
real=subprocess.Popen
children=[]
event=int(sys.argv[2])
real_signal=signal.signal
def install(sig,handler):
 if sig==signal.SIGINT and callable(handler):
  def observed(*args):
   os.write(event,b"C");return handler(*args)
  return real_signal(sig,observed)
 return real_signal(sig,handler)
signal.signal=install
real_cleanup=source_fact_process._cleanup
def cleanup(*args,**kwargs):
 os.write(event,b"K")
 time.sleep(.2)
 return real_cleanup(*args,**kwargs)
source_fact_process._cleanup=cleanup
def launch(argv,**kwargs):
 if "GOMAXPROCS" in kwargs.get("env",{}):
  argv=[*argv,"--probe","scanner","framed_exchange_delay",str(event)]
  kwargs["pass_fds"]+=(event,)
 child=real(argv,**kwargs);children.append(child);return child
subprocess.Popen=launch
verified=False
try:
 status=cli.main(sys.argv[3:])
 assert status==2
 assert children and all(child.returncode is not None for child in children)
 for child in children:
  try:os.waitpid(child.pid,os.WNOHANG)
  except ChildProcessError:pass
  else:raise AssertionError("Production did not reap owned child")
 verified=True
finally:
 errors=[]
 try:
  end=time.monotonic()+2
  for child in children:
   errors.extend(stop_owned(child,end))
  observed,_,remaining=cleanup_adopted(time.monotonic()+2)
  errors.extend(remaining)
  if verified and observed:errors.append("Unexpected adopted descendant after production reap")
  if errors:raise RuntimeError("Driver cleanup unconfirmed")
  if verified:os.write(event,b"Q")
 finally:os.close(event)
raise SystemExit(status)
'''


def test_actual_double_sigint_during_wait_reaps_and_emits_one_fixed_error(request, images, probe, source_case, portable_project):
    options = dict(images); options["source_scanner"], options["source_scanner_sha256"] = probe
    fds = set(); selectors_owned = []
    def close():
        errors = []
        for selector in selectors_owned:
            try: selector.close()
            except BaseException as error: errors.append(type(error).__name__)
        while fds:
            fd = fds.pop()
            try: os.close(fd)
            except OSError as error: errors.append(type(error).__name__)
        if errors: pytest.fail("Event descriptor cleanup unconfirmed: " + repr(errors))
    request.addfinalizer(close)
    reader, writer = os.pipe(); fds.update((reader, writer))
    os.set_blocking(reader, False)
    child = own_command(request, [sys.executable, "-c", DOUBLE_INTERRUPT_DRIVER, str(SUPPORT), str(writer),
                                  *argv(portable_project, options, source_case[0])],
                        cwd=ROOT, pass_fds=(writer,), stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    os.close(writer); fds.remove(writer)
    selector = selectors.DefaultSelector(); selectors_owned.append(selector)
    selector.register(reader, selectors.EVENT_READ)
    events = bytearray(); eof = False
    def drain_until(marker, seconds):
        nonlocal eof
        end = time.monotonic() + seconds
        while (marker is None or marker not in events) and not eof and time.monotonic() < end:
            for _, _ in selector.select(min(.05, max(0, end - time.monotonic()))):
                try: value = os.read(reader, 4096)
                except BlockingIOError: continue
                if not value: eof = True; break
                events.extend(value)
                assert len(events) <= 4096
        if marker is not None: assert marker in events, "Driver did not reach expected event"
    drain_until(b"E", 8)
    signal_owned(child.pid, signal.SIGINT)
    drain_until(b"K", 2)
    assert b"C" in events
    signal_owned(child.pid, signal.SIGINT)
    out, err = collect_output(child, 6)
    drain_until(None, 1)
    assert eof and child.returncode == 2 and b"Q" in events and events.count(b"C") == 2
    from types import SimpleNamespace
    fixed_error(SimpleNamespace(out=out.decode(), err=err.decode()), "CANCELLED")
