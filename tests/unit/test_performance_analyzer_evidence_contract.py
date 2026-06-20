import pytest

from src.ai.agents.performance_analyzer import (
    PERFORMANCE_CONTRACT,
    PerformanceAnalyzer,
)


@pytest.mark.asyncio
async def test_performance_analyzer_does_not_fabricate_without_metrics():
    analyzer = PerformanceAnalyzer()

    result = await analyzer.analyze_performance("ERP")

    assert result["mode"] == PERFORMANCE_CONTRACT
    assert result["coverage"] == "no_runtime_metrics"
    assert result["measured"] is False
    assert result["bottlenecks"] == []
    assert result["apdex_score"] is None
    assert result["apdex_measured"] is False
    assert result["performance_grade"] == "unknown"
    assert result["scalability_assessment"]["current_capacity"] is None
    assert result["estimated_improvement"]["potential_speedup"] == "not_estimated"
    assert "Отчет.ПродажиЗаПериод" not in str(result)
    assert "Документ.Заказ.ПриПроведении" not in str(result)


@pytest.mark.asyncio
async def test_performance_analyzer_uses_supplied_metrics_only():
    analyzer = PerformanceAnalyzer()

    result = await analyzer.analyze_performance(
        "ERP",
        {
            "current_users": 120,
            "growth_factor": 3,
            "memory_usage": 0.91,
            "cpu_usage": 0.42,
            "response_times": [1.0, 2.5, 9.0],
            "slow_queries": [
                {
                    "location": "Report.Inventory",
                    "avg_duration_ms": 4200,
                    "threshold_seconds": 3,
                    "query_type": "report_generation",
                    "executions": 17,
                },
                {
                    "location": "Fast.Query",
                    "avg_time": 0.5,
                    "threshold": 3,
                },
            ],
        },
    )

    assert result["mode"] == PERFORMANCE_CONTRACT
    assert result["measured"] is True
    assert "slow_queries" in result["coverage"]
    assert "resource_thresholds" in result["coverage"]
    assert result["apdex_score"] == 0.5
    assert result["performance_grade"] == "Poor"
    assert result["scalability_assessment"]["current_capacity"] == "120 users"
    assert result["scalability_assessment"]["predicted_capacity"] == "360 users (12 months)"

    bottleneck_locations = {item["location"] for item in result["bottlenecks"]}
    assert "Report.Inventory" in bottleneck_locations
    assert "Fast.Query" not in bottleneck_locations
    assert any(item["type"] == "high_memory" for item in result["bottlenecks"])
    assert result["estimated_improvement"]["caveat"]


@pytest.mark.asyncio
async def test_performance_analyzer_marks_partial_metrics():
    analyzer = PerformanceAnalyzer()

    result = await analyzer.analyze_performance(
        "ERP",
        {"cpu_usage": 0.9},
    )

    assert result["coverage"] == "resource_thresholds"
    assert result["apdex_score"] is None
    assert "response time samples for Apdex" in result["required_evidence"]
    assert "slow query log or top SQL report" in result["required_evidence"]
    assert any(item["type"] == "high_cpu" for item in result["bottlenecks"])


@pytest.mark.asyncio
async def test_performance_analyzer_normalizes_string_metrics():
    analyzer = PerformanceAnalyzer()

    result = await analyzer.analyze_performance(
        "ERP",
        {
            "current_users": "10",
            "growth_factor": "2.5",
            "memory_usage": "0.91",
            "cpu_usage": "not-a-number",
            "response_times": ["1.0", "2,5", "bad"],
            "slow_queries": [
                {
                    "location": "Report.StringMetrics",
                    "avg_duration_ms": "4500",
                    "threshold_seconds": "3",
                    "executions": "7",
                }
            ],
        },
    )

    assert result["apdex_score"] == 0.75
    assert result["scalability_assessment"]["current_capacity"] == "10 users"
    assert result["scalability_assessment"]["predicted_capacity"] == "25 users (12 months)"
    assert any(
        item["location"] == "Report.StringMetrics"
        for item in result["bottlenecks"]
    )
    assert any(item["type"] == "high_memory" for item in result["bottlenecks"])
    assert not any(item["type"] == "high_cpu" for item in result["bottlenecks"])
