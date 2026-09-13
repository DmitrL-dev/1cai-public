"""Git service composition contracts; no SCM or native BSL process is started."""

import json
import os
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from rentgen_core import service_entry
from rentgen_core.errors import CoreError
from rentgen_core.git_watcher import NotificationOutbox, SchedulerJournal
from rentgen_core.owner_report_store import OwnerReportStore
from test_git_bsl_analyzer import FakeAdapter
import test_git_snapshot_evidence as evidence_fixtures


scanner = evidence_fixtures.scanner
project = evidence_fixtures.project
workspace = evidence_fixtures.workspace
pytestmark = evidence_fixtures.pytestmark


@pytest.fixture
def configured(tmp_path):
    registry = tmp_path / "empty-registry.sqlite3"
    registry.touch()
    profile = tmp_path / "profile"
    profile.mkdir()
    diagnostics = tmp_path / "diagnostics"
    diagnostics.mkdir()
    document = {
        "schema": 2,
        "service_name": "Rentgen.GitAudit",
        "registry": str(registry),
        "profile": str(profile),
        "project": "6e461c4d-e19c-4e37-85b3-3aa0961580b7",
        "diagnostics_root": str(diagnostics),
        "interval_seconds": 5,
    }
    path = tmp_path / "git-service.json"

    def write(**updates):
        path.write_text(json.dumps(document | updates), encoding="utf-8")
        return path

    write()
    return SimpleNamespace(path=path, document=document, write=write)


def test_git_config_defaults_to_dry_run_without_worker_or_writes(configured):
    config = service_entry.load_config(configured.path)
    assert (config.mode, config.max_cycles) == ("dry-run", 1)
    result = service_entry.run_console(
        configured.path, worker_factory=lambda _: pytest.fail("dry run started worker")
    )
    assert (result.exit_code, result.cycles) == (0, 0)
    assert list(config.profile.iterdir()) == []


@pytest.mark.parametrize(
    "updates",
    [
        {"mode": "apply"},
        {"mode": "live"},
        {"max_cycles": None},
        {"max_cycles": 0},
        {"max_cycles": 10001},
        {"max_cycles": True},
        {"interval_seconds": 4},
        {"interval_seconds": 86401},
        {"scanner": "arbitrary.exe"},
        {"factory": "arbitrary.module"},
        {"diagnostics_root": "relative"},
    ],
)
def test_git_config_rejects_incomplete_or_unlisted_settings(configured, updates):
    configured.write(**updates)
    with pytest.raises(CoreError) as error:
        service_entry.load_config(configured.path)
    assert error.value.code == "SERVICE_CONFIG_INVALID"


def test_git_config_requires_diagnostics_root(configured):
    document = dict(configured.document)
    del document["diagnostics_root"]
    configured.path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(CoreError) as error:
        service_entry.load_config(configured.path)
    assert error.value.code == "SERVICE_CONFIG_INVALID"


def wire(configured, workspace, monkeypatch, *, adapter=None, publish=True):
    observer, source, module = workspace
    snapshot = observer.tick()["snapshot_id"] if publish else None
    configured.write(
        mode="read-only",
        registry=str(observer.runtime.registry.path),
        profile=str(observer.profile),
        project=observer.project_id,
    )
    import rentgen_core.local_identity as identity
    import rentgen_diagnostics.installed as installed

    adapter = adapter or FakeAdapter()
    monkeypatch.setattr(
        identity, "current_windows_principal", lambda: observer.principal
    )
    monkeypatch.setattr(
        installed,
        "InstalledDiagnostics",
        lambda **kwargs: SimpleNamespace(for_profile=lambda profile_id: adapter),
    )
    return observer, source, module, snapshot, adapter


@pytest.mark.parametrize("mode", ["console", "mocked_scm"])
def test_service_entry_wires_durable_git_findings_outbox_and_owner_report(
    configured, workspace, monkeypatch, mode
):
    observer, source, module, snapshot, adapter = wire(
        configured, workspace, monkeypatch
    )
    original = module.read_bytes()
    if mode == "console":
        result = service_entry.run_console(configured.path)
    else:
        from test_service_entry import SCM, states

        class GitSCM(SCM):
            def dispatch(self, callback):
                callback("Rentgen.GitAudit", True)

            def register(self, name, handler):
                assert name == "Rentgen.GitAudit"
                self.handler = handler
                return 123

        scm = GitSCM()
        result = service_entry.NativeService(configured.path, scm=scm).run()
        assert states(scm) == [
            service_entry.START_PENDING,
            service_entry.RUNNING,
            service_entry.STOP_PENDING,
            service_entry.STOPPED,
        ]

    assert (result.exit_code, result.cycles) == (0, 1)
    assert adapter.calls
    assert module.read_bytes() == original
    state = observer.findings_status()["state"]
    notifications = NotificationOutbox(observer.profile / "git-outbox.json").peek()
    event = notifications[0]["event"]
    assert event["status"] == "analyzed"
    assert event["commit"] == state["report"]["observation"]["commit"]
    store = OwnerReportStore(
        observer.runtime.registry.get(observer.project_id).state_root / "owner-reports"
    )
    receipt = store.get(
        event["owner_report_id"],
        expected_project_id=observer.project_id,
        expected_snapshot_id=snapshot,
        authorize=lambda: observer._context(write=True),
    )
    assert receipt["report"]["quality"]["provenance"] == "git_source_verified"
    assert receipt["report"]["business_metrics"]["status"] == "not_available"
    assert (
        SchedulerJournal(observer.profile / "git-journal.json").read()["phase"]
        == "idle"
    )


def test_git_output_paths_cannot_resolve_into_source(
    configured, workspace, monkeypatch
):
    observer, _, module, _, adapter = wire(configured, workspace, monkeypatch)
    original = module.read_bytes()
    path = observer.profile / "git-journal.json"
    # Model an existing redirected leaf without requiring Windows symlink rights.
    resolve = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda self, *args, **kwargs: resolve(
            module if self == path else self, *args, **kwargs
        ),
    )
    with pytest.raises(CoreError) as error:
        worker = service_entry.create_worker(service_entry.load_config(configured.path))
        worker.close()
    assert error.value.code == "SERVICE_CONFIG_INVALID"
    assert adapter.calls == []
    assert module.read_bytes() == original


@pytest.mark.parametrize("name", ["git-outbox.json.lock", "git-journal.json.lock"])
def test_git_auxiliary_hardlink_is_rejected_before_unrelated_file_write(
    configured, workspace, monkeypatch, name, tmp_path
):
    observer, _, _, _, adapter = wire(configured, workspace, monkeypatch)
    unrelated = tmp_path / "unrelated-empty.txt"
    unrelated.touch()
    os.link(unrelated, observer.profile / name)

    result = service_entry.run_console(configured.path)

    assert unrelated.read_bytes() == b""
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert adapter.calls == []
    assert not (observer.profile / "git-journal.json").exists()
    assert not (observer.profile / "git-outbox.json").exists()


@pytest.mark.parametrize("boundary", ["worker", "entrypoint"])
def test_exhausted_budget_after_retryable_error_fails_the_service(
    configured, workspace, monkeypatch, boundary
):
    observer, _, module, _, adapter = wire(configured, workspace, monkeypatch)
    module.write_bytes(module.read_bytes() + b"// dirty tracked file\n")

    if boundary == "worker":
        worker = service_entry.create_worker(service_entry.load_config(configured.path))
        try:
            with pytest.raises(CoreError) as error:
                worker.run(Event())
            assert error.value.code == "GIT_TRACKED_DIRTY"
        finally:
            worker.close()
    else:
        result = service_entry.run_console(configured.path)
        assert (result.exit_code, result.error_code) == (2, "SERVICE_WORKER_FAILED")

    assert adapter.calls == []
    events = NotificationOutbox(observer.profile / "git-outbox.json").peek()
    assert [item["event"] for item in events] == [
        {"status": "error", "code": "GIT_TRACKED_DIRTY", "attempt": 1}
    ]
    with observer.locked():
        pass


@pytest.mark.parametrize("failure", ["missing_snapshot", "incomplete_analysis"])
def test_incomplete_evidence_never_publishes_findings_or_success_notification(
    configured, workspace, monkeypatch, failure
):
    adapter = FakeAdapter(complete=failure != "incomplete_analysis")
    observer, _, _, _, _ = wire(
        configured,
        workspace,
        monkeypatch,
        adapter=adapter,
        publish=failure != "missing_snapshot",
    )
    result = service_entry.run_console(configured.path)
    assert result.error_code == "SERVICE_WORKER_FAILED"
    assert observer.findings_status()["state"] is None
    events = NotificationOutbox(observer.profile / "git-outbox.json").peek()
    assert [item["event"]["status"] for item in events] == ["fatal"]
    if failure == "missing_snapshot":
        assert adapter.calls == []


def test_git_worker_stop_finishes_active_cycle_and_prevents_later_ticks(
    configured, workspace, monkeypatch
):
    entered, release, stop = Event(), Event(), Event()

    class BlockingAdapter(FakeAdapter):
        def analyze(self, *args, **kwargs):
            entered.set()
            assert release.wait(10)
            return super().analyze(*args, **kwargs)

    observer, _, _, _, adapter = wire(
        configured, workspace, monkeypatch, adapter=BlockingAdapter()
    )
    document = json.loads(configured.path.read_text(encoding="utf-8"))
    document.update(max_cycles=100, interval_seconds=86400)
    configured.path.write_text(json.dumps(document), encoding="utf-8")
    results = []
    thread = Thread(
        target=lambda: results.append(
            service_entry.run_console(configured.path, stop_event=stop)
        )
    )
    thread.start()
    try:
        assert entered.wait(10)
        stop.set()
        release.set()
        thread.join(10)
        assert not thread.is_alive()
    finally:
        stop.set()
        release.set()
        thread.join(10)
    assert (results[0].exit_code, results[0].cycles) == (0, 1)
    assert len(adapter.calls) == 1
    with observer.locked():
        pass
    assert (
        SchedulerJournal(observer.profile / "git-journal.json").read()["phase"]
        == "idle"
    )
