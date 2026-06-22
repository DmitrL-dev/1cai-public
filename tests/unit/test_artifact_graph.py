import pytest

from src.ai.mcp.server import (
    TOOLS,
    handle_artifact_create,
    handle_artifact_link,
    handle_artifact_matrix,
    handle_artifact_trace,
)
from src.services.rentgen import artifact_graph as graph


def test_artifact_graph_links_trace_and_matrix(tmp_path):
    store = tmp_path / "artifact_graph.json"

    requirement = graph.create_artifact(
        {
            "type": "requirement",
            "title": "Credit limit validation",
            "owner": "ba",
            "priority": "high",
            "attributes": {"source": "workshop"},
        },
        path=store,
    )
    module = graph.create_artifact(
        {
            "type": "bsl_module",
            "title": "Documents/Order/Ext/ObjectModule.bsl",
            "owner": "developer",
        },
        path=store,
    )
    test_case = graph.create_artifact(
        {
            "type": "test_case",
            "title": "YAxUnit credit limit posting test",
            "owner": "qa",
        },
        path=store,
    )

    graph.link_artifacts(
        source_id=requirement["id"],
        target_id=module["id"],
        link_type="implements",
        rationale="Posting logic lives in the object module.",
        path=store,
    )
    graph.link_artifacts(
        source_id=requirement["id"],
        target_id=test_case["id"],
        link_type="verifies",
        rationale="Acceptance scenario is covered by unit test.",
        path=store,
    )

    trace = graph.trace_artifact(requirement["id"], path=store)
    matrix = graph.coverage_matrix(path=store)
    health = graph.health(path=store)

    assert trace["summary"]["nodes"] == 3
    assert trace["summary"]["links"] == 2
    assert matrix["summary"]["covered"] == 1
    assert matrix["rows"][0]["coverage"] == "covered"
    assert health["by_type"]["requirement"] == 1


def test_artifact_update_preserves_attributes_and_versions(tmp_path):
    store = tmp_path / "artifact_graph.json"
    item = graph.create_artifact(
        {
            "type": "requirement",
            "title": "Posting validation",
            "attributes": {"source": "ba"},
        },
        path=store,
    )

    updated = graph.update_artifact(
        item["id"],
        {"status": "approved", "attributes": {"baseline": "R1"}},
        path=store,
    )

    assert updated["status"] == "approved"
    assert updated["version"] == 2
    assert updated["attributes"] == {"source": "ba", "baseline": "R1"}


def test_artifact_create_upserts_explicit_id_without_losing_history(tmp_path):
    store = tmp_path / "artifact_graph.json"
    first = graph.create_artifact(
        {
            "id": "REQ-1",
            "type": "requirement",
            "title": "Posting validation",
            "owner": "ba",
        },
        path=store,
    )
    second = graph.create_artifact(
        {
            "id": "REQ-1",
            "type": "requirement",
            "title": "Posting validation",
            "owner": "architect",
        },
        path=store,
    )

    assert second["id"] == "REQ-1"
    assert second["created_at"] == first["created_at"]
    assert second["version"] == 2
    assert graph.list_artifacts(path=store)["total"] == 1


def test_artifact_graph_rejects_unknown_types(tmp_path):
    with pytest.raises(ValueError):
        graph.create_artifact(
            {"type": "unknown", "title": "Bad"}, path=tmp_path / "artifact_graph.json"
        )


@pytest.mark.asyncio
async def test_mcp_artifact_tools_are_registered_and_work(tmp_path, monkeypatch):
    store = tmp_path / "artifact_graph.json"
    monkeypatch.setattr(graph, "STORE_PATH", store)

    names = {tool.name for tool in TOOLS}
    assert {
        "artifact_create",
        "artifact_link",
        "artifact_trace",
        "artifact_matrix",
    } <= names

    requirement = await handle_artifact_create(
        {"type": "requirement", "title": "Credit limit"}
    )
    test_case = await handle_artifact_create(
        {"type": "test_case", "title": "YAxUnit credit limit"}
    )
    link = await handle_artifact_link(
        {
            "source_id": requirement["id"],
            "target_id": test_case["id"],
            "type": "verifies",
            "rationale": "Unit test covers acceptance criteria.",
        }
    )
    trace = await handle_artifact_trace({"artifact_id": requirement["id"]})
    matrix = await handle_artifact_matrix({})

    assert link["type"] == "verifies"
    assert trace["summary"]["nodes"] == 2
    assert matrix["summary"]["partial"] == 1
