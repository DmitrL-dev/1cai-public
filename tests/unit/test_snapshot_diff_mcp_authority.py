"""Final MCP encoding rechecks genuine local memberships and catalog records.

Catalogs below are test-only state records without retained generations. They
verify disclosure authorization, never capture or native Linux acceptance.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import io
import json
from time import monotonic
from uuid import uuid4

import pytest
from mcp import types

from project_access_test_support import force_legacy_membership
from rentgen_core import _sqlite, snapshot_diff, stdio_mcp
from rentgen_core.context import Principal, SnapshotRef
from rentgen_core.local import LocalRuntime
from rentgen_core.registry import ProjectRegistry
from rentgen_core.snapshots import SnapshotCatalogEntry, SnapshotLayer
from rentgen_core.state import ProjectState


@pytest.mark.parametrize("mutation,expected", [
    ("revoke", "PROJECT_FORBIDDEN"),
    ("before_catalog", "SNAPSHOT_CORRUPT"),
    ("after_catalog", "SNAPSHOT_CORRUPT"),
    ("deadline", "SNAPSHOT_READ_DEADLINE_EXCEEDED"),
])
def test_real_state_authority_is_rechecked_after_final_encoding(tmp_path, monkeypatch, mutation, expected):
    principal = Principal("output-reader", "local_os")
    registry = ProjectRegistry.create(tmp_path / "registry.sqlite3")
    source = tmp_path / "live"
    source.mkdir()
    project = registry.register(principal, source_root=source, state_root=tmp_path / "state", display_name="Output authority fixture")
    state = ProjectState(project.state_root / "state.sqlite3", project.project_id)
    catalogs = [SnapshotCatalogEntry(
        SnapshotRef(project.project_id, char * 64, char * 64), "c" * 64,
        "d" * 64, "generations/" + char * 64, 1, datetime.now(timezone.utc).isoformat(),
    ) for char in ("a", "b")]
    with state.transaction(principal, write=True) as tx:
        for catalog in catalogs:
            tx.commit_publication(
                expected_head=tx.get_project_head(), catalog=catalog,
                layers=(SnapshotLayer("base", 0, "base", None, "unresolved", "unknown"),),
                operation_id=str(uuid4()),
            )
    runtime = LocalRuntime(registry.path)
    scope = snapshot_diff.DiffOutputScope(
        project.project_id, catalogs[0].snapshot.snapshot_id, catalogs[1].snapshot.snapshot_id,
        snapshot_diff._catalog_pair_digest(*catalogs), monotonic() + 30,
    )
    value = {
        "before_snapshot": asdict(catalogs[0].snapshot), "after_snapshot": asdict(catalogs[1].snapshot),
        "scope": "source_bytes_by_layer_and_path", "identity": "source_path_only",
        "counts": {"added": 1, "removed": 0, "modified": 0, "unchanged": 0},
        "changes": ["PRIVATE_DIFF_OUTPUT"], "next_cursor": None,
    }
    reply = stdio_mcp._diff_reply(runtime, principal, snapshot_diff.DiffOperationResult(value, scope), str(uuid4()), 7)
    assert reply.isError is False
    document = types.JSONRPCResponse(
        jsonrpc="2.0", id=7, result=reply.model_dump(by_alias=True, mode="json", exclude_none=True),
    ).model_dump_json(by_alias=True, exclude_none=True) + "\n"
    stream = io.BytesIO()
    guarded = stdio_mcp._GuardedOutput(stream, runtime, principal)
    original = guarded._bytes
    mutated = False

    def encode_then_mutate(document):
        nonlocal mutated
        encoded = original(document)
        if not mutated:
            mutated = True
            if mutation == "revoke":
                with state.transaction(principal, write=True) as tx:
                    force_legacy_membership(tx, principal, {"project:admin"})
            elif mutation.endswith("_catalog"):
                selected = catalogs[0 if mutation == "before_catalog" else 1].snapshot.snapshot_id
                with _sqlite.transaction(state.path, write=True) as db:
                    db.execute("UPDATE snapshots SET graph_hash=? WHERE project_id=? AND snapshot_id=?", ("e" * 64, project.project_id, selected))
            else:
                monkeypatch.setattr(snapshot_diff, "monotonic", lambda: scope.deadline + 1)
        return encoded

    monkeypatch.setattr(guarded, "_bytes", encode_then_mutate)
    guarded._write(document)
    assert mutated
    emitted = json.loads(stream.getvalue())
    assert emitted["result"]["isError"] is True
    assert emitted["result"]["structuredContent"]["error"]["code"] == expected
    assert b"PRIVATE_DIFF_OUTPUT" not in stream.getvalue()
