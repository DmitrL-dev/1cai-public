"""Caller-supplied findings CLI exercises real authorization and persistence."""

from dataclasses import asdict
import json
import os

import pytest

import rentgen_core as api
from rentgen_core import observer_cli as cli
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from project_access_test_support import force_legacy_membership

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows observer lock")


@pytest.fixture
def command(tmp_path, monkeypatch, capsys):
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    observer = Observer(
        LocalRuntime(registry.path),
        principal,
        project.project_id,
        tmp_path / "observer",
    )
    observer.initialize()
    monkeypatch.setattr(cli, "current_windows_principal", lambda: principal)

    def forbidden(*args, **kwargs):
        pytest.fail("Findings CLI must not start a watcher, capture or analyzer")

    monkeypatch.setattr(Observer, "_tick", forbidden)
    monkeypatch.setattr(cli.time, "sleep", forbidden)

    def invoke(action, *args):
        code = cli.main(
            [
                action,
                "--registry",
                str(registry.path),
                "--project",
                project.project_id,
                "--profile",
                str(observer.profile),
                *args,
            ]
        )
        output = capsys.readouterr().out
        assert len(output.encode("utf-8")) <= 2 * 1024 * 1024
        return code, json.loads(output)

    return observer, invoke


def report_file(observer, tmp_path, commit="a", anchors=("a",)):
    report = FindingReport(
        GitObservation(
            str(observer._context().source_root.resolve()),
            commit * 40,
            "refs/heads/main",
        ),
        "analyzer-v1",
        "whole-repository",
        True,
        tuple(
            Finding("rule", "Module.bsl", anchor, "Сообщение", 1) for anchor in anchors
        ),
    )
    path = tmp_path / f"report-{commit}.json"
    path.write_text(json.dumps(asdict(report), ensure_ascii=False), encoding="utf-8")
    return path


def test_baseline_new_resolve_and_historical_replay(command, tmp_path):
    observer, invoke = command
    first = report_file(observer, tmp_path)
    code, baseline = invoke("record-findings", "--report", str(first))
    assert code == 0
    assert baseline["result"]["baseline"] is True
    assert baseline["result"]["analysis"] == "caller_supplied"
    assert baseline["result"]["model_calls"] == 0
    assert [e["kind"] for e in baseline["result"]["events"]] == ["new"]
    for commit, anchors, event in (("b", ("a", "b"), "new"), ("c", ("b",), "resolved")):
        path = report_file(observer, tmp_path, commit, anchors)
        code, result = invoke("record-findings", "--report", str(path))
        assert code == 0
        assert [e["kind"] for e in result["result"]["events"]] == [event]
    before = observer.findings_status()
    assert invoke("record-findings", "--report", str(first)) == (0, baseline)
    assert observer.findings_status() == before
    path = report_file(observer, tmp_path, "a", ())
    assert (
        invoke("record-findings", "--report", str(path))[1]["error"]["code"]
        == "FINDINGS_REPLAY_CONFLICT"
    )


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"complete": False}, "FINDINGS_INCOMPLETE"),
        ({"profile_id": "other"}, "FINDINGS_CONTEXT_CHANGED"),
        ({"scope_id": "other"}, "FINDINGS_CONTEXT_CHANGED"),
    ],
)
def test_rejected_reports_leave_state_unchanged(command, tmp_path, change, expected):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    assert invoke("record-findings", "--report", str(path))[0] == 0
    before = observer.findings_status()
    path = report_file(observer, tmp_path, "b", ())
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(change)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, result = invoke("record-findings", "--report", str(path))
    assert code == 2
    assert result["error"]["code"] == expected
    assert observer.findings_status() == before


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"{}{}",
        b'{"a":1,"a":2}',
        b'{"nested":{"a":1,"a":2}}',
        b'{"a":NaN}',
        b'"\xff"',
        b"\xef\xbb\xbf{}",
        b'"\\ud800"',
        b"[" * 1500,
        b" " * (1024 * 1024 + 1),
        b"[]",
    ],
    ids=[
        "syntax",
        "trailing",
        "duplicate",
        "nested-duplicate",
        "nan",
        "utf8",
        "bom",
        "surrogate",
        "depth",
        "oversize",
        "array",
    ],
)
def test_invalid_json_and_oversize_are_bounded_errors(command, tmp_path, raw):
    observer, invoke = command
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    code, result = invoke("record-findings", "--report", str(path))
    assert code == 2
    assert result["error"]["code"] == "INVALID_ARGUMENT"
    assert observer.findings_status()["state"] is None


@pytest.mark.parametrize(
    "change, expected",
    [
        ({"extra": 1}, "INVALID_ARGUMENT"),
        ({"findings": {}}, "INVALID_ARGUMENT"),
        ({"findings": [None]}, "INVALID_ARGUMENT"),
        ({"observation": None}, "INVALID_ARGUMENT"),
        ({"profile_id": []}, "FINDINGS_CONTEXT_INVALID"),
        ({"complete": 1}, "FINDINGS_INCOMPLETE"),
    ],
)
def test_dto_validation(command, tmp_path, change, expected):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(change)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, result = invoke("record-findings", "--report", str(path))
    assert code == 2
    assert result["error"]["code"] == expected
    assert observer.findings_status()["state"] is None


@pytest.mark.parametrize(
    "field, value", [("commit", "HEAD"), ("repository", "wrong"), ("ref", "")]
)
def test_provenance_validation(command, tmp_path, field, value):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["observation"][field] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    code, result = invoke("record-findings", "--report", str(path))
    assert code == 2
    assert result["error"]["code"] == "FINDINGS_CONTEXT_INVALID"


@pytest.mark.parametrize("permissions", [{"project:read"}, {"analysis:run"}])
def test_denied_access_for_record_and_status(command, tmp_path, permissions):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    ctx = observer._context()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, permissions)
    for action, args in (
        ("record-findings", ("--report", str(path))),
        ("findings-status", ()),
    ):
        code, result = invoke(action, *args)
        assert code == 2
        assert result["error"]["code"] == "PROJECT_FORBIDDEN"


def test_status_limit_and_legacy_status(command, tmp_path):
    observer, invoke = command
    for commit in ("a", "b"):
        path = report_file(observer, tmp_path, commit)
        assert invoke("record-findings", "--report", str(path))[0] == 0
    code, result = invoke("findings-status", "--limit", "1")
    assert code == 0
    assert len(result["result"]["reports"]) == 1
    assert result["result"]["reports_truncated"] is True
    for limit in ("0", "101"):
        code, result = invoke("findings-status", "--limit", limit)
        assert code == 2
        assert result["error"]["code"] == "INVALID_QUERY_OPTIONS"
    assert invoke("status")[0] == 0
    assert observer.status()["reports"] == []


def test_record_requires_report_and_status_rejects_report(command, tmp_path):
    _, invoke = command
    for action, args in (
        ("record-findings", ()),
        ("findings-status", ("--report", str(tmp_path / "x"))),
    ):
        code, result = invoke(action, *args)
        assert code == 2
        assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_snapshot_id_is_only_for_record_and_requires_published_snapshot(
    command, tmp_path
):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    code, result = invoke(
        "record-findings",
        "--report",
        str(path),
        "--snapshot-id",
        "b" * 64,
    )
    assert code == 2
    assert result["error"]["code"] == "SNAPSHOT_NOT_FOUND"

    code, result = invoke("status", "--snapshot-id", "b" * 64)
    assert code == 2
    assert result["error"]["code"] == "INVALID_ARGUMENT"


def test_status_reauthorizes_analysis_permission_after_encoding(
    command, tmp_path, monkeypatch
):
    observer, invoke = command
    path = report_file(observer, tmp_path)
    assert invoke("record-findings", "--report", str(path))[0] == 0
    real = cli.json.dumps

    def revoke(value, *args, **kwargs):
        encoded = real(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value:
            ctx = observer._context()
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, {"project:read"})
        return encoded

    monkeypatch.setattr(cli.json, "dumps", revoke)
    code, result = invoke("findings-status")
    assert code == 2
    assert result["error"]["code"] == "PROJECT_FORBIDDEN"


def test_status_response_size_limit(command, monkeypatch):
    _, invoke = command
    monkeypatch.setattr(
        Observer,
        "findings_status",
        lambda self, **kwargs: {"state": "x" * (2 * 1024 * 1024)},
    )
    code, result = invoke("findings-status")
    assert code == 2
    assert result["error"]["code"] == "OBSERVER_RESPONSE_LIMIT"
