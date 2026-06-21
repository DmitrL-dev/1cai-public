from src.services.rentgen.guided_demo import build_guided_demo


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
        "offline": {"runtime": {"environment": "development"}},
        "manager_actions": [],
    }


def _business_case():
    return {
        "decision": {"status": "ready", "score": 86, "headline": "Ready for buyer."},
        "assumptions": {"currency": "RUB"},
        "summary": {"first_year_visible_value": 4_800_000},
        "objections": [
            {
                "question": "Is this just another AI subscription?",
                "answer": "No, local evidence remains useful without external AI.",
                "proof_route": "/offline-readiness",
            }
        ],
    }


def _productization():
    return {
        "status": "warn",
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
            "route": "/guided-demo",
            "status": status,
            "ask": "Run guided proof and forward artifacts.",
            "reason": "Guided, demo and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: run guided proof and forward artifacts.",
        "role_cards": [
            {"role": "developer", "title": "Developer", "route": "/change", "status": "ready", "spark": "Show code proof.", "proof_file": "rentgen-developer-report.md"},
            {"role": "architect", "title": "Architect", "route": "/platform-doctor", "status": "ready", "spark": "Show platform proof.", "proof_file": "rentgen-architect-report.md"},
            {"role": "director", "title": "Director", "route": "/board-pack", "status": status, "spark": "Show value proof.", "proof_file": "board-pack.md"},
            {"role": "security", "title": "Security", "route": "/enterprise-trust-center", "status": "ready", "spark": "Show trust proof.", "proof_file": "rentgen-security-questionnaire.md"},
            {"role": "vendor", "title": "Vendor", "route": "/vendor-portfolio", "status": "ready", "spark": "Show portfolio proof.", "proof_file": "vendor-portfolio.md"},
        ],
        "proof_readiness": [
            {"id": "evidence-bundle", "title": "Forwardable evidence", "route": "/evidence-bundle", "status": status, "signal": "Proof routes and hashes.", "file": "OPEN_FIRST.md"},
            {"id": "governance", "title": "Approval gates", "route": "/approvals", "status": "ready", "signal": "Governance gates.", "file": "governance-proof.md"},
            {"id": "audit-siem", "title": "Audit / SIEM handoff", "route": "/audit", "status": "ready", "signal": "SIEM export.", "file": "rentgen-audit-siem.jsonl"},
            {"id": "trust", "title": "Enterprise trust", "route": "/enterprise-trust-center", "status": "ready", "signal": "Trust proof.", "file": "rentgen-security-questionnaire.md"},
        ],
        "meeting_flow": [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick role."},
            {"step": 2, "label": "Guide", "route": "/guided-demo", "line": "Walk route."},
            {"step": 3, "label": "Prove", "route": "/killer-demo", "line": "Show proof."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
    }


def test_guided_demo_builds_role_routes_and_close_artifacts():
    report = build_guided_demo(
        executive=_executive_report(),
        demo_story={"demo_steps": [{"id": "open"}]},
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
    assert report["summary"]["steps"] >= 8
    assert report["summary"]["total_minutes"] <= 8
    assert report["summary"]["guided_room_roles"] == 5
    assert report["summary"]["guided_room_proofs"] == 4
    assert report["summary"]["guided_room_steps"] == 4
    assert report["summary"]["guided_room_open_first"] == 4
    bridge = report["guided_room_bridge"]
    assert bridge["source"] == "management-buyer-brief"
    assert bridge["primary_motion"]["route"] == "/guided-demo"
    assert bridge["guided_path"]["route"] == "/"
    assert bridge["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in bridge["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in bridge["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["exports"][0]["filename"] == "buyer-brief.md"
    assert report["exports"][1]["filename"] == "buyer-pulse.md"
    assert {item["role"] for item in report["guided_steps"]} >= {
        "developer",
        "architect",
        "director",
        "vendor",
    }
    routes = {item["route"] for item in report["guided_steps"]}
    assert "/business-case" in routes
    assert "/productization" in routes
    assert "/evidence-bundle" in routes
    assert any(item["role"] == "Security / Enterprise IT" for item in report["role_paths"])
    assert any(item["proof_route"] == "/productization" for item in report["objection_cards"])
    assert any(item["route"] == "/guided-demo" for item in report["exports"])
    assert "Guided Demo" in report["markdown"]
    assert "Guided Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
