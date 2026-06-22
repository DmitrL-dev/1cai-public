from src.services.rentgen.scenario_hub import build_scenario_hub


def _executive_report():
    return {
        "decision": {"status": "watch", "score": 78, "headline": "Track yellow areas."},
        "kpis": {
            "modules": 120,
            "modules_with_issues": 17,
            "red_areas": 1,
            "review_queue": 3,
            "call_edges": 540,
            "offline_score": 92,
            "coverage_score": 89,
        },
        "risk_summary": {"high_hotspots": 2, "top_risks": []},
        "coverage": {"score": 89},
    }


def _guided_demo():
    return {
        "decision": {"status": "watch", "score": 80, "headline": "Usable demo."},
        "summary": {"steps": 9, "total_minutes": 7},
    }


def _business_case():
    return {
        "decision": {"status": "ready", "score": 86, "headline": "Ready for buyer."},
        "summary": {"first_year_visible_value": 4_800_000},
    }


def _productization():
    return {
        "status": "watch",
        "release_decision": "pilot_ready",
        "score": 81,
        "summary": {"deliverables": 31, "findings": 4},
    }


def _buyer_brief(status="ready", score=88):
    return {
        "status": status,
        "score": score,
        "purchase_status": status,
        "source": "management-buyer-brief",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/scenario-hub",
            "status": status,
            "ask": "Pick buyer pain and prove the route.",
            "reason": "Scenario, guided and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: pick buyer pain and prove the route.",
        "role_cards": [
            {
                "role": "developer",
                "title": "Developer",
                "route": "/change",
                "status": "ready",
                "spark": "Show code proof.",
                "proof_file": "rentgen-developer-report.md",
            },
            {
                "role": "architect",
                "title": "Architect",
                "route": "/platform-doctor",
                "status": "ready",
                "spark": "Show platform proof.",
                "proof_file": "rentgen-architect-report.md",
            },
            {
                "role": "director",
                "title": "Director",
                "route": "/board-pack",
                "status": status,
                "spark": "Show value proof.",
                "proof_file": "board-pack.md",
            },
            {
                "role": "security",
                "title": "Security",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "spark": "Show trust proof.",
                "proof_file": "rentgen-security-questionnaire.md",
            },
            {
                "role": "vendor",
                "title": "Vendor",
                "route": "/vendor-portfolio",
                "status": "ready",
                "spark": "Show portfolio proof.",
                "proof_file": "vendor-portfolio.md",
            },
        ],
        "proof_readiness": [
            {
                "id": "evidence-bundle",
                "title": "Forwardable evidence",
                "route": "/evidence-bundle",
                "status": status,
                "signal": "Proof routes and hashes.",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "governance",
                "title": "Approval gates",
                "route": "/approvals",
                "status": "ready",
                "signal": "Governance gates.",
                "file": "governance-proof.md",
            },
            {
                "id": "audit-siem",
                "title": "Audit / SIEM handoff",
                "route": "/audit",
                "status": "ready",
                "signal": "SIEM export.",
                "file": "rentgen-audit-siem.jsonl",
            },
            {
                "id": "trust",
                "title": "Enterprise trust",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "signal": "Trust proof.",
                "file": "rentgen-security-questionnaire.md",
            },
        ],
        "meeting_flow": [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick role.",
            },
            {
                "step": 2,
                "label": "Choose",
                "route": "/scenario-hub",
                "line": "Pick pain.",
            },
            {
                "step": 3,
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show proof.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward packet.",
            },
        ],
    }


def test_scenario_hub_builds_pain_led_gallery():
    report = build_scenario_hub(
        executive=_executive_report(),
        guided_demo=_guided_demo(),
        business_case=_business_case(),
        productization=_productization(),
        value_packs={"decision": {"status": "ready", "score": 83}, "packs": [{}, {}]},
        vendor_portfolio={
            "decision": {"status": "watch", "score": 79},
            "portfolio": {"clients": 1},
            "work_packages": [{"id": "platform"}],
        },
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["scenarios"] >= 10
    assert report["summary"]["killer_scenarios"] >= 2
    assert report["summary"]["scenario_room_roles"] == 5
    assert report["summary"]["scenario_room_proofs"] == 4
    assert report["summary"]["scenario_room_steps"] == 4
    assert report["summary"]["scenario_room_open_first"] == 4
    bridge = report["scenario_room_bridge"]
    assert bridge["source"] == "management-buyer-brief"
    assert bridge["primary_motion"]["route"] == "/scenario-hub"
    assert bridge["scenario_motion"]["route"] in report["proof_routes"]
    assert bridge["files"][:3] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
    ]
    assert [item["stage"] for item in bridge["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert "/killer-demo" in bridge["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["exports"][0]["filename"] == "buyer-brief.md"
    assert report["exports"][1]["filename"] == "buyer-pulse.md"
    scenario_ids = {item["id"] for item in report["scenarios"]}
    assert {
        "left-join-null",
        "platform-upgrade",
        "vendor-presale-audit",
        "local-enterprise-proof",
    } <= scenario_ids
    assert any("ЕстьNULL" in item["title"] for item in report["scenarios"])
    assert len(report["recommended_path"]) >= 4
    assert {item["role"] for item in report["role_lenses"]} >= {
        "Developer",
        "Architect",
        "Director",
        "Vendor",
        "Security",
    }
    assert any(
        item["proof_route"] == "/guided-demo" for item in report["objection_map"]
    )
    assert any(item["route"] == "/scenario-hub" for item in report["exports"])
    assert "/quality" in report["proof_routes"]
    assert "Scenario Hub" in report["markdown"]
    assert "Scenario Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
