from src.services.rentgen.coverage_ledger import build_coverage_ledger


def test_coverage_ledger_never_treats_missing_inputs_as_safe():
    ledger = build_coverage_ledger()

    assert ledger["status"] == "risk"
    assert ledger["summary"]["items"] == 1
    assert ledger["summary"]["unknown"] == 1
    assert ledger["summary"]["caveats"] == 1
    assert "not measured" in ledger["caveats"][0]


def test_coverage_ledger_combines_executive_intake_and_platform_caveats():
    ledger = build_coverage_ledger(
        executive={
            "available": True,
            "decision": {"status": "watch", "score": 78, "headline": "Watch"},
            "kpis": {"modules": 10, "call_edges": 20},
            "coverage": {"score": 80, "done": 8, "total": 10},
            "offline": {"decision": {"status": "pass", "score": 96}},
            "risk_summary": {"high_hotspots": 1},
        },
        intake={
            "decision": {
                "status": "partial",
                "score": 55,
                "headline": "Partial source",
            },
            "coverage": [
                {"id": "bsl", "title": "BSL", "status": "ready", "count": 5},
                {
                    "id": "rights",
                    "title": "Rights",
                    "status": "missing",
                    "count": 0,
                    "caveat": "Rights missing",
                },
            ],
        },
        platform={
            "decision": {"status": "risk", "score": 58, "headline": "Platform risk"},
            "checks": [
                {
                    "id": "platform-version",
                    "title": "Platform version",
                    "status": "warn",
                    "action": "Set version",
                },
            ],
        },
    )

    assert ledger["status"] == "risk"
    assert ledger["summary"]["items"] == 10
    assert ledger["summary"]["measured"] >= 7
    assert ledger["summary"]["caveats"] >= 5
    assert {item["id"] for item in ledger["items"]} >= {
        "local-store",
        "workflow-coverage",
        "intake-rights",
        "platform-doctor",
    }
