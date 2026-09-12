"""Durable findings use real project authorization and SQLite transactions."""

from dataclasses import replace
import json
import os
import sqlite3

import pytest

import rentgen_core as api
from rentgen_core import observer as implementation
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from project_access_test_support import force_legacy_membership

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows observer lock")
FIRST = Finding("rule", "Module.bsl", "procedure:a", "First", 1)
SECOND = Finding("rule", "Module.bsl", "procedure:b", "Second", 2)


@pytest.fixture
def observer(tmp_path):
    principal = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        principal, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    result = Observer(
        LocalRuntime(registry.path),
        principal,
        project.project_id,
        tmp_path / "observer",
    )
    result.initialize()
    return result


def report(observer, commit="a", findings=(FIRST,), **changes):
    ctx = observer._context(write=True)
    value = FindingReport(
        GitObservation(str(ctx.source_root.resolve()), commit * 40, "refs/heads/main"),
        "analyzer-v1",
        "whole-repository",
        True,
        findings,
    )
    return replace(value, **changes)


def revoke(observer, permissions):
    ctx = observer._context()
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, permissions)


def test_baseline_new_resolve_reopen_and_restart(observer):
    baseline = observer.record_findings(report(observer))
    assert baseline["baseline"] is True
    assert baseline["report"]["complete"] is True
    assert baseline["report"]["profile_id"] == "analyzer-v1"
    assert baseline["report"]["scope_id"] == "whole-repository"
    assert baseline["report"]["observation"]["commit"] == "a" * 40
    assert [event["kind"] for event in baseline["events"]] == ["new"]
    added = observer.record_findings(report(observer, "b", (FIRST, SECOND)))
    assert added["baseline"] is False
    assert [event["kind"] for event in added["events"]] == ["new"]
    resolved = observer.record_findings(report(observer, "c", (SECOND,)))
    assert [event["kind"] for event in resolved["events"]] == ["resolved"]
    restarted = Observer(
        observer.runtime, observer.principal, observer.project_id, observer.profile
    )
    reopened = restarted.record_findings(report(observer, "d", (FIRST, SECOND)))
    assert [event["kind"] for event in reopened["events"]] == ["reopened"]
    status = restarted.findings_status()
    assert len(status["reports"]) == 4
    assert status["state"]["records"][0]["first_seen"] == "a" * 40
    assert status["state"]["records"][0]["last_seen"] == "d" * 40


def test_replay_is_idempotent_even_after_later_commit(observer):
    first_report = report(observer, findings=(SECOND, FIRST))
    first = observer.record_findings(first_report)
    assert (
        observer.record_findings(replace(first_report, findings=(FIRST, SECOND)))
        == first
    )
    observer.record_findings(report(observer, "b", ()))
    before = observer.findings_status()
    assert observer.record_findings(first_report) == first
    assert observer.findings_status() == before
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(replace(first_report, findings=()))
    assert error.value.code == "FINDINGS_REPLAY_CONFLICT"
    assert observer.findings_status() == before


@pytest.mark.parametrize(
    "change,code",
    [
        ({"complete": False}, "FINDINGS_INCOMPLETE"),
        ({"profile_id": "other"}, "FINDINGS_CONTEXT_CHANGED"),
        ({"scope_id": "partial"}, "FINDINGS_CONTEXT_CHANGED"),
    ],
)
def test_invalid_context_never_closes_findings(observer, change, code):
    observer.record_findings(report(observer))
    before = observer.findings_status()
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(report(observer, "b", (), **change))
    assert error.value.code == code
    assert observer.findings_status() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("commit", ""),
        ("repository", ""),
        ("ref", ""),
        ("commit", "HEAD"),
        ("repository", "C:/unrelated"),
    ],
)
def test_report_requires_bound_provenance(observer, field, value):
    incoming = report(observer)
    incoming = replace(
        incoming, observation=replace(incoming.observation, **{field: value})
    )
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(incoming)
    assert error.value.code == "FINDINGS_CONTEXT_INVALID"
    assert observer.findings_status()["state"] is None


@pytest.mark.parametrize("permissions", [{"project:read"}, {"analysis:run"}])
def test_denied_access_prevents_write_and_read(observer, permissions):
    incoming = report(observer)
    revoke(observer, permissions)
    for operation in (
        lambda: observer.record_findings(incoming),
        observer.findings_status,
    ):
        with pytest.raises(api.CoreError) as error:
            operation()
        assert error.value.code == "PROJECT_FORBIDDEN"


def test_revocation_after_reconciliation_rolls_back(observer, monkeypatch):
    observer.record_findings(report(observer))
    incoming = report(observer, "b", ())

    def boundary(name):
        if name == "findings_ready":
            revoke(observer, {"project:read"})

    monkeypatch.setattr(implementation, "_boundary", boundary)
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(incoming)
    assert error.value.code == "PROJECT_FORBIDDEN"
    with sqlite3.connect(observer.database) as db:
        assert db.execute("SELECT count(*) FROM finding_reports").fetchone()[0] == 1
        assert (
            json.loads(db.execute("SELECT state FROM finding_state").fetchone()[0])[
                "records"
            ][0]["resolved_at"]
            is None
        )


@pytest.mark.parametrize("point", ["findings_state_saved", "findings_journal_saved"])
def test_transaction_failure_keeps_state_and_events_together(
    observer, monkeypatch, point
):
    observer.record_findings(report(observer))
    before = observer.findings_status()

    def crash(name):
        if name == point:
            raise KeyboardInterrupt("Simulated termination")

    monkeypatch.setattr(implementation, "_boundary", crash)
    with pytest.raises(KeyboardInterrupt):
        observer.record_findings(report(observer, "b", ()))
    assert observer.findings_status() == before
    monkeypatch.setattr(implementation, "_boundary", lambda name: None)
    assert (
        observer.record_findings(report(observer, "b", ()))["events"][0]["kind"]
        == "resolved"
    )


def test_old_profile_migrates_without_losing_source_jobs(observer):
    with sqlite3.connect(observer.database) as db:
        db.execute("DROP TABLE IF EXISTS finding_state")
        db.execute("DROP TABLE IF EXISTS finding_reports")
        db.execute("PRAGMA user_version=0")
        db.execute("UPDATE meta SET error='legacy-marker'")
    assert observer.findings_status()["state"] is None
    observer.record_findings(report(observer))
    with sqlite3.connect(observer.database) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert db.execute("SELECT error FROM meta").fetchone()[0] == "legacy-marker"
        assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0


def test_journal_limit_stops_without_pruning_and_still_allows_replay(
    observer, monkeypatch
):
    monkeypatch.setattr(implementation, "FINDINGS_MAX_REPORTS", 1)
    incoming = report(observer)
    first = observer.record_findings(incoming)
    before = observer.findings_status()
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(report(observer, "b", ()))
    assert error.value.code == "OBSERVER_JOURNAL_FULL"
    assert observer.findings_status() == before
    assert observer.record_findings(incoming) == first


def test_branch_change_requires_a_new_profile(observer):
    incoming = report(observer)
    observer.record_findings(incoming)
    before = observer.findings_status()
    changed = replace(
        incoming,
        observation=replace(
            incoming.observation, ref="refs/heads/other", commit="b" * 40
        ),
    )
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(changed)
    assert error.value.code == "FINDINGS_CONTEXT_CHANGED"
    assert observer.findings_status() == before


def test_status_reauthorizes_after_read(observer, monkeypatch):
    observer.record_findings(report(observer))

    def revoke_after_read(name):
        if name == "findings_status_ready":
            revoke(observer, {"project:read"})

    monkeypatch.setattr(implementation, "_boundary", revoke_after_read)
    with pytest.raises(api.CoreError) as error:
        observer.findings_status()
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_first_operation_failure_rolls_back_schema_migration(observer, monkeypatch):
    def crash(name):
        if name == "findings_state_saved":
            raise KeyboardInterrupt("First operation failed")

    monkeypatch.setattr(implementation, "_boundary", crash)
    with pytest.raises(KeyboardInterrupt):
        observer.record_findings(report(observer))
    with sqlite3.connect(observer.database) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 0
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'finding_%'"
            ).fetchall()
            == []
        )


def test_future_schema_is_rejected_without_modification(observer):
    incoming = report(observer)
    with sqlite3.connect(observer.database) as db:
        db.execute("PRAGMA user_version=99")
    for operation in (
        lambda: observer.record_findings(incoming),
        observer.findings_status,
    ):
        with pytest.raises(api.CoreError) as error:
            operation()
        assert error.value.code == "OBSERVER_SCHEMA_UNSUPPORTED"
    with sqlite3.connect(observer.database) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99


@pytest.mark.parametrize(
    "constant", ["FINDINGS_MAX_BYTES", "FINDINGS_MAX_DOCUMENT_BYTES"]
)
def test_byte_limit_retains_history(observer, monkeypatch, constant):
    observer.record_findings(report(observer))
    before = observer.findings_status()
    monkeypatch.setattr(implementation, constant, 1)
    with pytest.raises(api.CoreError) as error:
        observer.record_findings(report(observer, "b", ()))
    assert error.value.code == "OBSERVER_JOURNAL_FULL"
    assert observer.findings_status() == before


def test_status_marks_omitted_history_and_rejects_invalid_limit(observer):
    observer.record_findings(report(observer))
    observer.record_findings(report(observer, "b", ()))
    status = observer.findings_status(limit=1)
    assert len(status["reports"]) == 1
    assert status["reports_truncated"] is True
    for limit in (0, 101, True):
        with pytest.raises(api.CoreError) as error:
            observer.findings_status(limit=limit)
        assert error.value.code == "INVALID_QUERY_OPTIONS"
