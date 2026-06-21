from src.services.rentgen.demo_command_center import build_demo_command_center


def _executive_report():
    return {"decision": {"status": "watch", "score": 78, "headline": "Track yellow areas."}}


def _scenario_hub():
    return {
        "decision": {"status": "watch", "score": 80},
        "scenarios": [
            {"id": "left-join-null", "title": "LEFT JOIN field without ЕстьNULL"},
            {"id": "platform-upgrade", "title": "Platform update feels unsafe"},
        ],
        "role_lenses": [{"role": "Developer"}, {"role": "Architect"}],
    }


def _guided_demo():
    return {"decision": {"status": "watch", "score": 80}}


def _pilot_launchpad():
    return {"decision": {"status": "ready", "score": 84}, "summary": {"offers": 4, "acceptance_checks": 6}}


def _business_case():
    return {
        "decision": {"status": "ready", "score": 86},
        "summary": {"first_year_visible_value": 4_800_000},
    }


def _productization():
    return {"status": "watch", "score": 81, "summary": {"findings": 4}}


def _buyer_brief(status="ready", score=88):
    return {
        "status": status,
        "score": score,
        "purchase_status": status,
        "source": "management-buyer-brief",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/demo-command-center",
            "status": status,
            "ask": "Run buyer-safe proof and move to paid pilot.",
            "reason": "Demo, pilot and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: run buyer-safe proof and move to paid pilot.",
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
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Show proof."},
            {"step": 3, "label": "Ask", "route": "/pilot-launchpad", "line": "Ask for pilot."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
    }


def test_demo_command_center_builds_live_stages_role_pivots_and_recovery():
    report = build_demo_command_center(
        executive=_executive_report(),
        scenario_hub=_scenario_hub(),
        guided_demo=_guided_demo(),
        pilot_launchpad=_pilot_launchpad(),
        business_case=_business_case(),
        productization=_productization(),
        vendor_portfolio={
            "decision": {"status": "watch", "score": 79},
            "work_packages": [{"id": "platform"}],
        },
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["stages"] >= 8
    assert report["summary"]["role_pivots"] >= 5
    assert report["summary"]["proof_assets"] >= 6
    assert report["summary"]["total_minutes"] <= 8
    assert report["summary"]["demo_room_roles"] == 5
    assert report["summary"]["demo_room_proofs"] == 4
    assert report["summary"]["demo_room_steps"] == 4
    assert report["summary"]["demo_room_open_first"] == 4
    bridge = report["demo_room_bridge"]
    assert bridge["source"] == "management-buyer-brief"
    assert bridge["primary_motion"]["route"] == "/demo-command-center"
    assert bridge["presenter_opening"]["route"] == "/buyer-concierge"
    assert bridge["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in bridge["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in bridge["routes"]
    assert report["exports"][0]["filename"] == "buyer-brief.md"
    assert report["exports"][1]["filename"] == "buyer-pulse.md"
    assert {item["id"] for item in report["live_stages"]} >= {
        "developer-spark",
        "architecture-platform",
        "pilot-close",
        "artifact-close",
    }
    assert {item["role"] for item in report["role_pivots"]} >= {
        "Developer",
        "Architect",
        "Director",
        "Security",
        "Vendor",
    }
    assert "before_demo" in report["live_checklist"]
    assert any(item["route"] == "/demo-command-center" for item in report["exports"])
    assert any(item["route"] == "/quality" for item in report["recovery_cards"])
    assert "Demo Command Center" in report["markdown"]
    assert "Demo Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
