from src.api.copilot_coverage_api import COVERAGE_ITEMS, _next_actions, _summary


def test_copilot_coverage_map_has_enterprise_spread():
    stages = {item["stage"] for item in COVERAGE_ITEMS}
    personas = {persona for item in COVERAGE_ITEMS for persona in item["personas"]}

    assert len(COVERAGE_ITEMS) >= 12
    assert {
        "architecture",
        "coding",
        "review",
        "testing",
        "delivery",
        "governance",
        "operations",
    } <= stages
    # HONESTY: statuses are no longer a blanket {"done"}; partial work is admitted.
    statuses = {item["status"] for item in COVERAGE_ITEMS}
    assert statuses <= {"done", "partial", "planned"}
    assert "partial" in statuses
    assert {"developer", "architect", "ba", "qa", "manager"} <= personas


def test_copilot_coverage_score_is_computed_not_hardcoded():
    summary = _summary(COVERAGE_ITEMS)
    actions = _next_actions(COVERAGE_ITEMS)

    partials = sum(1 for item in COVERAGE_ITEMS if item["status"] == "partial")

    assert summary["total_items"] == len(COVERAGE_ITEMS)
    # Score reflects real per-item delivery: with partials present it is < 100.
    assert partials >= 1
    assert summary["partial"] == partials
    assert summary["coverage_score"] < 100
    assert summary["done"] < len(COVERAGE_ITEMS)
    # Non-done items surface as real next actions instead of an empty list.
    assert len(actions) == sum(1 for it in COVERAGE_ITEMS if it["status"] != "done")
    assert all(action["id"] for action in actions)
    assert "not a hardcoded value" in summary["method"]
