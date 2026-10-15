"""Real POSIX generations/SQLite and CLI; synthetic graph records, no native 1C."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import os
import sys
from uuid import uuid4

import pytest

from project_access_test_support import grant_membership, revoke_membership
from rentgen_core import snapshot_diff as diff
from rentgen_core._read_operation_budget import ReadOperationBudget, ReadOperationLimits
from rentgen_core.context import Principal, SnapshotRef
from rentgen_core.errors import CoreError
from rentgen_core.graph import GraphBuildReceipt
from rentgen_core.local import LocalRuntime
from rentgen_core.local_identity import initialize_local_identity, current_local_principal
from rentgen_core.manifests import CapturedInput, build_manifest, build_source_document, canonical_bytes, sha256
from rentgen_core.registry import ProjectRegistry
from rentgen_core.snapshots import SnapshotCatalogEntry, SnapshotLayer
from rentgen_core.source_configuration import SourceConfiguration, SourceLayerSpec
from rentgen_core.state import ProjectState
from rentgen_graph.build_store import BuildInputs, build_snapshot_graph
from rentgen_graph.snapshot_adapter import RentgenGraphReaderFactory, SEMANTIC_SCOPE

pytestmark = pytest.mark.skipif(sys.platform not in {"linux", "darwin"}, reason="Actual POSIX pair ownership")
CALLER = "CommonModules/Caller/Ext/Module.bsl"
CALLEE = "CommonModules/Callee/Ext/Module.bsl"


@pytest.fixture
def pair(tmp_path):
    private = tmp_path.resolve() / "private"; private.mkdir(mode=0o700)
    profile = private / "identity" / "identity.json"
    if sys.platform == "linux":
        initialize_local_identity(profile)
        principal = current_local_principal(identity_profile=profile)
    else:
        # A trusted unit-adapter identity exercises real POSIX state/IO here;
        # it does not qualify the Linux-only bootstrap on a macOS host.
        principal = Principal("pair-test-reader", "local_os")
    source = tmp_path.resolve() / "live"; source.mkdir()
    registry_path = private / "registry.sqlite3"; ProjectRegistry.create(registry_path)
    state_root = private / "project"
    project = ProjectRegistry(registry_path).register(principal, source_root=source,
        state_root=state_root, display_name="Real retained pair fixture")
    # This newly created owned fixture establishes the retained private mode;
    # the product reader never repairs permissions on an input generation.
    project.state_root.chmod(0o700)
    runtime = LocalRuntime(registry_path, graph_reader_factory=RentgenGraphReaderFactory())
    state = ProjectState(project.state_root / "state.sqlite3", project.project_id)
    first = {CALLER: b"\xef\xbb\xbfProcedure Caller() Export\r\nCallee.Target();\r\nEndProcedure\r\n",
             CALLEE: b"Procedure Target() Export\nEndProcedure\n", "Old.xml": b"<same/>",
             "Kept.xml": "<same>Кириллица</same>".encode(), "fixture.bin": b"\xff\0"}
    second = dict(first); second[CALLER] = first[CALLER].replace(b"Target();", b"Target(); // changed")
    second["New.xml"] = second.pop("Old.xml")
    value = dict(runtime=runtime, principal=principal, state=state, project_id=project.project_id,
                 profile=profile, registry=registry_path, source=source)
    value["before"] = _publish(value, first)
    value["after"] = _publish(value, second)
    return value


def _publish(pair, contents):
    state, principal, project_id = pair["state"], pair["principal"], pair["project_id"]
    root = state.path.parent / "generations"; root.mkdir(mode=0o700, exist_ok=True)
    path = root / str(uuid4()); path.mkdir(mode=0o700)
    entries = tuple(CapturedInput("base", name, sha256(raw), len(raw),
        "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8" if name != "fixture.bin" else None)
        for name, raw in sorted(contents.items()))
    source = build_source_document(project_id, SourceConfiguration(1,
        (SourceLayerSpec("base", 0, "base", ".", "unknown"),)), (), entries)
    bindings = sorted([dict(asdict(entry), graph_source_path="base/" + entry.relative_path)
        for entry in entries if entry.relative_path.endswith(".bsl")], key=lambda row: row["graph_source_path"])
    receipt = GraphBuildReceipt("2", "source-path-v1", sha256(source), sha256(canonical_bytes(bindings)),
        "rentgen-captured-go-v1", "synthetic-scanner-fixture", "fixture-builder", "b" * 64, SEMANTIC_SCOPE)
    for name, raw in contents.items():
        leaf = path / "sources/base" / name; leaf.parent.mkdir(parents=True, exist_ok=True); leaf.write_bytes(raw)
    inputs = path / "inputs"; inputs.mkdir(); (path / "build-work").mkdir()
    records = [dict(name="Caller", module="Caller", source_path="base/" + CALLER,
        line=1, end_line=3, is_export=True, calls=["Callee.Target"]),
        dict(name="Target", module="Callee", source_path="base/" + CALLEE,
        line=1, end_line=2, is_export=True, calls=[])]
    ndjson = inputs / "callgraph.ndjson"; ndjson.write_bytes(b"\n".join(json.dumps(row).encode() for row in records))
    (inputs / "scanner-coverage.json").write_bytes(b'{"fixture":"synthetic scanner coverage"}')
    build_snapshot_graph(BuildInputs(ndjson, None), path / "graph.sqlite3", receipt,
                         source_paths=tuple(row["graph_source_path"] for row in bindings))
    graph = (path / "graph.sqlite3").read_bytes()
    derived = [dict(relative_path=name, raw_sha256=sha256((path / name).read_bytes()),
        size_bytes=(path / name).stat().st_size) for name in ("inputs/callgraph.ndjson", "inputs/scanner-coverage.json")]
    import sqlite3
    manifest = build_manifest(source, dict(asdict(receipt), relative_path="graph.sqlite3",
        raw_sha256=sha256(graph), sqlite_version=sqlite3.sqlite_version, quality="unavailable"), derived)
    (path / "manifest.json").write_bytes(manifest)
    for child in path.rglob("*"): child.chmod(0o700 if child.is_dir() else 0o600)
    snapshot = SnapshotRef(project_id, sha256(manifest), sha256(manifest))
    catalog = SnapshotCatalogEntry(snapshot, sha256(source), sha256(graph), "generations/" + path.name,
                                   1, datetime.now(timezone.utc).isoformat())
    with state.transaction(principal, write=True) as tx:
        tx.commit_publication(expected_head=tx.get_project_head(), catalog=catalog,
            layers=(SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),), operation_id=str(uuid4()))
    return dict(snapshot=snapshot, catalog=catalog, path=path, contents=contents,
        copied=len(manifest) + len(graph) + sum(map(len, contents.values())) + sum(v["size_bytes"] for v in derived))


def compare(pair, **options):
    return diff.compare_retained_pair(pair["runtime"], pair["principal"], pair["project_id"],
        pair["before"]["snapshot"].snapshot_id, pair["after"]["snapshot"].snapshot_id, **options)


def observe_budget(monkeypatch):
    budgets = []
    def factory(*args, **kwargs):
        value = ReadOperationBudget(*args, **kwargs); budgets.append(value); return value
    monkeypatch.setattr(diff, "ReadOperationBudget", factory)
    return budgets


def test_pair_pages_reverse_self_and_later_head_do_not_use_eager_resolver(pair, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Pair must not call the eager resolver")
    monkeypatch.setattr(LocalRuntime, "resolve", forbidden)
    before_db = pair["state"].path.read_bytes()
    page = compare(pair, limit=1); changes = list(page.value["changes"])
    assert page.value["counts"] == dict(added=1, removed=1, modified=1, unchanged=3)
    while page.value["next_cursor"]:
        page = compare(pair, limit=1, cursor=page.value["next_cursor"]); changes.extend(page.value["changes"])
    assert [v["kind"] for v in changes] == ["modified", "added", "removed"]
    assert pair["state"].path.read_bytes() == before_db
    later = _publish(pair, pair["before"]["contents"] | {"Later.xml": b"<later/>"})
    (later["path"] / "manifest.json").write_bytes(b"broken unrelated latest")
    pair["source"].rmdir()
    assert compare(pair).value["changes"] == changes
    reverse = diff.compare_retained_pair(pair["runtime"], pair["principal"], pair["project_id"],
        pair["after"]["snapshot"].snapshot_id, pair["before"]["snapshot"].snapshot_id)
    assert reverse.value["counts"] == dict(added=1, removed=1, modified=1, unchanged=3)
    same = diff.compare_retained_pair(pair["runtime"], pair["principal"], pair["project_id"],
        pair["before"]["snapshot"].snapshot_id, pair["before"]["snapshot"].snapshot_id)
    assert same.value["changes"] == [] and same.value["counts"]["unchanged"] == 5


@pytest.mark.parametrize("field,value,code", [("limit", True, "INVALID_QUERY_OPTIONS"),
    ("limit", 0, "INVALID_QUERY_OPTIONS"), ("limit", 101, "INVALID_QUERY_OPTIONS"),
    ("cursor", "v1." + "0" * 64 + ".1", "INVALID_DIFF_CURSOR"), ("cursor", "", "INVALID_DIFF_CURSOR")])
def test_invalid_pair_options_refuse_before_retained_io(pair, monkeypatch, field, value, code):
    from rentgen_core import _posix_snapshot_session as backend
    def forbidden(**kwargs): raise AssertionError("Invalid options opened retained sources")
    monkeypatch.setattr(backend, "open_posix_snapshot_session", forbidden)
    with pytest.raises(CoreError) as error: compare(pair, **{field: value})
    assert error.value.code == code


def test_unauthorized_request_precedes_invalid_selectors_or_catalog_io(pair, monkeypatch):
    from rentgen_core import _posix_snapshot_session as backend
    def forbidden(**kwargs): raise AssertionError("Unauthorized retained IO")
    monkeypatch.setattr(backend, "open_posix_snapshot_session", forbidden)
    with pytest.raises(CoreError) as error:
        diff.compare_retained_pair(pair["runtime"], Principal("unknown", "local_os"), pair["project_id"], "", "", limit=True)
    assert error.value.code == "PROJECT_FORBIDDEN"


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("artifact", ["manifest.json", "graph.sqlite3", "sources/base/" + CALLER, "extra"])
def test_either_corrupt_generation_closes_real_owners_before_error(pair, monkeypatch, side, artifact):
    budgets = observe_budget(monkeypatch)
    (pair[side]["path"] / artifact).write_bytes(b"corrupt retained bytes")
    with pytest.raises(CoreError) as error: compare(pair)
    assert error.value.code == "SNAPSHOT_CORRUPT"
    summary = budgets[0].summary()
    assert summary["closed"] and summary["active_owners"] == 0 and not any(summary["held"].values())


def test_two_individually_fitting_generations_share_one_copy_budget(pair, monkeypatch):
    budgets = observe_budget(monkeypatch)
    bound = pair["before"]["copied"] + pair["after"]["copied"] - 1
    assert max(pair[side]["copied"] for side in ("before", "after")) < bound
    with pytest.raises(CoreError) as error:
        compare(pair, operation_limits=replace(ReadOperationLimits(), copied_bytes=bound))
    assert error.value.code == "SNAPSHOT_READ_LIMIT_EXCEEDED"
    summary = budgets[0].summary()
    assert summary["closed"] and summary["cumulative"]["copied_bytes"] <= bound
    assert summary["active_owners"] == 0 and not any(summary["held"].values())


def test_cli_serialization_rechecks_pair_and_access(pair, monkeypatch, capsys):
    from rentgen_core import cli
    admin = Principal("pair-revocation-admin", "local_os")
    with pair["state"].transaction(pair["principal"], write=True) as tx:
        grant_membership(tx, admin, {"project:read", "project:admin"})
    original_require, original_default = cli.require_operation, cli._default
    monkeypatch.setattr(cli, "require_operation", lambda name: None if name == "snapshot-diff" else original_require(name))
    if sys.platform == "darwin":
        monkeypatch.setattr(cli, "current_local_principal", lambda **options: pair["principal"])
    revoked = False
    def encode(value):
        nonlocal revoked
        result = original_default(value)
        if not revoked:
            revoked = True
            with pair["state"].transaction(admin, write=True) as tx:
                revoke_membership(tx, pair["principal"])
        return result
    monkeypatch.setattr(cli, "_default", encode)
    code = cli.main(["snapshot-diff", "--registry", str(pair["registry"]), "--identity-profile", str(pair["profile"]),
        "--project", pair["project_id"], "--before", pair["before"]["snapshot"].snapshot_id,
        "--after", pair["after"]["snapshot"].snapshot_id])
    output = json.loads(capsys.readouterr().out)
    assert revoked and code == 2 and output["error"]["code"] == "PROJECT_FORBIDDEN" and "result" not in output


@pytest.mark.parametrize("change", ["before", "after", "deadline"])
def test_cli_final_encoding_cannot_disclose_a_changed_pair_or_expired_operation(pair, monkeypatch, capsys, change):
    import sqlite3
    from rentgen_core import cli
    original_require, original_default, clock = cli.require_operation, cli._default, diff.monotonic
    monkeypatch.setattr(cli, "require_operation", lambda name: None if name == "snapshot-diff" else original_require(name))
    if sys.platform == "darwin":
        monkeypatch.setattr(cli, "current_local_principal", lambda **options: pair["principal"])
    changed = False
    def encode(value):
        nonlocal changed
        result = original_default(value)
        if not changed:
            changed = True
            if change == "deadline":
                monkeypatch.setattr(diff, "monotonic", lambda: clock() + 60)
            else:
                with sqlite3.connect(pair["state"].path) as db:
                    db.execute("UPDATE snapshots SET published_at=? WHERE snapshot_id=?",
                        ("2026-10-01T00:00:00+00:00", pair[change]["snapshot"].snapshot_id))
        return result
    monkeypatch.setattr(cli, "_default", encode)
    code = cli.main(["snapshot-diff", "--registry", str(pair["registry"]), "--identity-profile", str(pair["profile"]),
        "--project", pair["project_id"], "--before", pair["before"]["snapshot"].snapshot_id,
        "--after", pair["after"]["snapshot"].snapshot_id])
    output = json.loads(capsys.readouterr().out)
    expected = "SNAPSHOT_READ_DEADLINE_EXCEEDED" if change == "deadline" else "SNAPSHOT_CORRUPT"
    assert changed and code == 2 and output["error"]["code"] == expected and "result" not in output


def test_cli_success_preserves_public_page_shape_without_private_output_scope(pair, monkeypatch, capsys):
    from rentgen_core import cli
    original_require = cli.require_operation
    monkeypatch.setattr(cli, "require_operation", lambda name: None if name == "snapshot-diff" else original_require(name))
    if sys.platform == "darwin":
        monkeypatch.setattr(cli, "current_local_principal", lambda **options: pair["principal"])
    code = cli.main(["snapshot-diff", "--registry", str(pair["registry"]), "--identity-profile", str(pair["profile"]),
        "--project", pair["project_id"], "--before", pair["before"]["snapshot"].snapshot_id,
        "--after", pair["after"]["snapshot"].snapshot_id, "--limit", "1"])
    output = json.loads(capsys.readouterr().out)
    assert code == 0 and set(output) == {"result", "request_id"}
    assert output["result"]["counts"] == dict(added=1, removed=1, modified=1, unchanged=3)
    assert len(output["result"]["changes"]) == 1 and output["result"]["next_cursor"]
    assert "output_scope" not in str(output) and "catalog_digest" not in str(output)
