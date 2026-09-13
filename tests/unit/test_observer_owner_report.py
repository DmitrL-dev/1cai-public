"""Observer turns durable findings into an evidence-bound owner report."""

import os
import sqlite3

import pytest

import rentgen_core as api
import rentgen_core.observer as observer_impl
import rentgen_core.owner_report as owner_report_impl
from rentgen_core.git_observer import Finding, FindingReport, GitObservation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from project_access_test_support import force_legacy_membership


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows observer lock")


@pytest.fixture
def observer(tmp_path):
    owner = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    project = registry.register(
        owner, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    snapshot = "b" * 64
    with sqlite3.connect(project.state_root / "state.sqlite3") as connection:
        connection.execute(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project.project_id,
                snapshot,
                snapshot,
                "a" * 64,
                "a" * 64,
                "generations/" + snapshot,
                1,
                "2026-09-13T00:00:00+00:00",
            ),
        )
    value = Observer(
        LocalRuntime(registry.path), owner, project.project_id, tmp_path / "observer"
    )
    value.initialize()
    return value, snapshot, source


def publish_snapshot(value, snapshot):
    project = value.runtime.registry.get(value.project_id)
    with sqlite3.connect(project.state_root / "state.sqlite3") as connection:
        connection.execute(
            "INSERT INTO snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project.project_id,
                snapshot,
                snapshot,
                "a" * 64,
                "c" * 64,
                "generations/" + snapshot,
                1,
                "2026-09-13T00:00:00+00:00",
            ),
        )


def test_owner_report_reads_durable_findings_and_keeps_runtime_unavailable(observer):
    value, snapshot, source = observer
    value.record_findings(
        FindingReport(
            GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
            "bsl-ls",
            "whole-repository",
            True,
            (Finding("rule", "Module.bsl", "anchor", "Message", 4),),
        ),
        snapshot_id=snapshot,
    )

    report = value.owner_report(snapshot)

    assert report["project_id"] == value.project_id
    assert report["snapshot_id"] == snapshot
    assert report["quality"]["status"] == "available"
    assert report["quality"]["open"] == 1
    assert report["business_metrics"] == {
        "status": "not_available",
        "reason": "runtime_adapter_not_configured",
    }


def test_owner_report_without_explicit_binding_is_unavailable(observer):
    value, snapshot, source = observer
    value.record_findings(
        FindingReport(
            GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
            "bsl-ls",
            "whole-repository",
            True,
            (Finding("rule", "Module.bsl", "anchor", "Message", 4),),
        )
    )

    report = value.owner_report(snapshot)

    assert report["quality"] == {
        "status": "not_available",
        "reason": "quality_snapshot_binding_unverified",
    }


def test_owner_report_without_findings_is_explicitly_unavailable(observer):
    value, snapshot, _ = observer

    report = value.owner_report(snapshot)

    assert report["quality"] == {
        "status": "not_available",
        "reason": "quality_analysis_not_configured",
    }


def test_owner_report_rejects_unpublished_snapshot_before_reading_findings(observer):
    value, _, _ = observer

    with pytest.raises(api.CoreError) as error:
        value.owner_report("c" * 64)

    assert error.value.code == "SNAPSHOT_NOT_FOUND"


def test_owner_report_reauthorizes_after_build(observer, monkeypatch):
    value, snapshot, _ = observer
    original = owner_report_impl.build_owner_report

    def revoke_during_build(*args, **kwargs):
        ctx = value._context()
        with ctx.state.transaction(ctx.principal, write=True) as tx:
            force_legacy_membership(tx, ctx.principal, {"project:read"})
        return original(*args, **kwargs)

    monkeypatch.setattr(owner_report_impl, "build_owner_report", revoke_during_build)
    with pytest.raises(api.CoreError) as error:
        value.owner_report(snapshot)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_owner_report_exposes_history_bound_as_explicit_parameter(observer):
    value, snapshot, source = observer
    findings = tuple(
        Finding("rule", f"Module{i}.bsl", f"anchor-{i}", "Message", i + 1)
        for i in range(1001)
    )
    value.record_findings(
        FindingReport(
            GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
            "bsl-ls",
            "whole-repository",
            True,
            findings,
        ),
        snapshot_id=snapshot,
    )

    with pytest.raises(api.CoreError) as error:
        value.owner_report(snapshot)
    assert error.value.code == "OWNER_REPORT_LIMIT"

    report = value.owner_report(snapshot, max_findings=1001)
    assert report["quality"]["status"] == "available"
    assert report["quality"]["total"] == 1001


def test_historical_replay_does_not_move_current_snapshot_binding(observer):
    value, snapshot_a, source = observer
    snapshot_b = "c" * 64
    publish_snapshot(value, snapshot_b)
    report_a = FindingReport(
        GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
        "bsl-ls",
        "whole-repository",
        True,
        (Finding("rule", "A.bsl", "a", "A", 1),),
    )
    report_b = FindingReport(
        GitObservation(str(source.resolve()), "b" * 40, "refs/heads/main"),
        "bsl-ls",
        "whole-repository",
        True,
        (Finding("rule", "B.bsl", "b", "B", 1),),
    )

    value.record_findings(report_a)
    value.record_findings(report_b)
    value.record_findings(report_a, snapshot_id=snapshot_a)
    assert value.owner_report(snapshot_b)["quality"]["reason"] == (
        "quality_snapshot_binding_unverified"
    )

    value.record_findings(report_b, snapshot_id=snapshot_b)
    value.record_findings(report_a, snapshot_id=snapshot_a)
    assert value.owner_report(snapshot_a)["quality"]["reason"] == (
        "quality_snapshot_binding_unverified"
    )
    report = value.owner_report(snapshot_b)
    assert report["quality"]["status"] == "available"
    assert report["quality"]["commit"] == "b" * 40


def test_snapshot_binding_rolls_back_with_finding_transaction(observer, monkeypatch):
    value, snapshot, source = observer
    incoming = FindingReport(
        GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
        "bsl-ls",
        "whole-repository",
        True,
        (Finding("rule", "Module.bsl", "anchor", "Message", 4),),
    )

    def crash(name):
        if name == "findings_journal_saved":
            raise RuntimeError("injected")

    monkeypatch.setattr(observer_impl, "_boundary", crash)
    with pytest.raises(RuntimeError):
        value.record_findings(incoming, snapshot_id=snapshot)
    monkeypatch.setattr(observer_impl, "_boundary", lambda name: None)
    assert value.owner_report(snapshot)["quality"]["reason"] == (
        "quality_analysis_not_configured"
    )

    value.record_findings(incoming, snapshot_id=snapshot)
    assert value.owner_report(snapshot)["quality"]["status"] == "available"


def test_legacy_findings_schema_without_binding_fails_closed(observer):
    value, snapshot, source = observer
    value.record_findings(
        FindingReport(
            GitObservation(str(source.resolve()), "a" * 40, "refs/heads/main"),
            "bsl-ls",
            "whole-repository",
            True,
            (Finding("rule", "Module.bsl", "anchor", "Message", 4),),
        )
    )
    with sqlite3.connect(value.database) as connection:
        connection.execute("DROP TABLE finding_binding")

    report = value.owner_report(snapshot)
    assert report["quality"] == {
        "status": "not_available",
        "reason": "quality_snapshot_binding_unverified",
    }
