"""Pure capture-wait controls; no SCM/native lifecycle is executed or accepted."""
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def api():
    path = Path(__file__).resolve().parents[2] / "scripts/verification/scm_acceptance_worker.py"
    spec = importlib.util.spec_from_file_location("capture_wait_worker", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def job(phase="capture", operation_id="new", **fields):
    return {"operation_id": operation_id, "phase": phase, "attempts": 0, "error": None, **fields}


def status(*jobs, **fields):
    return {"checked_at": "2026-10-02T00:00:00Z", "error": None,
            "jobs": list(jobs), "reports": [], "last_snapshot": "old", **fields}


def scm(state=4):
    return {"exists": True, "status": {"state": state, "pid": 1234}, "pid_valid": True}


def harness(api, monkeypatch, snapshots, *, event=None):
    worker = api.Acceptance.__new__(api.Acceptance)
    worker.status = Mock(side_effect=snapshots)
    worker.current = Mock(return_value=scm())
    worker.event = event or Mock()
    clock = [0.0]
    monkeypatch.setattr(api, "bounded", lambda seconds: seconds)
    monkeypatch.setattr(api.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(api.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return worker, clock


def test_only_the_new_capture_is_selected(api):
    old = job("done", "old")
    new = job(attempts=2)
    reason, selected = api.classify_capture_wait(status(old, new), scm(), {"old"})
    assert reason == "capture_observed"
    assert selected is new
    assert api.classify_capture_wait(status(old), scm(), {"old"}) == ("waiting_for_new_job", None)


@pytest.mark.parametrize("snapshot,expected", [
    (status(job("report")), "missed_capture_window"),
    (status(job("done")), "missed_capture_window"),
    (status(job("failed", error="scan exploded")), "job_failed"),
    (status(job("superseded")), "job_superseded"),
    (status(job(error="retry failed", attempts=3)), "job_error"),
    (status(job(), error="observer failed"), "observer_error"),
    (status(job(), job(operation_id="another")), "ambiguous_new_jobs"),
    (status(job("alien")), "invalid_job"),
    (status(job(attempts=True)), "invalid_job"),
    (status(job(), job(operation_id="new")), "invalid_job"),
    (status(*[job(operation_id=str(i)) for i in range(11)]), "invalid_status"),
])
def test_explicit_refusals(api, snapshot, expected):
    assert api.classify_capture_wait(snapshot, scm(), {"old"}) == (expected, None)


def test_stopped_service_refuses_even_with_capture(api):
    assert api.classify_capture_wait(status(job()), scm(1), set()) == ("service_stopped", None)


def test_capture_wait_buffers_selected_job_without_event_io(api, monkeypatch):
    selected = job()
    worker, _ = harness(api, monkeypatch, [status(job("done", "old")), status(selected)])
    assert worker.capture_job({"old"}) is selected
    worker.event.assert_not_called()
    worker.flush_capture_observation()
    kind = worker.event.call_args.args[0]
    evidence = worker.event.call_args.kwargs
    assert kind == "capture_wait"
    assert evidence["reason"] == "capture_observed"
    assert evidence["poll_count"] == 2
    assert evidence["samples"][0]["new_jobs"] == []
    assert evidence["samples"][-1]["new_jobs"][0]["operation_id"] == "new"
    assert worker.current.call_count == 2


def test_missed_capture_refuses_without_control(api, monkeypatch):
    worker, _ = harness(api, monkeypatch, [status(job("done"))])
    worker.installer = Mock()
    with pytest.raises(RuntimeError, match="missed_capture_window"):
        worker.capture_job(set())
    worker.installer.stop.assert_not_called()
    assert worker.event.call_args.kwargs["reason"] == "missed_capture_window"


def test_no_job_timeout_keeps_first_and_last_with_fake_clock(api, monkeypatch):
    worker, clock = harness(api, monkeypatch, [])
    worker.status = Mock(side_effect=lambda: status())
    with pytest.raises(RuntimeError, match="Timed out: active capture journal"):
        worker.capture_job(set())
    evidence = worker.event.call_args.kwargs
    assert evidence["reason"] == "timeout"
    assert 90 <= clock[0] < 90.1
    assert evidence["poll_count"] >= 1800
    assert evidence["samples"][0]["elapsed_seconds"] == 0
    assert evidence["samples"][-1]["elapsed_seconds"] >= 90
    assert len(evidence["samples"]) == 2


@pytest.mark.parametrize("boundary", ["status", "current"])
def test_boundary_error_keeps_last_valid_sample_and_original_exception(api, monkeypatch, boundary):
    error = OSError("owned read failed")
    worker, _ = harness(api, monkeypatch, [status(), status()])
    if boundary == "status":
        worker.status = Mock(side_effect=[status(), error])
    else:
        worker.current = Mock(side_effect=[scm(), error])
    with pytest.raises(OSError) as failure:
        worker.capture_job(set())
    assert failure.value is error
    evidence = worker.event.call_args.kwargs
    assert evidence["reason"] == "observation_error"
    assert evidence["poll_count"] == 2
    assert evidence["samples"][0]["scm"]["pid"] == 1234
    assert evidence["error"]["type"] == "OSError"


@pytest.mark.parametrize("write_error", [OSError("disk failed"), KeyboardInterrupt(), SystemExit(8)])
def test_diagnostic_write_failure_does_not_mask_original_error(api, monkeypatch, write_error):
    error = LookupError("original observer exception")
    worker, _ = harness(api, monkeypatch, [error], event=Mock(side_effect=write_error))
    with pytest.raises(LookupError) as failure:
        worker.capture_job(set())
    assert failure.value is error


def test_unprintable_original_exception_survives_after_waiting_poll(api, monkeypatch):
    class UnprintableError(RuntimeError):
        def __str__(self):
            raise SystemExit("secondary formatting failure")
    error = UnprintableError("original failure")
    worker, _ = harness(api, monkeypatch, [status(), error])
    with pytest.raises(UnprintableError) as failure:
        worker.capture_job(set())
    assert failure.value is error


def test_one_pending_summary_cannot_be_overwritten_and_two_flushes_remain_bounded(api, monkeypatch):
    worker, _ = harness(api, monkeypatch, [status(job()), status(job(operation_id="second"))])
    assert worker.capture_job(set())["operation_id"] == "new"
    with pytest.raises(RuntimeError, match="not flushed"):
        worker.capture_job(set())
    worker.flush_capture_observation()
    assert worker.capture_job({"new"})["operation_id"] == "second"
    worker.flush_capture_observation()
    assert worker.pending_capture_observation is None
    assert worker.event.call_count == 2


def test_safe_boundary_flush_failure_refuses_instead_of_silently_accepting(api, monkeypatch):
    worker, _ = harness(api, monkeypatch, [status(job())], event=Mock(side_effect=OSError("disk failed")))
    assert worker.capture_job(set())["operation_id"] == "new"
    with pytest.raises(OSError, match="disk failed"):
        worker.flush_capture_observation()


def test_trace_bounds_unicode_fields_transitions_and_omissions(api):
    trace = api.CaptureObservation(set())
    huge = "😀" * 10000
    for index in range(500):
        snapshot = status(*[job(operation_id=f"{index}-{n}" + huge, error=huge) for n in range(10)],
                          checked_at=huge, error=huge, reports=[{"secret": huge}])
        service = scm()
        service['status']['pid'] += index
        trace.observe(snapshot, service, index / 20, index + 1)
    result = trace.result("observation_error")
    assert len(result["samples"]) <= 16
    assert len(json.dumps(result, ensure_ascii=False).encode("utf-8")) <= 40 * 1024
    assert all(len(json.dumps(s, ensure_ascii=False).encode("utf-8")) <= 2048 for s in result["samples"])
    assert result["samples"][0]["elapsed_seconds"] == 0
    assert result["samples"][-1]["elapsed_seconds"] == 24.95
    assert result["omitted_transitions"] > 0
    assert result["samples"][-1]["omitted_jobs"] > 0
    assert result["samples"][-1]["truncated_fields"] > 0
    assert "secret" not in json.dumps(result)


def test_capture_changing_to_done_before_stop_observation_remains_refused(api, monkeypatch, tmp_path):
    old = job("done", "old")
    first = status(old, reports=[{"id": "old"}])
    repeated = {**first, "checked_at": "next tick"}
    worker, _ = harness(api, monkeypatch, [first, repeated, status(old, job()), status(old, job("done"))])
    worker.f = {"service_source": str(tmp_path)}
    worker.spec = object()
    worker.native = Mock()
    worker.native.query.return_value = {"exists": False}
    worker.installer = Mock()
    worker.prepare_acl = Mock()
    worker.start = Mock()
    worker.stop = Mock()
    worker.reported = Mock(return_value=first)
    worker.seed_corpus = Mock(return_value={})
    worker.state = Mock()
    monkeypatch.setattr(api, "binding", lambda row, spec: True)
    monkeypatch.setattr(api, "inventory", lambda path: {})
    worker.installer.stop.side_effect = lambda spec: assert_no_capture_events(worker)
    with pytest.raises(RuntimeError, match="Stop-in-tick window was not proved") as failure:
        worker.exercise()
    worker.installer.stop.assert_called_once_with(worker.spec)
    worker.state.assert_not_called()
    assert not any(call.args[0] == "stop_accepted_during_capture" for call in worker.event.call_args_list)
    assert_no_capture_events(worker)
    worker.flush_capture_observation(reason="control_or_phase_error", error=failure.value)
    assert worker.event.call_args.kwargs["reason"] == "control_or_phase_error"


def assert_no_capture_events(worker):
    assert not any(call.args[0] == "capture_wait" for call in worker.event.call_args_list)


def test_stop_and_interruption_flush_only_after_their_durable_phase_gates(api, monkeypatch, tmp_path):
    old = job("done", "old")
    first = status(old, reports=[{"id": "old"}])
    repeated = {**first, "checked_at": "next tick"}
    after_stop = status(old, job("done"), reports=[{"id": "old"}, {"id": "new"}])
    worker, _ = harness(api, monkeypatch, [first, repeated, status(old, job()), status(old, job()),
                                          after_stop, status(old, job("done"), job(operation_id="crash")),
                                          status(old, job("done"), job(operation_id="crash"))])
    worker.f = {"service_source": str(tmp_path)}
    worker.spec = object()
    worker.native = Mock()
    worker.native.query.return_value = {"exists": False}
    worker.installer = Mock()
    worker.installer.stop.side_effect = lambda spec: assert_no_capture_events(worker)
    worker.prepare_acl = Mock()
    worker.start = Mock(side_effect=[None, None, None, {"status": {"pid": 1234}},
                                    RuntimeError("after durable boundary")])
    worker.stop = Mock()
    worker.reported = Mock(return_value=first)
    worker.seed_corpus = Mock(return_value={})
    worker.state = Mock(return_value={"status": {"win32_exit": 0, "service_exit": 0}})
    worker.observer = Mock()
    worker.observer.locked.side_effect = lambda: nullcontext()
    def interrupt(pid):
        assert pid == 1234
        assert sum(call.args[0] == "capture_wait" for call in worker.event.call_args_list) == 1
        assert worker.status.call_count == 6
    worker.terminate_owned_running_process = Mock(side_effect=interrupt)
    changed = tmp_path / "CommonModules/ScmProbe0000/Ext/Module.bsl"
    changed.parent.mkdir(parents=True)
    changed.write_bytes(b"owned mock input")
    monkeypatch.setattr(api, "binding", lambda row, spec: True)
    monkeypatch.setattr(api, "inventory", lambda path: {})
    monkeypatch.setattr(api, "owned_scanner_pids", lambda: [])
    with pytest.raises(RuntimeError, match="after durable boundary"):
        worker.exercise()
    assert worker.pending_capture_observation is None
    assert worker.status.call_count == 7
    assert sum(call.args[0] == "capture_wait" for call in worker.event.call_args_list) == 2
