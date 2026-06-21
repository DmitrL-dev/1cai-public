import pytest

from src.ai.agents.sql_optimizer import SQL_EVIDENCE_CONTRACT, SQLOptimizer


@pytest.mark.asyncio
async def test_sql_optimizer_rewrites_only_safe_or_to_in():
    optimizer = SQLOptimizer("postgresql")
    query = (
        "SELECT id FROM orders WHERE status = 'new' OR status = 'paid' "
        "OR status = 'hold' OR status = 'ship' OR status = 'done' "
        "OR status = 'cancel' OR status = 'archived'"
    )

    result = await optimizer.optimize_query(query)

    assert result["mode"] == SQL_EVIDENCE_CONTRACT
    assert result["rewrite_status"] == "rewritten"
    assert "status IN (" in result["optimized_query"]
    assert "TODO" not in result["optimized_query"]
    assert result["speedup_factor"] == "not_measured"
    assert result["improvement_measured"] is False
    assert "EXPLAIN/ANALYZE plan" in result["required_evidence"]
    assert all(isinstance(item, dict) for item in result["optimizations"])


@pytest.mark.asyncio
async def test_sql_optimizer_does_not_fabricate_not_exists_rewrite():
    optimizer = SQLOptimizer("postgresql")
    query = "SELECT id FROM orders WHERE id NOT IN (SELECT order_id FROM returns)"

    result = await optimizer.optimize_query(query)

    assert result["rewrite_status"] == "needs_evidence"
    assert result["optimized_query"] == query
    assert any(
        item["issue_type"] == "NOT_IN_WITH_NULLS"
        and item["rewrite_status"] == "needs_evidence"
        for item in result["optimizations"]
    )
    assert "NOT EXISTS" not in result["optimized_query"]
    assert result["confidence"] == 0.0


@pytest.mark.asyncio
async def test_sql_optimizer_database_config_requires_hardware_evidence():
    optimizer = SQLOptimizer("postgresql")

    missing = await optimizer.recommend_database_config("postgresql", {})
    configured = await optimizer.recommend_database_config(
        "postgresql",
        {"ram_gb": 32, "cpu_cores": 8, "ssd": True},
    )

    assert missing["status"] == "needs_evidence"
    assert missing["recommended_config"] == {}
    assert {"ram_gb", "cpu_cores"} == set(missing["required_evidence"])

    assert configured["status"] == "success"
    assert configured["mode"] == SQL_EVIDENCE_CONTRACT
    assert configured["recommended_config"]["shared_buffers"] == "8192MB"
    assert configured["estimated_improvement"] == "not_measured_requires_benchmark"
