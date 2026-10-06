"""Finite public P completion adapters. Source-only until independently released.

The two native images and production thresholds are unchanged. Controlled faults
qualify lifecycle/disclosure only. Tracing covers an owned synthetic operation;
trusted Linux, loader/runtime files and explicit SQLite sidecars are allowances,
not a sandbox claim. Ptrace/strace denial is a failed/unrun qualification blocker.
"""
import ast
import base64
from contextlib import ExitStack
import copy
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import selectors
import shutil
import signal
import socket
import struct
import subprocess
import sys
import sysconfig
import time
from types import SimpleNamespace

import pytest

from rentgen_core import cli, source_fact_process as process
from rentgen_core import submitted_source_facts as workflow
from rentgen_core.errors import CoreError
from rentgen_core.rust_input import RustInputSession
import test_source_fact_runtime_boundaries as prior
from test_source_fact_runtime_boundaries import (
    images, probe, qualification_preflight, source_case, portable_project,
)
from boundary_supervisor import (
    cleanup_adopted, close_streams, kernel_empty_children, owned_status,
    proc_identity, read_exact, read_to_eof, signal_owned, stop_owned, subreaper,
)

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
ROLES = [("source_scanner", "source_fact_scan_v1"),
         ("source_kernel", "submitted_source_facts_v1")]
MARKER = b"RENTGEN_P_TRACE:"


def record(tmp_path, label, value):
    """Keep measured facts even when a later assertion fails; never claim PASS."""
    (tmp_path / (label + ".json")).write_text(json.dumps(value, indent=2) + "\n")


def driver_argv(mode, *args):
    # This file is fixed and pinned, not an arbitrary command adapter. Imports
    # remain isolated from user site/config and bytecode stays outside the run.
    bootstrap = ("import runpy,sys;root=sys.argv.pop(1);"
                 "sys.path[:0]=[root,root+'/tests/unit'];"
                 "runpy.run_path(sys.argv.pop(1),run_name='__main__')")
    return [sys.executable, "-I", "-B", "-c", bootstrap, str(ROOT), str(HERE), mode, *map(str, args)]


def request_for(role):
    if role == "source_scanner":
        caller = b"Procedure Run()\nCandidate.SYNTH_Method();\nEndProcedure\n"
        candidate = b"Procedure SYNTH_Method() Export\nEndProcedure\n"
        def buffer(i, raw):
            return {"entry_id": i, "size_bytes": len(raw),
                    "raw_sha256": hashlib.sha256(raw).hexdigest(),
                    "data_base64": base64.b64encode(raw).decode()}
        start = caller.index(b"Candidate.SYNTH_Method")
        return {"protocol": "source_fact_scan_v1", "caller": buffer(0, caller),
                "candidate": {"kind": "distinct_entry", "buffer": buffer(1, candidate)},
                "selection": {"start": start, "end": start + len(b"Candidate.SYNTH_Method")}}
    return {"schema_version": 2, "profile": "submitted_source_facts_v1",
            "rule_set": "source_observations_v1",
            "scope": {"case_id": 1, "input_id": 2, "selector_id": 3,
                      "caller_entry_id": 4, "candidate_entry_id": 5, "xml_entry_id": None},
            "observations": {"selector": {"state": "unavailable", "reason": "selector_not_qualified"},
                             "export": {"state": "unavailable", "reason": "selector_unavailable"},
                             "server": {"state": "unavailable", "reason": "selector_unavailable"}},
            "receipts": {"selector": None, "export": None, "server": None},
            "receiver_binding": "unknown", "runtime_relation": "unknown"}


def payload(value):
    return json.dumps(value, separators=(",", ":")).encode()


def frame_read(fd, limit, deadline):
    size = struct.unpack("<I", read_exact(fd, 4, deadline))[0]
    assert 1 <= size <= limit
    return read_exact(fd, size, deadline)


def checked_hello(fd, protocol):
    assert json.loads(frame_read(fd, 512, time.monotonic() + 5)) == {
        "protocol": protocol, "kind": "hello", "ownership": "linux_parent_death_v1"}


def admitted_response(role, raw):
    value = json.loads(raw)
    assert b"SYNTH" not in raw
    if role == "source_scanner":
        assert value["protocol"] == "source_fact_scan_v1" and value["status"] == "ok"
        assert value["caller"]["admission"] == value["candidate"]["admission"] == {"state": "admitted"}
        assert value["selector"]["state"] == "observed"
        assert value["header"]["state"] == "observed" and value["header"]["export"] is True
    else:
        expected = request_for(role); del expected["receipts"]
        expected["assurance"] = "source_facts_host_asserted_no_binding_no_runtime"
        assert value == expected


def ptrace(request, pid=0):
    libc = ctypes.CDLL(None, use_errno=True)
    libc.ptrace.restype = ctypes.c_long
    if libc.ptrace(ctypes.c_uint(request), ctypes.c_uint(pid), ctypes.c_void_p(), ctypes.c_void_p()) == -1:
        raise OSError(ctypes.get_errno(), "Owned pre-hello ptrace gate unavailable")


def exec_gate_owner(binary, expected, channel_fd):
    """TRACEME only in our new child; no attach, security change or EXITKILL."""
    child = channel = None; errors = []; phase = "channel"
    def report_failure(at, error):
        if channel is not None:
            try:
                channel.send(payload({"owner_failure": {"phase": at,
                    "type": type(error).__name__, "errno": getattr(error, "errno", None),
                    "message": str(error)[:512]}}))
            except OSError:
                pass  # Preserve the primary failure if the controller is gone.
    try:
        channel = socket.socket(fileno=int(channel_fd)); channel.settimeout(15)
        def request_trace():
            try:
                ptrace(0)  # PTRACE_TRACEME; no retry or alternate trace operation.
            except OSError as error:
                # Popen normally replaces this errno with a generic preexec_fn
                # SubprocessError and closes its pipes before returning. Preserve
                # the exact attempted operation/errno via our owned control socket.
                report_failure("ptrace_traceme", error)
                raise
            finally:
                os.close(channel.fileno())  # No diagnostic FD reaches the image.
        with ExitStack() as stack:
            phase = "seal_image"
            image = process._executable(Path(binary), expected, stack)
            phase = "spawn_traced_image"
            child = subprocess.Popen([f"/proc/self/fd/{image}", "--parent-pid", str(os.getpid())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                close_fds=True, pass_fds=(image, channel.fileno()), env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GOMAXPROCS": "1"},
                preexec_fn=request_trace)
        phase = "observe_exec_stop"
        end = time.monotonic() + 5
        while time.monotonic() < end:
            status = os.waitid(os.P_PID, child.pid, os.WSTOPPED | os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if status is not None: break
            time.sleep(.005)
        assert status is not None and status.si_code == os.CLD_TRAPPED and status.si_status == signal.SIGTRAP
        found, stopped = os.waitpid(child.pid, os.WUNTRACED)
        assert found == child.pid and os.WIFSTOPPED(stopped) and os.WSTOPSIG(stopped) == signal.SIGTRAP
        phase = "verify_exec_identity"
        identity = proc_identity(f"/proc/{child.pid}/stat")
        assert identity[:2] == (child.pid, os.getpid())
        # The exec has occurred, but no instruction of the new real image ran.
        assert prior.digest(f"/proc/{child.pid}/exe") == expected
        phase = "transfer_exec_gate"
        socket.send_fds(channel, [payload({"pid": child.pid, "start": identity[2], "exec_stop": True})],
                        [child.stdin.fileno(), child.stdout.fileno(), child.stderr.fileno()])
        child.stdin.close()  # The controller alone retains the input writer.
        phase = "await_control_continue"
        command = channel.recv(1)
        assert command == b"C"
        phase = "detach_control"
        ptrace(17, child.pid)  # PTRACE_DETACH resumes this owned exec-stop control.
        status = child.wait(timeout=7)
        channel.send(payload({"status": status, "reaped": True}))
    except BaseException as error:
        report_failure(phase, error)
        raise
    finally:
        try:
            if child is not None: errors.extend(stop_owned(child, time.monotonic() + 2))
        finally:
            if channel is not None: channel.close()
        if errors: raise RuntimeError("Exec-gate owner cleanup unconfirmed")


def exec_gate_driver(binary, expected, role, protocol):
    subreaper()
    records = []
    for mode in ("control", "death"):
        parent = channel = peer = None; held = []; tested_reap = False; result = None
        errors = []
        try:
            channel, peer = socket.socketpair(socket.AF_UNIX, socket.SOCK_DGRAM); channel.settimeout(10)
            parent = subprocess.Popen(driver_argv("exec-gate-owner", binary, expected, peer.fileno()),
                                      pass_fds=(peer.fileno(),), stdin=subprocess.DEVNULL,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            peer.close(); peer = None
            data, held, flags, _ = socket.recv_fds(channel, 1024, 3)
            gate = json.loads(data)
            if "owner_failure" in gate:
                assert held == [] and flags == 0
                raise RuntimeError("Owned exec-gate failure: " + json.dumps(gate["owner_failure"], sort_keys=True))
            child = gate["pid"]
            assert len(held) == 3 and flags == 0 and gate["exec_stop"] is True
            assert proc_identity(f"/proc/{child}/stat") == (child, parent.pid, gate["start"])
            assert prior.digest(f"/proc/{child}/exe") == expected
            os.set_blocking(held[1], False)
            with pytest.raises(BlockingIOError): os.read(held[1], 1)
            if mode == "control":
                channel.send(b"C")
                checked_hello(held[1], protocol)
                raw = payload(request_for(role)); os.write(held[0], struct.pack("<I", len(raw)) + raw)
                os.close(held[0]); held[0] = -1
                response = frame_read(held[1], 65536, time.monotonic() + 5)
                admitted_response(role, response)
                assert read_to_eof(held[1], time.monotonic() + 2) == b""
                assert read_to_eof(held[2], time.monotonic() + 2) == b""
                assert json.loads(channel.recv(1024)) == {"status": 0, "reaped": True}
                out, err = prior.collect_output(parent, 3)
                assert parent.returncode == 0 and out == err == b""
                tested_reap = True
                result = {"mode": mode, "exec_stop": True, "complete_exchange": True, "exit": 0}
            else:
                signal_owned(parent.pid, signal.SIGKILL)
                parent.wait(timeout=2); assert parent.returncode == -signal.SIGKILL
                end = time.monotonic() + 3
                while time.monotonic() < end:
                    status = owned_status(child)
                    if status is not None: break
                    time.sleep(.005)
                assert status is not None, "Real image did not exit after pre-hello parent death"
                found, status = os.waitpid(child, os.WNOHANG)
                assert found == child and os.WIFEXITED(status) and os.WEXITSTATUS(status) == 2
                tested_reap = True
                # Parent exited before setup; real post-install parent check must
                # reject. This is not credited as installed-PDEATHSIG behavior.
                assert read_to_eof(held[1], time.monotonic() + 1) == b""
                assert read_to_eof(held[2], time.monotonic() + 1) == b""
                with pytest.raises(ChildProcessError): os.waitpid(child, os.WNOHANG)
                result = {"mode": mode, "exec_stop": True, "retained_stdin": True,
                          "hello_bytes": 0, "exit": 2, "exact_reap": True}
        finally:
            try:
                if parent is not None: errors.extend(stop_owned(parent, time.monotonic() + 2))
            finally:
                observed, _, remaining = cleanup_adopted(time.monotonic() + 2)
                errors.extend(remaining)
                if tested_reap and observed: errors.append("unexpected-child-after-tested-reap")
                for fd in held:
                    if fd >= 0: os.close(fd)
                for item in (channel, peer):
                    if item is not None: item.close()
            if errors: raise RuntimeError("Exec-gate driver cleanup unconfirmed: " + repr(errors))
        records.append(result)
    assert kernel_empty_children()
    print(json.dumps(records), flush=True)


@pytest.mark.parametrize("role,protocol", ROLES)
def test_completion_real_before_hello_parent_death(request, images, tmp_path, role, protocol):
    child = prior.own_command(request, driver_argv("exec-gate", images[role], images[role + "_sha256"], role, protocol),
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = prior.collect_output(child, 25)
    (tmp_path / "gate.stdout").write_bytes(out); (tmp_path / "gate.stderr").write_bytes(err)
    assert child.returncode == 0 and err == b"", (child.returncode, out, err)
    records = json.loads(out)
    assert records == [{"mode": "control", "exec_stop": True, "complete_exchange": True, "exit": 0},
                       {"mode": "death", "exec_stop": True, "retained_stdin": True,
                        "hello_bytes": 0, "exit": 2, "exact_reap": True}]


@pytest.mark.parametrize("role", ["scanner", "kernel"])
@pytest.mark.parametrize("action", ["cancel", "revoke"])
def test_completion_observed_authorization_poll_intervals(request, probe, portable_project, monkeypatch, tmp_path, role, action):
    ctx = prior.project_context(portable_project)
    with monkeypatch.context() as control_patch:
        control = prior.LaunchAudit(request, control_patch, probe_role=role, probe_mode="normal")
        assert prior.exchange(probe, role, authorize=lambda: workflow.authorize(ctx), cancelled=lambda: False) == b'{"probe":true}'
        control.reaped(); assert control.trace() == b"SHIERX"
    audit = prior.LaunchAudit(request, monkeypatch, probe_role=role, probe_mode="exchange_delay")
    consumed = bytearray(); polls = []; stopped = []
    def authorize():
        now = time.monotonic()
        if audit.events:
            try: consumed.extend(os.read(audit.events[0], 4096))
            except BlockingIOError: pass
        if b"E" in consumed:
            polls.append(now)
            if len(polls) == 5:
                stopped.append(now)
                if action == "revoke": prior.revoke(ctx)
        workflow.authorize(ctx)
    with pytest.raises(CoreError) as error:
        prior.exchange(probe, role, authorize=authorize, cancelled=lambda: bool(stopped) and action == "cancel")
    returned = time.monotonic()
    intervals = [b - a for a, b in zip(polls, polls[1:])]
    record(tmp_path, "observed-polls", {"timestamps": polls, "intervals": intervals,
           "literal_max_seconds": .1, "response_seconds": returned - stopped[0] if stopped else None,
           "code": error.value.code})
    assert error.value.code == "SOURCE_FACTS_" + ("CANCELLED" if action == "cancel" else "PERMISSION_DENIED")
    audit.reaped(); audit.trace()
    assert len(intervals) == 4 and all(0 <= elapsed <= .1 for elapsed in intervals)
    assert returned - stopped[0] < 2


@pytest.mark.parametrize("action", ["cancel", "revoke"])
def test_completion_cancel_or_revoke_before_kernel_launch(request, images, source_case, portable_project, monkeypatch, action):
    ctx = prior.project_context(portable_project)
    with monkeypatch.context() as control_patch:
        control = prior.LaunchAudit(request, control_patch)
        result = workflow.source_facts(ctx, **images, **source_case[0]); control.reaped()
        assert result["kernel"]["observations"]["selector"]["state"] == "observed"
        assert len(control.children) == 3
    audit = prior.LaunchAudit(request, monkeypatch); triggered = []
    real = workflow.run_owned_helper
    def before_kernel(*args, **kwargs):
        if kwargs["role"] == "kernel":
            triggered.append(True)
            if action == "revoke": prior.revoke(ctx)
        return real(*args, **kwargs)
    monkeypatch.setattr(workflow, "run_owned_helper", before_kernel)
    with pytest.raises(CoreError) as error:
        workflow.source_facts(ctx, **images, **source_case[0], cancelled=lambda: bool(triggered) and action == "cancel")
    assert triggered == [True] and len(audit.children) == 2
    assert error.value.code == "SOURCE_FACTS_" + ("CANCELLED" if action == "cancel" else "PERMISSION_DENIED")
    assert str(error.value) == prior.MESSAGE and error.value.details == {}
    audit.reaped()


def test_completion_real_sixty_second_operation_deadline(request, images, source_case, portable_project, monkeypatch, capsys, tmp_path):
    case, files = source_case
    metadata = "CommonModules/Candidate.xml"
    files[metadata] = files[metadata].replace(b"<Properties>", b"<Properties>" + b" " * (4 * 1024 * 1024 - len(files[metadata])))
    assert len(files[metadata]) == 4 * 1024 * 1024
    case["archive"].write_bytes(prior.archive_bytes(files)); case["archive_sha256"] = prior.digest(case["archive"])
    with monkeypatch.context() as control_patch:
        control = prior.LaunchAudit(request, control_patch)
        assert cli.main(prior.argv(portable_project, images, case)) == 0
        output = capsys.readouterr(); control.reaped()
        assert not output.err and json.loads(output.out)["result"]["kernel"]["observations"]["server"] == {"state": "observed", "value": False, "receipt_id": 3, "property_id": 1}
    audit = prior.LaunchAudit(request, monkeypatch)
    real = RustInputSession.request; requests = []; polls = []; delay_entries = []
    def delayed(session, operation, **fields):
        # Delay BETWEEN real chunk requests, never past a per-request subdeadline.
        # Both authorize/checkpoint callbacks are the unchanged production checks.
        if operation == "read_entry":
            start = time.monotonic(); delay_entries.append(start)
            try:
                while time.monotonic() - start < .55:
                    session.authorize(); polls.append(time.monotonic())
                    time.sleep(min(.025, max(0, .55 - (time.monotonic() - start))))
            finally:
                requests.append({"entry_id": fields["entry_id"], "offset": fields["offset"], "delay": time.monotonic() - start})
        began = time.monotonic()
        result = real(session, operation, **fields)
        requests.append({"operation": operation, "elapsed": time.monotonic() - began})
        return result
    monkeypatch.setattr(RustInputSession, "request", delayed)
    began = time.monotonic()
    assert cli.main(prior.argv(portable_project, images, case)) == 2
    elapsed = time.monotonic() - began
    output = capsys.readouterr()
    record(tmp_path, "whole-operation", {"elapsed_seconds": elapsed, "chunk_delays": len(delay_entries),
           "requests": requests, "poll_timestamps": polls, "stdout": output.out, "stderr": output.err})
    prior.fixed_error(output, "TIMEOUT")
    assert 60 <= elapsed < 63
    assert len(delay_entries) > 90 and len(audit.children) == 1
    assert all(item.get("elapsed", 0) < 5 for item in requests if item.get("operation") != "open_import")
    assert all(item.get("delay", 0) < 1 for item in requests)
    audit.reaped()


@pytest.mark.parametrize("role", ["scanner", "kernel"])
@pytest.mark.parametrize("primary", ["cancel", "timeout"])
def test_completion_real_cleanup_confirmation_timeout(request, probe, monkeypatch, tmp_path, role, primary):
    with monkeypatch.context() as control_patch:
        control = prior.LaunchAudit(request, control_patch, probe_role=role, probe_mode="normal")
        assert prior.exchange(probe, role) == b'{"probe":true}'
        control.reaped(); assert control.trace() == b"SHIERX"
    audit = prior.LaunchAudit(request, monkeypatch, probe_role=role, probe_mode="exchange_delay")
    consumed = bytearray(); suppression = []; waits = []; original_wait = []; cleanup_primary = []; identities = []
    real_launch = subprocess.Popen; real_cleanup = process._cleanup
    def launch(*args, **kwargs):
        child = real_launch(*args, **kwargs)
        assert len(audit.children) == 1, "Fault may own exactly one sleeping probe"
        identity = proc_identity(f"/proc/{child.pid}/stat"); identities.append(identity)
        wait = child.wait; original_wait.append(wait)
        def suppressed_kill():
            assert child is audit.children[0]
            assert proc_identity(f"/proc/{child.pid}/stat") == identity
            assert owned_status(child.pid) is None
            suppression.append(child.pid)  # Suppress ONLY this retained child's product kill.
        def observed_wait(*args, **kwargs):
            start = time.monotonic()
            try: return wait(*args, **kwargs)
            except subprocess.TimeoutExpired:
                waits.append({"timeout": kwargs.get("timeout"), "elapsed": time.monotonic() - start})
                raise
        child.kill = suppressed_kill; child.wait = observed_wait
        return child
    def cleanup(*args, **kwargs):
        exception = sys.exc_info()[1]
        cleanup_primary.append(getattr(exception, "code", None))
        return real_cleanup(*args, **kwargs)  # Actual unchanged wait(timeout=2).
    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(process, "_cleanup", cleanup)
    def authorize():
        if audit.events:
            try: consumed.extend(os.read(audit.events[0], 4096))
            except BlockingIOError: pass
    began = time.monotonic()
    try:
        with pytest.raises(CoreError) as error:
            prior.exchange(probe, role, authorize=authorize,
                cancelled=lambda: primary == "cancel" and b"E" in consumed,
                deadline=began + (.5 if primary == "timeout" else 10))
        elapsed = time.monotonic() - began
        record(tmp_path, "cleanup-timeout", {"elapsed": elapsed, "suppressed_pid": suppression,
               "waits": waits, "primary": cleanup_primary, "final": error.value.code})
        assert error.value.code == "SOURCE_FACTS_CLEANUP_UNCONFIRMED"
        assert str(error.value) == prior.MESSAGE and error.value.details == {}
        assert b"E" in consumed and len(suppression) == 1
        assert cleanup_primary == ["SOURCE_FACTS_" + ("CANCELLED" if primary == "cancel" else "TIMEOUT")]
        assert len(waits) == 1 and waits[0]["timeout"] == 2 and 2 <= waits[0]["elapsed"] < 3
        child = audit.children[0]
        assert child.returncode is None and owned_status(child.pid) is None
        assert all(stream.closed for stream in (child.stdin, child.stdout, child.stderr))
    finally:
        # Independent exact PID/start/wait ownership gate, outside suppressed kill.
        # Never wait for the probe alarm, signal a process name, or reap anyone else.
        if audit.children:
            child = audit.children[0]
            if child.returncode is None:
                signal_owned(child.pid, signal.SIGKILL, start_time=identities[0][2])
                original_wait[0](timeout=2)
            assert child.returncode == -signal.SIGKILL
            with pytest.raises(ChildProcessError): os.waitpid(child.pid, os.WNOHANG)
            audit.trace()


@pytest.mark.parametrize("defect", ["missing", "signed", "space", "exponent", "image"])
def test_completion_cli_offending_synth_canaries(request, images, source_case, portable_project, monkeypatch, capsys, tmp_path, defect):
    audit = prior.LaunchAudit(request, monkeypatch)
    args = prior.argv(portable_project, images, source_case[0])
    assert cli.main(args) == 0
    control = capsys.readouterr(); assert not control.err and "result" in json.loads(control.out)
    if defect == "image":
        args[args.index("--source-scanner") + 1] = str(tmp_path / "SYNTH_IMAGE_MISSING")
    elif defect == "missing":
        # A canary-valued option-like token is the offending missing-value input.
        args[args.index("--archive") + 1] = "--SYNTH_MISSING_VALUE"
    else:
        args[args.index("--selector-end") + 1] = {
            "signed": "+1SYNTH_SIGNED", "space": " 1SYNTH_SPACE", "exponent": "1e0SYNTH_EXPONENT"}[defect]
    assert cli.main(args) == 2
    prior.fixed_error(capsys.readouterr(), "EXECUTABLE_INVALID" if defect == "image" else "INVALID_ARGUMENT")
    audit.reaped()


def canary_case(source_case, alias=False):
    case, original = source_case; files = {}
    for name, raw in original.items():
        name = name.replace("Candidate", "SYNTH_Candidate")
        files[name] = raw.replace(b"Candidate", b"SYNTH_Candidate")
    case["candidate_entry"] = "CommonModules/SYNTH_Candidate/Ext/Module.bsl"
    if alias:
        files[case["candidate_entry"]] = files[case["caller_entry"]] + files[case["candidate_entry"]]
        case["caller_entry"] = case["candidate_entry"]
    raw = files[case["caller_entry"]]
    case["selector_start"] = raw.index(b"SYNTH_Candidate.SYNTH_Method")
    case["selector_end"] = case["selector_start"] + len(b"SYNTH_Candidate.SYNTH_Method")
    metadata = "CommonModules/SYNTH_Candidate.xml"
    files[metadata] = files[metadata].replace(b"<Properties>", b"<Properties><!-- SYNTH_XML_TEXT_CANARY -->")
    case["archive"].write_bytes(prior.archive_bytes(files)); case["archive_sha256"] = prior.digest(case["archive"])
    return case, files


def string_locations(value, text, path=()):
    if isinstance(value, str): return [path] if text in value else []
    if isinstance(value, dict):
        return [found for key, item in value.items() for found in string_locations(item, text, (*path, key))]
    if isinstance(value, list):
        return [found for index, item in enumerate(value) for found in string_locations(item, text, (*path, index))]
    return []


def raw_native_exchange(request, image, protocol, raw):
    child = prior.own_command(request, [str(image), "--parent-pid", str(os.getpid())],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GOMAXPROCS": "1"})
    checked_hello(child.stdout.fileno(), protocol)
    child.stdin.write(struct.pack("<I", len(raw)) + raw); child.stdin.close()
    out, err = prior.collect_output(child, 6)
    assert len(out) >= 4 and len(out) == 4 + struct.unpack("<I", out[:4])[0]
    assert err == b""
    with pytest.raises(ChildProcessError): os.waitpid(child.pid, os.WNOHANG)
    return child.returncode, out[4:]


@pytest.mark.parametrize("alias", [False, True])
def test_completion_synth_disclosure_boundaries_and_reference_slots(request, images, source_case, portable_project, monkeypatch, tmp_path, alias):
    case, files = canary_case(source_case, alias)
    options = dict(images)
    for role, _ in ROLES:
        path = tmp_path / ("SYNTH_ABSOLUTE_IMAGE_" + role)
        shutil.copyfile(images[role], path); path.chmod(0o700); options[role] = path
    audit = prior.LaunchAudit(request, monkeypatch); boundaries = []
    real = workflow.run_owned_helper
    def capture(*args, **kwargs):
        raw = real(*args, **kwargs)
        boundaries.append((kwargs["role"], kwargs["request"], raw))
        assert b"SYNTH" not in raw  # Check at each direct Go/Rust output boundary.
        return raw
    monkeypatch.setattr(workflow, "run_owned_helper", capture)
    result = workflow.source_facts(prior.project_context(portable_project), **options, **case)
    audit.reaped(); assert [role for role, _, _ in boundaries] == ["scanner", "kernel"]
    assert result["kernel"]["observations"]["server"] == {"state": "observed", "value": False, "receipt_id": 3, "property_id": 1}
    for secret in ("SYNTH_XML_TEXT_CANARY", "SYNTH_Method", "SYNTH_LITERAL_CANARY", "SYNTH_COMMENT_CANARY", "SYNTH_ABSOLUTE_IMAGE", str(case["archive"])):
        assert not string_locations(result, secret)
    references = {"caller": case["caller_entry"], "candidate": case["candidate_entry"],
                  "metadata": "CommonModules/SYNTH_Candidate.xml"}
    for selected in set(references.values()):
        expected = [("references", role, "relative_path") for role, path in references.items() if path == selected]
        assert sorted(string_locations(result, selected)) == sorted(expected)
    without_refs = copy.deepcopy(result); del without_refs["references"]
    assert "SYNTH" not in json.dumps(without_refs)
    for role, reference in result["references"].items():
        assert reference["relative_path"] == references[role]
        assert reference["raw_sha256"] == hashlib.sha256(files[references[role]]).hexdigest()
    # Rust never receives source names in admitted input. Carry a SYNTH canary in
    # its own malformed input and inspect the actual closed native error bytes.
    monkeypatch.undo()  # Restore launch adapter before the separately owned wire control.
    valid = boundaries[1][1]
    status, native = raw_native_exchange(request, images["source_kernel"], "submitted_source_facts_v1", valid)
    assert status == 0 and json.loads(native) == result["kernel"]
    malformed = json.loads(valid); malformed["SYNTH_RUST_KEY"] = "SYNTH_RUST_VALUE"
    status, native = raw_native_exchange(request, images["source_kernel"], "submitted_source_facts_v1", payload(malformed))
    assert status == 2 and native == b'{"protocol":"submitted_source_facts_v1","status":"error","code":"invalid_envelope"}'
    record(tmp_path, "canary-boundaries", {"alias": alias, "go_sha256": hashlib.sha256(boundaries[0][2]).hexdigest(),
           "kernel_sha256": hashlib.sha256(boundaries[1][2]).hexdigest(), "rust_error": native.decode(), "references": references})


def malicious_child(role, parent):
    """Bounded transport fault double, explicitly not a native-source oracle."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) or os.getppid() != int(parent): return 2
    signal.alarm(10)
    protocol = "source_fact_scan_v1" if role == "scanner" else "submitted_source_facts_v1"
    hello = payload({"protocol": protocol, "kind": "hello", "ownership": "linux_parent_death_v1"})
    os.write(1, struct.pack("<I", len(hello)) + hello)
    size = struct.unpack("<I", read_exact(0, 4, time.monotonic() + 3))[0]
    assert 1 <= size <= 1_500_000
    read_exact(0, size, time.monotonic() + 3)
    assert read_to_eof(0, time.monotonic() + 3, cap=1) == b""
    error = payload({"protocol": protocol, "status": "error", "code": "SYNTH_CHILD_ERROR", "message": "SYNTH_PRIVATE_CHILD_MESSAGE"})
    os.write(2, b"SYNTH_PRIVATE_CHILD_STDERR\n")
    os.write(1, struct.pack("<I", len(error)) + error)
    return 2


@pytest.mark.parametrize("role", ["scanner", "kernel"])
def test_completion_adversarial_child_error_and_stderr_never_escape(request, images, source_case, portable_project, monkeypatch, capsys, role):
    with monkeypatch.context() as control_patch:
        control = prior.LaunchAudit(request, control_patch)
        assert cli.main(prior.argv(portable_project, images, source_case[0])) == 0
        assert "result" in json.loads(capsys.readouterr().out)
        control.reaped(); assert len(control.children) == 3
    real = subprocess.Popen; native_index = []; replaced = []
    def redirect(argv, **kwargs):
        if "GOMAXPROCS" in kwargs.get("env", {}):
            actual_role = "scanner" if not native_index else "kernel"; native_index.append(actual_role)
            if actual_role == role:
                replaced.append(actual_role)
                argv = driver_argv("malicious-child", role, os.getpid())
                kwargs["pass_fds"] = ()
        return real(argv, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", redirect)
    audit = prior.LaunchAudit(request, monkeypatch)
    assert cli.main(prior.argv(portable_project, images, source_case[0])) == 2
    prior.fixed_error(capsys.readouterr(), "CHILD_FAILED")
    assert replaced == [role]
    audit.reaped()


# These are explicit trusted loader/runtime reads, not access to arbitrary /etc,
# /proc, /sys or a user's home. Missing/extra files remain an audit failure.
TRUSTED_SYSTEM_FILES = {
    "/etc/ld.so.cache", "/etc/localtime",
    "/lib/x86_64-linux-gnu/libc.so.6", "/usr/lib/x86_64-linux-gnu/libc.so.6",
    "/lib/x86_64-linux-gnu/libgcc_s.so.1", "/usr/lib/x86_64-linux-gnu/libgcc_s.so.1",
    "/lib64/ld-linux-x86-64.so.2", "/usr/lib64/ld-linux-x86-64.so.2",
    "/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2", "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    "/sys/kernel/mm/transparent_hugepage/hpage_pmd_size", "/proc/self/maps",
}
NETWORK_SYSCALLS = set("socket socketpair socketcall connect bind listen accept accept4 sendto sendmsg sendmmsg recvfrom recvmsg recvmmsg shutdown getsockname getpeername setsockopt getsockopt".split())
FORBIDDEN_SYSCALLS = set("io_uring_setup io_uring_enter io_uring_register mount umount2 pivot_root chroot open_by_handle_at name_to_handle_at bpf unshare setns ptrace process_vm_readv process_vm_writev".split())
PATH_MUTATIONS = set("creat mkdir mkdirat mknod mknodat link linkat symlink symlinkat rename renameat renameat2 truncate chmod fchmodat chown fchownat lchown utime utimes futimesat utimensat rmdir".split())
PATH_INSPECTIONS = set("access faccessat faccessat2 stat lstat stat64 lstat64 newfstatat statx readlink readlinkat statfs statfs64 execve execveat open openat openat2 unlink unlinkat chdir".split())
FD_WRITE_SYSCALLS = {"write", "writev", "pwrite64", "pwritev", "pwritev2", "ftruncate", "fallocate", "fchmod"}
C_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')
# Closed syscall inventory: any unrecognized call is an audit failure, rather
# than silently assuming it cannot reach a file, network, or native service.
AUDITED_SYSCALLS = set("""
read readv pread64 preadv preadv2 write writev pwrite64 pwritev pwritev2 close
close_range lseek fstat fstat64 newfstatat statx stat lstat stat64 lstat64
open openat openat2 access faccessat faccessat2 readlink readlinkat unlink unlinkat
statfs statfs64 fstatfs fstatfs64 getdents getdents64 getcwd
mmap mmap2 mprotect munmap brk mremap madvise mincore msync
rt_sigaction rt_sigprocmask rt_sigreturn rt_sigpending rt_sigtimedwait rt_sigsuspend
sigaltstack tgkill kill alarm setitimer getitimer
futex futex_waitv set_robust_list get_robust_list rseq set_tid_address
getpid getppid gettid getuid geteuid getgid getegid getgroups getresuid getresgid
getpgrp getpgid getsid uname sysinfo getrandom arch_prctl prctl
getrlimit setrlimit prlimit64 getrusage times clock_gettime clock_getres
clock_nanosleep nanosleep gettimeofday sched_yield sched_getaffinity
pipe pipe2 dup dup2 dup3 fcntl fcntl64 flock ioctl epoll_create epoll_create1
epoll_ctl epoll_wait epoll_pwait epoll_pwait2 poll ppoll select pselect6
eventfd eventfd2 memfd_create fchmod ftruncate fallocate fsync fdatasync
clone clone3 fork vfork execve execveat wait4 waitid exit exit_group restart_syscall
""".split())


def trace_host(config_path, event_fd):
    import rentgen_core.rust_input as rust_input
    config = json.loads(Path(config_path).read_text()); event_fd = int(event_fd)
    project = config["project"]
    from rentgen_core.local import LocalRuntime
    from rentgen_core.local_identity import current_local_principal
    principal = current_local_principal(identity_profile=Path(project["profile"]))
    ctx = LocalRuntime(Path(project["registry"])).state_context(principal, project["id"])
    assert str(ctx.state.path) == config["state"]
    subreaper(); children = []; real_popen = subprocess.Popen
    real_image = rust_input._executable; real_open = RustInputSession.open_import
    def mark(value): os.write(event_fd, MARKER + value.encode() + b"\n")
    def image(path, expected, stack, **kwargs):
        fd = real_image(path, expected, stack, **kwargs)
        role = next(key for key, value in config["images"].items() if not key.endswith("_sha256") and str(path) == value)
        mark("L:" + role); return fd
    def opened(session, *args, **kwargs):
        result = real_open(session, *args, **kwargs); mark("A"); return result
    def launch(*args, **kwargs):
        child = real_popen(*args, **kwargs); children.append(child); return child
    rust_input._executable = process._executable = image
    RustInputSession.open_import = opened; subprocess.Popen = launch
    tested = False; errors = []
    try:
        mark("S")
        result = workflow.source_facts(ctx, **config["images"], **config["case"])
        mark("E")
        assert len(children) == 3 and all(child.returncode == 0 for child in children)
        for child in children:
            with pytest.raises(ChildProcessError): os.waitpid(child.pid, os.WNOHANG)
        tested = True
        print(json.dumps(result, separators=(",", ":")), flush=True)
    finally:
        try:
            for child in children: errors.extend(stop_owned(child, time.monotonic() + 2))
            observed, _, remaining = cleanup_adopted(time.monotonic() + 2); errors.extend(remaining)
            if tested and observed: errors.append("unexpected-child-after-product-reap")
        finally:
            os.close(event_fd)
        if errors: raise RuntimeError("Trace-host cleanup unconfirmed")


def trace_controller(config_path, trace_path):
    import resource
    subreaper(); child = None; reader = writer = None; errors = []; result = None
    try:
        reader, writer = os.pipe()
        command = ["/usr/bin/strace", "-f", "-qq", "-ttt", "-yy", "-s", "4096", "-o", str(trace_path),
                   "--", *driver_argv("trace-host", config_path, writer)]
        def bound_trace_file(): resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
        child = subprocess.Popen(command, pass_fds=(writer,), stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 preexec_fn=bound_trace_file)
        os.close(writer); writer = None
        out, err = prior.collect_output(child, 25)
        markers = read_to_eof(reader, time.monotonic() + 2, cap=1024)
        Path(str(trace_path) + ".stdout").write_bytes(out)
        Path(str(trace_path) + ".stderr").write_bytes(err)
        result = {"status": child.returncode, "markers": markers.decode(),
                  "stdout_sha256": hashlib.sha256(out).hexdigest(), "stderr": err.decode(errors="replace")}
    finally:
        try:
            if child is not None: errors.extend(stop_owned(child, time.monotonic() + 2))
        finally:
            observed, _, remaining = cleanup_adopted(time.monotonic() + 2); errors.extend(remaining)
            if result is not None and observed: errors.append("unexpected-adopted-traced-child")
            for fd in (reader, writer):
                if fd is not None: os.close(fd)
        if errors: raise RuntimeError("Trace-controller cleanup unconfirmed: " + repr(errors))
    assert kernel_empty_children()
    print(json.dumps(result), flush=True)


def trace_calls(raw):
    """Fail closed on unreadable/incomplete syscall lines; join strace split calls."""
    pending = {}; calls = []
    for number, line in enumerate(raw.splitlines(), 1):
        match = re.match(r"^(\d+)\s+([0-9]+\.[0-9]+)\s+(.*)$", line)
        assert match is not None, (number, line[:200])
        pid, stamp, body = int(match[1]), float(match[2]), match[3]
        start_line = number
        if body.startswith(("--- ", "+++ ")): continue
        # strace 6.8 uses ??? when it cannot decode the syscall registers.
        # A sibling exit_group can explain that loss, but cannot recover the
        # missing observation. Never reinterpret it as a harmless syscall.
        assert not body.startswith(("???(", "<... ??? resumed>")), ("Unresolved syscall observation", number, line)
        if body.endswith(" <unfinished ...>"):
            assert pid not in pending, ("Duplicate unfinished syscall", number, line)
            assert re.match(r"^[a-zA-Z0-9_]+\(", body), ("Malformed syscall entry", number, line)
            pending[pid] = (number, stamp, body[:-len(" <unfinished ...>")]); continue
        if body.startswith("<... "):
            resumed = re.match(r"^<\.\.\. ([a-zA-Z0-9_]+) resumed>(.*)$", body)
            assert resumed is not None and pid in pending, line
            start_line, began, head = pending.pop(pid)
            assert head.startswith(resumed[1] + "(")
            body = head + resumed[2]; stamp = began
        else:
            assert pid not in pending, ("Missing syscall resume", number, line)
        parsed = re.match(r"^([a-zA-Z0-9_]+)\((.*)\)\s+=\s+(.*)$", body)
        if parsed is None:
            raise AssertionError((number, body[:300]))
        calls.append({"line": number, "start_line": start_line, "pid": pid, "stamp": stamp,
                      "name": parsed[1], "args": parsed[2], "result": parsed[3]})
    # A death banner alone cannot complete an unfinished syscall observation.
    assert not pending, pending
    return calls


def traced_path(call):
    # Trace data describes Linux paths, regardless of the interpreter's host OS.
    args = call["args"]; strings = C_STRING.findall(args)
    assert strings, ("Missing decoded pathname", call)
    path = ast.literal_eval(strings[0])
    assert isinstance(path, str) and "\x00" not in path
    if not path:  # AT_EMPTY_PATH queries use the retained descriptor annotation.
        match = re.match(r"\d+<([^>]+)>,\s*\"\"", args)
        return match[1] if match else ""
    if path.startswith("/"): return posixpath.normpath(path)
    # dirfd annotations are supplied by strace -yy, not guessed from a basename.
    match = re.match(r"(?:\d+|AT_FDCWD)<([^>]+)>,", args)
    if match: return posixpath.normpath(posixpath.join(match[1], path))
    if call["name"] in {"open", "access", "stat", "lstat", "readlink", "execve", "chdir"} or args.startswith("AT_FDCWD,"):
        return posixpath.normpath(posixpath.join(ROOT.as_posix(), path))
    raise AssertionError(("Unresolved trace pathname", call))


def fd_path(args):
    match = re.match(r"\d+<([^>]+)>", args)
    assert match is not None, ("Missing decoded descriptor", args[:200])
    return match[1]


def absent_loader_probe(call):
    """One failed metadata lookup, never authority to read a preload file."""
    return (call["name"] == "access"
            and call["args"] == '"/etc/ld.so.preload", R_OK'
            and call["result"] == "-1 ENOENT (No such file or directory)")


def trace_marker(call):
    if call["name"] == "write" and '"RENTGEN_P_TRACE:' in call["args"]:
        value = ast.literal_eval(C_STRING.findall(call["args"])[0])
        return value.strip().split(":", 1)[1]
    return None


def check_trace_boundaries(calls):
    """Never assign a straddling observation to one side of an authority marker."""
    boundaries = [(call, trace_marker(call)) for call in calls if trace_marker(call) is not None]
    for call in calls:
        for boundary, marker in boundaries:
            if call is boundary: continue
            # S/E delimit all observations. L/A change locator-open authority;
            # ordinary pipe reads may span these internal admission markers.
            sensitive = marker in {"S", "E"} or (
                call["name"] in {"open", "openat", "openat2"}
                and (marker == "A" or marker.startswith("L:")))
            if sensitive:
                disjoint = call["line"] < boundary["start_line"] or call["start_line"] > boundary["line"]
                assert disjoint, ("Ambiguous trace boundary", marker, call, boundary)


def inspect_trace(trace, config):
    calls = trace_calls(trace); markers = []; active = False; finished = False
    check_trace_boundaries(calls)
    facts = {"opens": [], "execs": [], "memfds": [], "process_creates": [], "threads": [], "sidecar_mutations": [], "runtime_reads": [], "absent_loader_probes": []}
    accepted = set(); source_paths = {config["case"]["archive"]: "archive"}
    source_paths.update({value: key for key, value in config["images"].items() if not key.endswith("_sha256")})
    state = config["state"]; sidecars = {state + suffix for suffix in ("-wal", "-shm", "-journal")}
    authorized = set(source_paths) | {state} | sidecars
    directory_ancestors = {str(parent) for item in authorized for parent in PurePosixPath(item).parents}
    runtime_roots = {PurePosixPath(value) for value in config["runtime_roots"]}
    runtime_dirs = {str(parent) for root in runtime_roots for parent in (root, *root.parents)}
    runtime_files = set(TRUSTED_SYSTEM_FILES)
    def runtime(path):
        if path in runtime_files: return True
        target = PurePosixPath(path)
        return any(target.is_relative_to(root) and (target.suffix in {".py", ".pyc", ".so"} or ".so." in target.name) for root in runtime_roots)
    def allowed_path(path, call):
        if absent_loader_probe(call): facts["absent_loader_probes"].append(call); return True
        if path in authorized: return True
        if runtime(path): facts["runtime_reads"].append(path); return True
        # Directory traversals/metadata are not file-content authority. A root
        # ancestor open must request O_DIRECTORY; no broad readable subtree.
        if path in directory_ancestors | runtime_dirs:
            return call["name"] not in {"open", "openat", "openat2"} or "O_DIRECTORY" in call["args"]
        if path.startswith("/proc/self/fd/") and call["name"] in {"execve", "execveat"}: return True
        if path.startswith("/memfd:rentgen-input-core") and "(deleted)" in path: return True
        return False
    for call in calls:
        name, args, result = call["name"], call["args"], call["result"]
        marker = trace_marker(call)
        if marker is not None:
            markers.append(marker)
            if marker == "S": assert not active and not finished; active = True
            elif marker == "E": assert active; active = False; finished = True
            elif marker == "A": assert active; accepted.add("archive")
            elif marker.startswith("L:"): assert active; accepted.add(marker[2:])
            else: raise AssertionError(marker)
            continue
        if not active: continue
        assert name in AUDITED_SYSCALLS and name not in NETWORK_SYSCALLS | FORBIDDEN_SYSCALLS | PATH_MUTATIONS, call
        if name == "memfd_create":
            assert C_STRING.findall(args) == ['"rentgen-input-core"'] and "MFD_ALLOW_SEALING" in args and not result.startswith("-1"), call
            facts["memfds"].append(call)
        if name in {"execve", "execveat"}:
            path = traced_path(call)
            assert re.fullmatch(r"/proc/self/fd/[0-9]+", path) and result.startswith("0"), call
            facts["execs"].append({"pid": call["pid"], "path": path})
        if name in {"clone", "clone3", "fork", "vfork"} and not result.startswith("-1"):
            if "CLONE_THREAD" in args:
                assert "CLONE_VM" in args and "CLONE_SIGHAND" in args, call
                facts["threads"].append(call)
            else:
                facts["process_creates"].append(call)
        if name in PATH_INSPECTIONS:
            path = traced_path(call)
            assert allowed_path(path, call), ("Outside explicit authority", path, call)
            if name in {"open", "openat", "openat2"}:
                assert source_paths.get(path) not in accepted, ("Late locator reopen", path, call)
                if path in source_paths:
                    assert "O_RDONLY" in args and not any(flag in args for flag in ("O_CREAT", "O_TRUNC", "O_WRONLY", "O_RDWR")), call
                if any(flag in args for flag in ("O_CREAT", "O_TRUNC", "O_WRONLY", "O_RDWR")):
                    assert path in sidecars | {state}, call
                facts["opens"].append({"pid": call["pid"], "path": path, "result": result})
            if name in {"unlink", "unlinkat"}:
                assert path in sidecars, call
                facts["sidecar_mutations"].append(call)
        if name in FD_WRITE_SYSCALLS:
            target = fd_path(args)
            assert (target.startswith(("pipe:[", "/memfd:rentgen-input-core")) or target in sidecars), ("Unexpected regular-file write", call)
        if name in {"mmap", "mmap2"} and "PROT_WRITE" in args and "MAP_SHARED" in args and "MAP_ANONYMOUS" not in args:
            descriptors = re.findall(r"\d+<([^>]+)>", args)
            assert descriptors and descriptors[-1] in sidecars, call
        if name in {"sendfile", "copy_file_range", "splice", "tee", "vmsplice"}:
            raise AssertionError(("Unexpected data-transfer syscall", call))
    assert markers == ["S", "L:input_core", "A", "L:source_scanner", "L:source_kernel", "E"]
    assert finished and not active
    assert len(facts["execs"]) == len(facts["process_creates"]) == len(facts["memfds"]) == 3
    created = {int(call["result"].split()[0]) for call in facts["process_creates"]}
    assert created == {call["pid"] for call in facts["execs"]}
    for path in source_paths:
        opened = [call for call in facts["opens"] if call["path"] == path and not call["result"].startswith("-1")]
        assert len(opened) == 1, ("Expected exactly one admitted locator open", path, opened)
    facts["markers"] = markers
    facts["runtime_reads"] = sorted(set(facts["runtime_reads"]))
    facts["trusted_system_allowances"] = sorted(TRUSTED_SYSTEM_FILES)
    facts["trusted_runtime_roots"] = config["runtime_roots"]
    facts["scope"] = "Observed owned synthetic source operation only; trusted Linux/runtime, no sandbox or native Designer guarantee"
    return facts


def preserved_files(project, case, images):
    profile, registry, _, source, _ = project
    roots = [profile.parent, registry.parent / "state", source]
    paths = {profile, registry, Path(case["archive"])}
    paths.update(Path(value) for key, value in images.items() if not key.endswith("_sha256"))
    for root in roots:
        paths.update(path for path in root.rglob("*") if path.is_file())
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


@pytest.mark.parametrize("alias", [False, True])
def test_completion_owned_pipeline_syscall_authority_audit(request, images, source_case, portable_project, tmp_path, qualification_preflight, alias):
    case, _ = canary_case(source_case, alias)
    ctx = prior.project_context(portable_project)
    tool = qualification_preflight["strace"]
    assert tool["path"] == "/usr/bin/strace" and prior.digest(tool["path"]) == tool["sha256"]
    folder = tmp_path / "syscall-evidence"; folder.mkdir()
    config = {"project": {"profile": str(portable_project[0]), "registry": str(portable_project[1]), "id": portable_project[2]},
              "state": str(ctx.state.path), "case": {key: str(value) if isinstance(value, Path) else value for key, value in case.items()},
              "images": {key: str(value) if isinstance(value, Path) else value for key, value in images.items()},
              "runtime_roots": sorted({sysconfig.get_path("stdlib"), sysconfig.get_path("platstdlib"), str(ROOT / "rentgen_core")})}
    config_path = folder / "config.json"; config_path.write_text(json.dumps(config))
    trace_path = folder / "strace.log"
    before = preserved_files(portable_project, case, images)
    child = prior.own_command(request, driver_argv("trace-controller", config_path, trace_path),
                              cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = prior.collect_output(child, 34)
    (folder / "controller.stdout").write_bytes(out); (folder / "controller.stderr").write_bytes(err)
    assert child.returncode == 0 and not err, (child.returncode, out, err)
    status = json.loads(out)
    assert status["status"] == 0 and not status["stderr"], status  # Denial stays an explicit blocker.
    assert status["markers"] == "".join("RENTGEN_P_TRACE:" + item + "\n" for item in ["S", "L:input_core", "A", "L:source_scanner", "L:source_kernel", "E"])
    raw = trace_path.read_bytes(); assert 0 < len(raw) < 32 * 1024 * 1024
    result = json.loads(Path(str(trace_path) + ".stdout").read_bytes())
    assert result["kernel"]["observations"]["selector"]["state"] == "observed"
    assert result["kernel"]["receiver_binding"] == result["kernel"]["runtime_relation"] == "unknown"
    facts = inspect_trace(raw.decode(), config)
    facts["trace_sha256"] = hashlib.sha256(raw).hexdigest()
    facts["source_before"] = before; facts["source_after"] = preserved_files(portable_project, case, images)
    record(folder, "authority-audit", facts)
    assert facts["source_before"] == facts["source_after"]


def main():
    # Fixed entry points used only by this pinned module's owned children.
    mode, *args = sys.argv[1:]
    if mode == "exec-gate-owner": exec_gate_owner(*args)
    elif mode == "exec-gate": exec_gate_driver(*args)
    elif mode == "malicious-child": return malicious_child(*args)
    elif mode == "trace-host": trace_host(*args)
    elif mode == "trace-controller": trace_controller(*args)
    else: raise ValueError("Unknown fixed lifecycle driver")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
