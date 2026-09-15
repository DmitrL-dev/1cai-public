"""Administrative logical archives preserve evidence and actual Windows pins."""
from dataclasses import replace
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
import rentgen_core as api
from rentgen_core import native_resources as resources
from rentgen_core.manifests import canonical_bytes, sha256
from rentgen_core.platform_runs import get_platform_run
from project_access_test_support import grant_membership
import test_metadata_runs as metadata_fixtures

project = metadata_fixtures.project
scanner = metadata_fixtures.scanner
captured = metadata_fixtures.captured
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows retained handles")


@pytest.fixture
def retained(tmp_path):
    owner = api.Principal("owner", "local_os")
    source = tmp_path / "source"
    source.mkdir()
    registry = api.ProjectRegistry.create(tmp_path / "registry.sqlite3")
    registered = registry.register(
        owner, source_root=source, state_root=tmp_path / "state", display_name="A"
    )
    ctx = api.ContextResolver(registry).resolve_context(
        owner, api.Explicit(registered.project_id)
    )
    return ctx


def make_run(ctx, namespace="platform-checks"):
    run = ctx.state.path.parent / namespace / str(uuid4())
    run.mkdir(parents=True)
    binding = {
        "source_ref": {"snapshot": {"project_id": ctx.project_id}},
        "proposal_content_id": "a" * 64,
        "platform_executable_sha256": "b" * 64,
    }
    if namespace == "test-runs":
        binding["profile_id"] = "c" * 64
    request = {
        "schema": 1,
        "project_id": ctx.project_id,
        "run_id": run.name,
        "input": binding,
    }
    report = {"schema": 1, "run_id": run.name, **binding}
    report["report_sha256"] = sha256(canonical_bytes(report))
    for name, value in (("request", request), ("report", report)):
        (run / (name + ".json")).write_bytes(canonical_bytes(value))
    (run / "infobase").mkdir()
    (run / "infobase/1Cv8.1CD").write_bytes(b"retained database")
    (run / "stdout.log").write_bytes(b"evidence")
    return run


def archive(ctx, run, profile_id=None):
    return resources.archive_native_run(
        ctx, run.name, namespace=run.parent.name, profile_id=profile_id
    )


@pytest.mark.parametrize("namespace", ["platform-checks", "test-runs"])
def test_archive_is_idempotent_preserves_evidence_and_frees_only_slot(
    retained, monkeypatch, namespace
):
    ctx = retained
    run = make_run(ctx, namespace)
    before = {p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()}
    profile = "c" * 64 if namespace == "test-runs" else None
    result = archive(ctx, run, profile)
    assert result["status"] == "archived"
    assert result["released_logical_bytes"] == 0
    assert archive(ctx, run, profile) == result
    assert {
        p.relative_to(run): p.read_bytes() for p in run.rglob("*") if p.is_file()
    } == before
    assert get_platform_run(ctx, run.name, namespace=namespace)["status"] == "completed"
    monkeypatch.setattr(resources, "RETAINED_RUN_LIMIT", 1)
    limits = resources.DiskLimits(run_bytes=1, project_bytes=100000, free_bytes=0)
    resources.reserve_run(
        ctx.state.path.parent, run.parent / str(uuid4()), limits=limits
    )
    with pytest.raises(FileExistsError):
        resources.reserve_run(ctx.state.path.parent, run, limits=limits)
    with pytest.raises(api.CoreError) as error:
        resources.DiskBudget(
            ctx.state.path.parent,
            run,
            resources.DiskLimits(project_bytes=1, free_bytes=0),
        ).check(force=True)
    assert error.value.code == "NATIVE_STORAGE_LIMIT"


def test_non_admin_cannot_archive(retained):
    run = make_run(retained)
    reader = api.Principal("reader", "local_os")
    with retained.state.transaction(retained.principal, write=True) as tx:
        grant_membership(tx, reader, {"project:read", "source:edit", "analysis:run"})
    with pytest.raises(api.CoreError):
        archive(replace(retained, principal=reader), run)
    assert not (retained.state.path.parent / "native-archive").exists()


@pytest.mark.parametrize("lock", ["native-executor.lock", "native-admission.lock"])
def test_archive_rejects_active_locks(retained, lock):
    run = make_run(retained)
    with resources._file_slot(retained.state.path.parent, lock, "BUSY"):
        with pytest.raises(api.CoreError) as error:
            archive(retained, run)
    assert error.value.code in {"NATIVE_EXECUTOR_BUSY", "NATIVE_ADMISSION_BUSY"}
    assert not (retained.state.path.parent / "native-archive").exists()


@pytest.mark.parametrize(
    "fault", ["missing", "malformed", "foreign_project", "foreign_profile"]
)
def test_archive_rejects_unconfirmed_or_foreign_receipts(retained, fault):
    run = make_run(retained, "test-runs")
    if fault == "missing":
        (run / "report.json").unlink()
    elif fault == "malformed":
        (run / "report.json").write_bytes(b'{"schema":1,"schema":1}')
    elif fault == "foreign_project":
        value = json.loads((run / "request.json").read_bytes())
        value["project_id"] = str(uuid4())
        (run / "request.json").write_bytes(canonical_bytes(value))
    with pytest.raises(api.CoreError):
        archive(retained, run, "d" * 64 if fault == "foreign_profile" else "c" * 64)
    assert not (retained.state.path.parent / "native-archive").exists()


@pytest.mark.parametrize("fault", ["hardlink", "junction"])
def test_archive_rejects_linked_data_without_touching_user_files(retained, fault):
    run = make_run(retained)
    outside = retained.source_root / "working"
    outside.mkdir()
    sentinel = outside / "1Cv8.1CD"
    sentinel.write_bytes(b"user database")
    alias = run / "alias"
    if fault == "hardlink":
        os.link(sentinel, alias)
    else:
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(alias), str(outside)],
            check=True,
            capture_output=True,
            timeout=10,
        )
    try:
        with pytest.raises(api.CoreError):
            archive(retained, run)
        assert sentinel.read_bytes() == b"user database"
        assert not (retained.state.path.parent / "native-archive").exists()
    finally:
        if fault == "junction":
            alias.rmdir()


def test_changed_archive_fails_closed_on_replay_and_admission(retained):
    run = make_run(retained)
    archive(retained, run)
    (run / "stdout.log").write_bytes(b"changed")
    with pytest.raises(api.CoreError):
        archive(retained, run)
    with pytest.raises(api.CoreError):
        resources.reserve_run(retained.state.path.parent, run.parent / str(uuid4()))


def test_audit_write_failure_does_not_release_slot(retained, monkeypatch):
    run = make_run(retained)

    def fail(_):
        raise OSError("injected audit flush failure")

    with monkeypatch.context() as patch:
        patch.setattr(resources.os, "fsync", fail)
        with pytest.raises((api.CoreError, OSError)):
            archive(retained, run)
    with pytest.raises(api.CoreError):
        resources.reserve_run(retained.state.path.parent, run.parent / str(uuid4()))


def test_metadata_archive_keeps_verified_preview_and_rejects_profile(captured):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    with pytest.raises(api.CoreError):
        archive(ctx, run, "b" * 64)
    assert archive(ctx, run, "a" * 64)["status"] == "archived"
    assert metadata_fixtures.runs.get_preview(ctx, operation) == preview


@pytest.mark.parametrize("target", ["run", "namespace", "audit"])
def test_redirected_ancestors_cannot_be_archived(retained, target):
    run = make_run(retained)
    outside = retained.source_root / "external"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"user data")
    if target == "audit":
        link = retained.state.path.parent / "native-archive"
    else:
        link = run if target == "run" else run.parent
        moved = link.with_name(link.name + "-original")
        link.rename(moved)
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    try:
        with pytest.raises(api.CoreError):
            archive(retained, run)
        assert sentinel.read_bytes() == b"user data"
        assert list(outside.iterdir()) == [sentinel]
    finally:
        link.rmdir()


def test_tampered_archive_project_with_recomputed_digest_fails_closed(retained):
    run = make_run(retained)
    archive(retained, run)
    saved = (
        retained.state.path.parent
        / "native-archive"
        / (run.parent.name + "-" + run.name)
    )
    manifest = json.loads((saved / "manifest.json").read_bytes())
    manifest["project_id"] = str(uuid4())
    (saved / "manifest.json").write_bytes(canonical_bytes(manifest))
    receipt = json.loads((saved / "receipt.json").read_bytes())
    receipt["manifest_sha256"] = sha256(canonical_bytes(manifest))
    (saved / "receipt.json").write_bytes(canonical_bytes(receipt))
    with pytest.raises(api.CoreError):
        resources.reserve_run(retained.state.path.parent, run.parent / str(uuid4()))


def test_archive_requires_canonical_test_profile(retained):
    run = make_run(retained, "test-runs")
    for name in ("request", "report"):
        path = run / (name + ".json")
        value = json.loads(path.read_bytes())
        if name == "request":
            value["input"]["profile_id"] = "not-a-profile"
        else:
            value["profile_id"] = "not-a-profile"
            del value["report_sha256"]
            value["report_sha256"] = sha256(canonical_bytes(value))
        path.write_bytes(canonical_bytes(value))
    with pytest.raises(api.CoreError):
        archive(retained, run, "not-a-profile")


def test_metadata_unknown_runtime_cannot_be_archived(captured):
    ctx, _, run, _ = metadata_fixtures._finished_run(captured)
    (run / "runtime-closed.json").write_bytes(b'{"status":"unknown"}')
    with pytest.raises(api.CoreError):
        archive(ctx, run, "a" * 64)


@pytest.mark.parametrize("fault", ["boolean_schema", "missing_actor"])
def test_malformed_audit_is_not_an_admission_exemption(retained, fault):
    run = make_run(retained)
    archive(retained, run)
    saved = (
        retained.state.path.parent
        / "native-archive"
        / (run.parent.name + "-" + run.name)
    )
    manifest = json.loads((saved / "manifest.json").read_bytes())
    receipt = json.loads((saved / "receipt.json").read_bytes())
    if fault == "boolean_schema":
        receipt["schema"] = True
    else:
        manifest["requested_by"] = {}
        receipt["manifest_sha256"] = sha256(canonical_bytes(manifest))
        (saved / "manifest.json").write_bytes(canonical_bytes(manifest))
    (saved / "receipt.json").write_bytes(canonical_bytes(receipt))
    with pytest.raises(api.CoreError):
        resources.reserve_run(retained.state.path.parent, run.parent / str(uuid4()))


def test_inventory_limit_retains_all_files(retained):
    run = make_run(retained)
    for index in range(4096):
        (run / str(index)).touch()
    with pytest.raises(api.CoreError) as error:
        archive(retained, run)
    assert error.value.code == "NATIVE_ARCHIVE_LIMIT"
    assert not (retained.state.path.parent / "native-archive").exists()
    assert (run / "infobase/1Cv8.1CD").read_bytes() == b"retained database"


def test_disk_accounting_includes_archive_audit_bytes(retained):
    run = make_run(retained)
    archive(retained, run)
    root = retained.state.path.parent
    expected = sum(
        path.stat().st_size
        for namespace in (*resources.NAMESPACES, "native-archive")
        for path in (root / namespace).rglob("*")
        if path.is_file()
    )
    budget = resources.DiskBudget(root, run)
    budget.check(force=True)
    assert budget.last["project_bytes"] == expected


def test_business_evidence_refuses_archived_run_before_writing(captured):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    receipt = archive(ctx, run, "a" * 64)
    with pytest.raises(api.CoreError) as error:
        metadata_fixtures.runs.attach_business_evidence(
            ctx, operation, metadata_fixtures._evidence(preview)
        )
    assert error.value.code == "NATIVE_RUN_ARCHIVED"
    assert not (run / "business-evidence.json").exists()
    assert archive(ctx, run, "a" * 64) == receipt


def test_business_evidence_writer_serializes_archive_until_publication(
    captured, monkeypatch
):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    waiting, release = Event(), Event()
    original = metadata_fixtures.runs._validate_business_evidence

    def paused(*args):
        result = original(*args)
        waiting.set()
        assert release.wait(10), "writer was not released"
        return result

    monkeypatch.setattr(metadata_fixtures.runs, "_validate_business_evidence", paused)
    with ThreadPoolExecutor(max_workers=1) as workers:
        worker = workers.submit(
            metadata_fixtures.runs.attach_business_evidence,
            ctx,
            operation,
            metadata_fixtures._evidence(preview),
        )
        try:
            assert waiting.wait(10), "writer did not reach publication boundary"
            with pytest.raises(api.CoreError) as error:
                archive(ctx, run, "a" * 64)
            assert error.value.code == "NATIVE_ADMISSION_BUSY"
            assert not (run / "business-evidence.json").exists()
        finally:
            release.set()
        assert worker.result(timeout=10)["business_evidence"]["status"] == "passed"
    assert archive(ctx, run, "a" * 64)["status"] == "archived"


def test_business_evidence_writer_refuses_while_archive_holds_admission(captured):
    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    with resources._file_slot(ctx.state.path.parent, "native-admission.lock", "BUSY"):
        with pytest.raises(api.CoreError) as error:
            metadata_fixtures.runs.attach_business_evidence(
                ctx, operation, metadata_fixtures._evidence(preview)
            )
    assert error.value.code == "NATIVE_ADMISSION_BUSY"
    assert not (run / "business-evidence.json").exists()


def test_archive_publication_blocks_evidence_writer_and_preserves_manifest(
    captured, monkeypatch
):
    from rentgen_core import edt_execution

    ctx, operation, run, preview = metadata_fixtures._finished_run(captured)
    waiting, release = Event(), Event()
    original = edt_execution.write_record

    def paused(path, value):
        original(path, value)
        if path.name == "manifest.json":
            waiting.set()
            assert release.wait(10), "archive was not released"

    monkeypatch.setattr(edt_execution, "write_record", paused)
    with ThreadPoolExecutor(max_workers=1) as workers:
        worker = workers.submit(archive, ctx, run, "a" * 64)
        try:
            assert waiting.wait(10), "archive did not reach publication boundary"
            with pytest.raises(api.CoreError) as error:
                metadata_fixtures.runs.attach_business_evidence(
                    ctx, operation, metadata_fixtures._evidence(preview)
                )
            assert error.value.code == "NATIVE_ADMISSION_BUSY"
            assert not (run / "business-evidence.json").exists()
        finally:
            release.set()
        receipt = worker.result(timeout=10)
    with pytest.raises(api.CoreError) as error:
        metadata_fixtures.runs.attach_business_evidence(
            ctx, operation, metadata_fixtures._evidence(preview)
        )
    assert error.value.code == "NATIVE_RUN_ARCHIVED"
    assert archive(ctx, run, "a" * 64) == receipt


@pytest.mark.parametrize("existing_run", [False, True])
@pytest.mark.parametrize("operation", ["admission", "budget", "archive_replay"])
def test_dangling_archive_root_refuses_even_without_retained_runs(
    retained, existing_run, operation
):
    root = retained.state.path.parent
    run = (
        make_run(retained) if existing_run else root / "platform-checks" / str(uuid4())
    )
    run.parent.mkdir(exist_ok=True)
    target = retained.source_root / "missing-archive-target"
    link = root / "native-archive"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
        timeout=10,
    )
    try:
        assert not link.exists()
        assert link.lstat().st_file_attributes & 0x400
        with pytest.raises(api.CoreError) as error:
            if operation == "admission":
                resources.reserve_run(root, run)
            elif operation == "budget":
                resources.DiskBudget(root, run).check(force=True)
            else:
                archive(retained, run)
        assert error.value.code == "NATIVE_ARCHIVE_INVALID"
        assert not target.exists()
        assert run.exists() is existing_run
    finally:
        link.rmdir()
