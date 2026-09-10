"""File changes come from two verified retained snapshots, never current files."""
from dataclasses import replace

import pytest
import rentgen_core as api
import test_project_core_snapshot_resolver as fixtures
from project_access_test_support import force_legacy_membership
from rentgen_core.snapshot_diff import compare_snapshots
import test_project_core_cli as cli_fixtures

project = fixtures.project
scanner = fixtures.scanner
command = cli_fixtures.command
pytestmark = fixtures.pytestmark


def pair(project):
    module = project[2]
    root = module.parents[3]
    (root / "Old.xml").write_bytes(b"<same/>")
    (root / "Kept.xml").write_bytes(b"<unchanged/>")
    fixtures.publish(project)
    before = fixtures.selected(project)
    (root / "Old.xml").rename(root / "New.xml")
    module.write_bytes(module.read_bytes().replace(b"1", b"2"))
    fixtures.publish(project)
    return before, fixtures.selected(project)


def test_exact_byte_changes_remain_readable_after_live_sources_are_removed(project):
    before, after = pair(project)
    project[2].unlink()
    result = compare_snapshots(before, after)
    assert result["counts"] == {"added": 1, "removed": 1, "modified": 1, "unchanged": 1}
    assert [c["kind"] for c in result["changes"]] == ["modified", "added", "removed"]
    assert result["changes"][0]["before"].ref.snapshot == before.snapshot
    assert result["changes"][0]["after"].ref.snapshot == after.snapshot
    assert result["next_cursor"] is None
    assert result["scope"] == "source_bytes_by_layer_and_path"
    assert result["identity"] == "source_path_only"
    changed = result["changes"][0]
    assert b"1" in before.sources.read_source(changed["before"].ref)
    assert b"2" in after.sources.read_source(changed["after"].ref)
    assert compare_snapshots(after, after)["changes"] == []


def test_cursor_binds_ordered_snapshot_pair_and_limit(project):
    before, after = pair(project)
    result = compare_snapshots(before, after, limit=1)
    changes = list(result["changes"])
    cursor = result["next_cursor"]
    for left, right, limit in [
        (after, before, 1),
        (before, after, 2),
        (before, before, 1),
    ]:
        with pytest.raises(api.CoreError) as error:
            compare_snapshots(left, right, limit=limit, cursor=cursor)
        assert error.value.code == "INVALID_DIFF_CURSOR"
    while result["next_cursor"]:
        result = compare_snapshots(before, after, limit=1, cursor=result["next_cursor"])
        changes.extend(result["changes"])
    assert changes == compare_snapshots(before, after)["changes"]


def test_revocation_cannot_return_changes(project):
    before, after = pair(project)
    with before.state.transaction(before.principal, write=True) as tx:
        force_legacy_membership(tx, before.principal, {"project:admin"})
    with pytest.raises(api.CoreError) as error:
        compare_snapshots(before, after)
    assert error.value.code == "PROJECT_FORBIDDEN"


def test_retained_corruption_cannot_return_changes(project):
    before, after = pair(project)
    (before.sources._path / "manifest.json").write_bytes(b"corrupt")
    with pytest.raises(api.CoreError) as error:
        compare_snapshots(before, after)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_cli_pagination_uses_explicit_snapshots_after_a_later_publication(
    command, project
):
    before, after = pair(project)
    selectors = (
        "--before",
        before.snapshot.snapshot_id,
        "--after",
        after.snapshot.snapshot_id,
    )
    first, _ = command("snapshot-diff", *selectors, "--limit", "1")
    assert first["result"]["counts"]["modified"] == 1
    project[2].write_bytes(project[2].read_bytes().replace(b"2", b"3"))
    fixtures.publish(project)
    second, _ = command(
        "snapshot-diff",
        *selectors,
        "--limit",
        "1",
        "--cursor",
        first["result"]["next_cursor"],
    )
    assert (
        second["result"]["after_snapshot"]["snapshot_id"] == after.snapshot.snapshot_id
    )
    assert second["result"]["changes"][0]["kind"] == "added"
    failure, _ = command(
        "snapshot-diff", "--before", before.snapshot.snapshot_id, success=False
    )
    assert failure["error"]["code"] == "INVALID_ARGUMENT"


def test_mixed_principals_and_invalid_limits_fail_before_read_session(
    project, monkeypatch
):
    before, after = pair(project)
    from rentgen_core.sources import SnapshotSources

    def unexpected(*args, **kwargs):
        raise AssertionError("Invalid comparison must not open source files")

    monkeypatch.setattr(SnapshotSources, "read_session", unexpected)
    other = replace(after, principal=api.Principal("other", "local_os"))
    with pytest.raises(api.CoreError) as error:
        compare_snapshots(before, other)
    assert error.value.code == "CONTEXT_PROJECT_MISMATCH"
    for limit in [True, 0, 101, "10"]:
        with pytest.raises(api.CoreError) as error:
            compare_snapshots(before, after, limit=limit)
        assert error.value.code == "INVALID_QUERY_OPTIONS"


def test_cli_revocation_during_serialization_suppresses_the_report(
    command, project, monkeypatch
):
    import rentgen_core.cli as cli

    before, after = pair(project)
    original = cli._default
    revoked = False

    def encode(value):
        nonlocal revoked
        result = original(value)
        if not revoked:
            revoked = True
            with before.state.transaction(before.principal, write=True) as tx:
                force_legacy_membership(tx, before.principal, {"project:admin"})
        return result

    monkeypatch.setattr(cli, "_default", encode)
    output, _ = command(
        "snapshot-diff",
        "--before",
        before.snapshot.snapshot_id,
        "--after",
        after.snapshot.snapshot_id,
        success=False,
    )
    assert revoked
    assert output["error"]["code"] == "PROJECT_FORBIDDEN"
    assert "result" not in output


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("file_kind", ["manifest", "source"])
def test_both_generations_reject_tampering(side, file_kind, project):
    before, after = pair(project)
    context = before if side == "before" else after
    path = context.sources._path
    if file_kind == "manifest":
        target = path / "manifest.json"
    else:
        target = path / "sources/base/CommonModules/ОбщийМодуль/Ext/Module.bsl"
    target.write_bytes(b"changed outside the publication protocol")
    with pytest.raises(api.CoreError) as error:
        compare_snapshots(before, after)
    assert error.value.code == "SNAPSHOT_CORRUPT"


def test_cli_comparison_does_not_require_latest_generation_or_modify_state(
    command, project
):
    before, after = pair(project)
    project[2].write_bytes(project[2].read_bytes().replace(b"2", b"3"))
    fixtures.publish(project)
    latest = fixtures.selected(project)
    (latest.sources._path / "manifest.json").write_bytes(b"broken latest snapshot")
    original_database = before.state.path.read_bytes()
    original_source = project[2].read_bytes()
    result, _ = command(
        "snapshot-diff",
        "--before",
        before.snapshot.snapshot_id,
        "--after",
        after.snapshot.snapshot_id,
    )
    assert result["result"]["counts"] == {
        "added": 1,
        "removed": 1,
        "modified": 1,
        "unchanged": 1,
    }
    assert before.state.path.read_bytes() == original_database
    assert project[2].read_bytes() == original_source
