"""Real Windows source capture, persistent observer state and receipt recovery."""
import os

import pytest

import rentgen_core as api
import rentgen_core.observer as implementation
from rentgen_core.local import LocalRuntime
from rentgen_core.observer import Observer
from rentgen_core.source_probe import probe_sources
from project_access_test_support import force_legacy_membership
import test_project_core_publication as fixtures

project = fixtures.project
scanner = fixtures.scanner
pytestmark = fixtures.pytestmark


@pytest.fixture
def observer(project, tmp_path):
    ctx, resolver, _, builder = project

    class Counted:
        calls = 0

        def build(self, *args, **kwargs):
            self.calls += 1
            return builder.build(*args, **kwargs)

    runtime = LocalRuntime(
        resolver.registry.path, resolver.graph_reader_factory, Counted()
    )
    result = Observer(runtime, ctx.principal, ctx.project_id, tmp_path / "observer")
    result.initialize()
    return result


def test_probe_matches_published_digest_and_unchanged_ticks_do_not_build(
    observer, project
):
    ctx = project[0]
    source_hash = probe_sources(ctx)[1]
    assert not (ctx.state.path.parent / "generations").exists()
    first = observer.tick()
    assert first["status"] == "reported"
    with ctx.state.transaction(ctx.principal) as tx:
        catalog = tx.get_snapshot(first["snapshot_id"])
    assert source_hash == catalog.source_digest
    generations = list((ctx.state.path.parent / "generations").iterdir())
    assert observer.tick()["status"] == "unchanged"
    assert observer.tick()["status"] == "unchanged"
    assert observer.runtime.graph_builder.calls == 1
    assert list((ctx.state.path.parent / "generations").iterdir()) == generations
    status = observer.status()
    assert len(status["jobs"]) == len(status["reports"]) == 1
    assert status["reports"][0]["changes"]["kind"] == "baseline"
    assert status["reports"][0]["quality"]["status"] == "not_run"


def test_same_size_and_mtime_change_is_captured_and_reported(observer, project):
    observer.tick()
    module = project[2]
    stamp = module.stat()
    module.write_bytes(module.read_bytes().replace(b"1", b"2"))
    os.utime(module, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert observer.tick()["status"] == "reported"
    report = observer.status()["reports"][0]
    assert report["changes"]["counts"]["modified"] == 1
    assert report["before"] != report["after"]
    assert observer.runtime.graph_builder.calls == 2


def test_restart_after_committed_capture_uses_receipt_without_rebuilding(
    observer, project, monkeypatch
):
    def crash(name):
        if name == "capture_committed":
            raise KeyboardInterrupt("Simulated process termination")

    monkeypatch.setattr(implementation, "_boundary", crash)
    with pytest.raises(KeyboardInterrupt):
        observer.tick()
    job = observer.status()["jobs"][0]
    assert job["phase"] == "capture"
    monkeypatch.setattr(implementation, "_boundary", lambda name: None)
    restarted = Observer(
        observer.runtime, observer.principal, observer.project_id, observer.profile
    )
    result = restarted.tick()
    assert result["operation_id"] == job["operation_id"]
    assert result["status"] == "reported"
    assert observer.runtime.graph_builder.calls == 1
    assert len(restarted.status()["jobs"]) == 1


def test_report_failure_retries_same_snapshot_without_recapture(
    observer, project, monkeypatch
):
    observer.tick()
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"2"))
    real = implementation.compare_snapshots

    def unavailable(*args, **kwargs):
        raise api.CoreError("SNAPSHOT_READ_DEADLINE_EXCEEDED", "Test fault")

    monkeypatch.setattr(implementation, "compare_snapshots", unavailable)
    for _ in range(3):
        with pytest.raises(api.CoreError):
            observer.tick()
    status = observer.status()
    assert status["jobs"][0]["phase"] == "failed"
    assert len(status["reports"]) == 1
    assert observer.runtime.graph_builder.calls == 2
    with pytest.raises(api.CoreError) as error:
        observer.tick()
    assert error.value.code == "OBSERVER_JOB_FAILED"
    observer.retry()
    monkeypatch.setattr(implementation, "compare_snapshots", real)
    assert observer.tick()["status"] == "reported"
    assert observer.runtime.graph_builder.calls == 2


def test_external_publication_is_reported_without_recapture(observer, project):
    observer.tick()
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"2"))
    external = fixtures.publish(project)
    result = observer.tick()
    assert result["snapshot_id"] == external.snapshot.snapshot_id
    assert observer.runtime.graph_builder.calls == 1
    assert observer.status()["reports"][0]["changes"]["counts"]["modified"] == 1


def test_worker_lock_prevents_overlapping_operations(observer):
    with observer.locked():
        with pytest.raises(api.CoreError) as error:
            observer.tick()
        assert error.value.code == "OBSERVER_BUSY"
    assert observer.tick()["status"] == "reported"


def test_revoked_access_prevents_probe_and_saved_report_read(observer, project):
    observer.tick()
    ctx = project[0]
    with ctx.state.transaction(ctx.principal, write=True) as tx:
        force_legacy_membership(tx, ctx.principal, {"project:admin"})
    for operation in [observer.tick, observer.status, lambda: probe_sources(ctx)]:
        with pytest.raises(api.CoreError) as error:
            operation()
        assert error.value.code == "PROJECT_FORBIDDEN"


def test_profile_inside_sources_is_rejected_without_creating_files(observer, project):
    unsafe = Observer(
        observer.runtime,
        observer.principal,
        observer.project_id,
        project[0].source_root / "observer",
    )
    with pytest.raises(api.CoreError) as error:
        unsafe.initialize()
    assert error.value.code == "OBSERVER_PROFILE_UNSAFE"
    assert not unsafe.profile.exists()


def test_head_race_supersedes_attempt_then_reports_external_snapshot(
    observer, project, monkeypatch
):
    observer.tick()
    project[2].write_bytes(project[2].read_bytes().replace(b"1", b"2"))
    real = implementation.capture_and_publish

    def raced(*args, **kwargs):
        fixtures.publish(project)
        return real(*args, **kwargs)

    monkeypatch.setattr(implementation, "capture_and_publish", raced)
    with pytest.raises(api.CoreError) as error:
        observer.tick()
    assert error.value.code == "HEAD_CONFLICT"
    assert observer.status()["jobs"][0]["phase"] == "superseded"
    monkeypatch.setattr(implementation, "capture_and_publish", real)
    assert observer.tick()["status"] == "reported"
    assert observer.runtime.graph_builder.calls == 1


def test_layer_definition_change_is_not_skipped_as_unchanged(observer, project):
    from rentgen_core.source_configuration import (
        configure_source_layers,
        SourceLayerSpec,
    )

    observer.tick()
    configure_source_layers(
        project[0],
        (SourceLayerSpec("base", 0, "base", ".", "designer_xml"),),
        expected_revision=1,
    )
    assert observer.tick()["status"] == "reported"
    assert observer.runtime.graph_builder.calls == 2
    report = observer.status()["reports"][0]
    assert report["before"] != report["after"]
    assert report["changes"]["counts"]["modified"] == 0


def test_cli_reauthorizes_after_encoding_saved_report(
    observer, project, monkeypatch, capsys
):
    import rentgen_core.observer_cli as cli

    observer.tick()
    real = cli.json.dumps

    def revoked(value, *args, **kwargs):
        encoded = real(value, *args, **kwargs)
        if isinstance(value, dict) and "result" in value:
            ctx = project[0]
            with ctx.state.transaction(ctx.principal, write=True) as tx:
                force_legacy_membership(tx, ctx.principal, {"project:admin"})
        return encoded

    monkeypatch.setattr(cli.json, "dumps", revoked)
    with pytest.raises(api.CoreError) as error:
        cli._emit(observer, {"report": "must not appear"})
    assert error.value.code == "PROJECT_FORBIDDEN"
    assert capsys.readouterr().out == ""


def test_unavailable_journal_stops_worker_without_sleep(observer, monkeypatch, capsys):
    import rentgen_core.observer_cli as cli

    monkeypatch.setattr(cli, "LocalRuntime", lambda *args: observer.runtime)
    monkeypatch.setattr(cli, "current_windows_principal", lambda: observer.principal)

    def unavailable(self):
        raise api.CoreError("STATE_UNAVAILABLE", "Local state transaction failed")

    def forbidden_sleep(seconds):
        pytest.fail("Unavailable journal must stop the worker")

    monkeypatch.setattr(cli.Observer, "_tick", unavailable)
    monkeypatch.setattr(cli.time, "sleep", forbidden_sleep)
    code = cli.main(
        [
            "run",
            "--registry",
            str(observer.runtime.registry_path),
            "--project",
            observer.project_id,
            "--profile",
            str(observer.profile),
            "--scanner",
            "unused.exe",
        ]
    )
    assert code == 2
    assert '"code": "STATE_UNAVAILABLE"' in capsys.readouterr().out
