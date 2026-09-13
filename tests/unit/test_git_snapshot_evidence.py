"""Git/source evidence uses real Git, publication and the confined two-pass probe."""
from dataclasses import replace
import json
import sqlite3

import pytest

from rentgen_core.errors import CoreError
from rentgen_core.git_observer import FindingReport, observe_git
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
import rentgen_core.observer as implementation
from rentgen_core.git_watcher import GitWatcher
from test_git_watcher import git
import test_project_core_publication as fixtures

scanner = fixtures.scanner
project = fixtures.project
pytestmark = fixtures.pytestmark


@pytest.fixture
def workspace(project, tmp_path):
    ctx, resolver, module, builder = project
    source = ctx.source_root
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.name", "Evidence test")
    git(source, "config", "user.email", "evidence@example.invalid")
    git(source, "add", ".")
    git(source, "commit", "-m", "baseline")
    observer = Observer(
        LocalRuntime(resolver.registry.path, resolver.graph_reader_factory, builder),
        ctx.principal,
        ctx.project_id,
        tmp_path / "observer",
    )
    observer.initialize()
    return observer, source, module


def verify(observer, observation):
    method = getattr(observer, "verify_git_snapshot", None)
    assert callable(method), "Observer must verify the Git/snapshot source binding"
    return method(observation)


def report(observation):
    return FindingReport(observation, "analyzer-v1", "whole-repository", True, ())


def test_no_snapshot_returns_explicit_unbound_status(workspace):
    observer, source, _ = workspace
    assert verify(observer, observe_git(source)) is None
    result = GitWatcher(observer, report).tick()
    assert result["snapshot_binding"] == "unbound_no_snapshot"


def test_verifier_matches_published_source_digest(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    evidence = verify(observer, observation)
    from rentgen_core.git_snapshot_evidence import GitSnapshotEvidence

    assert isinstance(evidence, GitSnapshotEvidence)
    assert evidence.snapshot_id == snapshot
    assert evidence.observation == observation
    assert evidence.project_id == observer.project_id
    with observer._context().state.transaction(observer.principal) as tx:
        assert evidence.source_digest == tx.get_snapshot(snapshot).source_digest


def test_snapshot_source_mismatch_fails_before_analysis(workspace):
    observer, source, module = workspace
    observer.tick()
    module.write_text("changed\n", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "changed")
    calls = []
    with pytest.raises(CoreError) as error:
        GitWatcher(observer, lambda observation: calls.append(observation)).tick()
    assert error.value.code == "GIT_SNAPSHOT_MISMATCH"
    assert calls == []
    assert observer.findings_status()["state"] is None


def test_verifier_rejects_other_repository(workspace):
    observer, source, _ = workspace
    with pytest.raises(CoreError) as error:
        verify(observer, replace(observe_git(source), repository=str(source.parent)))
    assert error.value.code == "GIT_SNAPSHOT_CONTEXT"


@pytest.mark.parametrize("when", ["before", "after"])
def test_verifier_rejects_head_race(workspace, monkeypatch, when):
    observer, source, _ = workspace
    observation = observe_git(source)
    changed = replace(observation, commit="f" * 40)
    values = iter(
        (changed, observation) if when == "before" else (observation, changed)
    )
    monkeypatch.setattr(
        implementation, "observe_git", lambda _: next(values), raising=False
    )
    with pytest.raises(CoreError) as error:
        verify(observer, observation)
    assert error.value.code == "GIT_HEAD_CHANGED"


def test_unstable_probe_never_issues_evidence(workspace, monkeypatch):
    observer, source, _ = workspace

    def unstable(_):
        raise CoreError("SOURCE_CAPTURE_CHANGED", "test race")

    monkeypatch.setattr(implementation, "probe_sources", unstable)
    with pytest.raises(CoreError) as error:
        verify(observer, observe_git(source))
    assert error.value.code == "SOURCE_CAPTURE_CHANGED"


def test_evidence_persists_replays_and_marks_owner_report(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    evidence = verify(observer, observation)
    first = observer.record_findings(report(observation), evidence=evidence)
    restarted = Observer(
        observer.runtime, observer.principal, observer.project_id, observer.profile
    )
    git(source, "commit", "--allow-empty", "-m", "later")
    assert restarted.record_findings(report(observation), evidence=evidence) == first
    with sqlite3.connect(observer.database) as db:
        assert db.execute("SELECT count(*) FROM git_snapshot_evidence").fetchone() == (
            1,
        )
    owner = restarted.owner_report(snapshot)
    assert owner["quality"]["provenance"] == "git_source_verified"
    assert owner["business_metrics"]["status"] == "not_available"


def test_manual_binding_stays_caller_asserted_after_legacy_migration(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    first = observer.record_findings(report(observation), snapshot_id=snapshot)
    with sqlite3.connect(observer.database) as db:
        db.execute("DROP TABLE IF EXISTS git_snapshot_evidence")
        db.execute("PRAGMA user_version=1")
    assert observer.owner_report(snapshot)["quality"]["provenance"] == "caller_asserted"
    assert observer.record_findings(report(observation), snapshot_id=snapshot) == first
    assert observer.findings_status()["reports"] == [first]
    assert observer.owner_report(snapshot)["quality"]["provenance"] == "caller_asserted"


def test_evidence_conflict_and_corruption_fail_closed(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    evidence = verify(observer, observation)
    observer.record_findings(report(observation), evidence=evidence)
    with pytest.raises(CoreError):
        observer.record_findings(
            report(observation), evidence=replace(evidence, source_digest="f" * 64)
        )
    with sqlite3.connect(observer.database) as db:
        db.execute("UPDATE git_snapshot_evidence SET evidence=?", ("{}",))
    with pytest.raises(CoreError) as error:
        observer.owner_report(snapshot)
    assert error.value.code == "GIT_SNAPSHOT_EVIDENCE_INVALID"


def test_watcher_passes_verified_evidence_after_analysis(workspace, monkeypatch):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    original = observer.record_findings
    received = []

    def record(value, **kwargs):
        received.append(kwargs.get("evidence"))
        return original(value, **kwargs)

    monkeypatch.setattr(observer, "record_findings", record)
    result = GitWatcher(observer, report).tick()
    assert received and received[0] is not None
    assert received[0].snapshot_id == snapshot
    assert result["snapshot_binding"] == "git_source_verified"
    assert (
        observer.owner_report(snapshot)["quality"]["provenance"]
        == "git_source_verified"
    )


@pytest.mark.parametrize(
    "limit_name",
    ["MAX_EVIDENCE_ROWS", "MAX_EVIDENCE_BYTES", "MAX_EVIDENCE_TOTAL_BYTES"],
)
def test_evidence_limits_roll_back_new_findings(workspace, monkeypatch, limit_name):
    import rentgen_core.git_snapshot_evidence as evidence_impl

    observer, source, _ = workspace
    observer.tick()
    observation = observe_git(source)
    evidence = verify(observer, observation)
    monkeypatch.setattr(evidence_impl, limit_name, 0)
    with pytest.raises(CoreError) as error:
        observer.record_findings(report(observation), evidence=evidence)
    assert error.value.code == "OBSERVER_JOURNAL_FULL"
    assert observer.findings_status()["state"] is None


def test_missing_v2_evidence_schema_fails_closed_without_losing_receipts(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    first = observer.record_findings(
        report(observation), evidence=verify(observer, observation)
    )
    with sqlite3.connect(observer.database) as db:
        db.execute("DROP TABLE git_snapshot_evidence")
    with pytest.raises(CoreError) as error:
        observer.owner_report(snapshot)
    assert error.value.code == "OBSERVER_SCHEMA_UNSUPPORTED"
    with sqlite3.connect(observer.database) as db:
        assert (
            json.loads(db.execute("SELECT receipt FROM finding_reports").fetchone()[0])
            == first
        )


def test_foreign_legacy_evidence_table_migration_rolls_back(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    first = observer.record_findings(report(observation), snapshot_id=snapshot)
    with sqlite3.connect(observer.database) as db:
        db.execute("DROP TABLE git_snapshot_evidence")
        db.execute("CREATE TABLE git_snapshot_evidence (foreign_data TEXT)")
        db.execute("PRAGMA user_version=1")
    with pytest.raises(CoreError) as error:
        observer.record_findings(report(observation), snapshot_id=snapshot)
    assert error.value.code == "OBSERVER_SCHEMA_UNSUPPORTED"
    with sqlite3.connect(observer.database) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (1,)
        assert (
            json.loads(db.execute("SELECT receipt FROM finding_reports").fetchone()[0])
            == first
        )


def test_source_change_during_analyzer_cannot_bind_snapshot(workspace):
    observer, _, module = workspace
    snapshot = observer.tick()["snapshot_id"]

    def analyzer(observation):
        module.write_text("changed during analysis\n", encoding="utf-8")
        return report(observation)

    with pytest.raises(CoreError) as error:
        GitWatcher(observer, analyzer).tick()
    assert error.value.code == "GIT_TRACKED_DIRTY"
    assert observer.owner_report(snapshot)["quality"]["status"] == "not_available"


def test_inconsistent_persisted_evidence_never_gets_verified_marker(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    evidence = verify(observer, observation)
    observer.record_findings(report(observation), evidence=evidence)
    with sqlite3.connect(observer.database) as db:
        raw = json.loads(
            db.execute("SELECT evidence FROM git_snapshot_evidence").fetchone()[0]
        )
        raw["source_digest"] = "e" * 64
        db.execute("UPDATE git_snapshot_evidence SET evidence=?", (json.dumps(raw),))
    with pytest.raises(CoreError) as error:
        observer.owner_report(snapshot)
    assert error.value.code == "GIT_SNAPSHOT_EVIDENCE_INVALID"


def test_legacy_version_cannot_promote_an_unversioned_evidence_table(workspace):
    observer, source, _ = workspace
    snapshot = observer.tick()["snapshot_id"]
    observation = observe_git(source)
    observer.record_findings(
        report(observation), evidence=verify(observer, observation)
    )
    with sqlite3.connect(observer.database) as db:
        db.execute("PRAGMA user_version=1")
    with pytest.raises(CoreError) as error:
        observer.owner_report(snapshot)
    assert error.value.code == "OBSERVER_SCHEMA_UNSUPPORTED"
    with pytest.raises(CoreError) as error:
        observer.record_findings(report(observation), snapshot_id=snapshot)
    assert error.value.code == "OBSERVER_SCHEMA_UNSUPPORTED"
