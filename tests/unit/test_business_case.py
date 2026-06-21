from src.services.rentgen.business_case import build_business_case, normalize_assumptions


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


def _platform_report():
    return {
        "decision": {"status": "watch", "score": 82},
        "inventory": {"configuration_name": "DemoERP", "configuration_version": "1.0"},
        "checks": [
            {"id": "platform-version", "status": "pass"},
            {"id": "tech-journal", "status": "warn"},
        ],
        "caveats": [],
    }


def _intake_report():
    return {
        "decision": {"status": "ready", "score": 76},
        "inventory": {"bsl_files": 10, "xml_files": 12},
        "caveats": [],
    }


def _buyer_brief():
    return {
        "status": "ready",
        "score": 90,
        "purchase_status": "ready",
        "source": "management-buyer-brief",
        "room_line": "Ask for local license: move from proof to product. AI baseline: 7 200 000 RUB over three years.",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/board-pack",
            "status": "ready",
            "ask": "Move from demo proof to a local product purchase.",
            "reason": "Buyer pulse is ready.",
        },
        "role_cards": [
            {"role": "developer", "title": "Developer", "route": "/change", "status": "ready", "spark": "impact proof", "proof_file": "rentgen-developer-report.md"},
            {"role": "architect", "title": "Architect", "route": "/platform-doctor", "status": "ready", "spark": "platform proof", "proof_file": "rentgen-architect-report.md"},
            {"role": "director", "title": "Director", "route": "/board-pack", "status": "ready", "spark": "money proof", "proof_file": "board-pack.md"},
            {"role": "security", "title": "Security", "route": "/enterprise-trust-center", "status": "ready", "spark": "trust proof", "proof_file": "rentgen-security-questionnaire.md"},
            {"role": "vendor", "title": "Vendor", "route": "/vendor-portfolio", "status": "ready", "spark": "audit proof", "proof_file": "vendor-portfolio.md"},
        ],
        "proof_readiness": [
            {"id": "bundle", "title": "Evidence Bundle", "route": "/evidence-bundle", "status": "ready", "signal": "hashed proof", "file": "OPEN_FIRST.md"},
            {"id": "approval", "title": "Approval gates", "route": "/approvals", "status": "ready", "signal": "governance proof", "file": "governance-proof.md"},
            {"id": "audit", "title": "Audit / SIEM", "route": "/audit", "status": "ready", "signal": "hash chain", "file": "rentgen-audit-siem.jsonl"},
            {"id": "trust", "title": "Enterprise Trust", "route": "/enterprise-trust-center", "status": "ready", "signal": "questionnaire", "file": "rentgen-security-questionnaire.md"},
        ],
        "meeting_flow": [
            {"step": 1, "label": "Orient", "route": "/buyer-concierge", "line": "Pick the role."},
            {"step": 2, "label": "Prove", "route": "/killer-demo", "line": "Show proof."},
            {"step": 3, "label": "Ask", "route": "/board-pack", "line": "Ask for purchase."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
    }


def test_business_case_builds_money_map_and_buyer_committee():
    report = build_business_case(
        executive=_executive_report(),
        platform=_platform_report(),
        intake=_intake_report(),
        vendor={"work_packages": [{"title": "Risk audit"}]},
        value_packs={"packs": [{"title": "Developer Pack"}, {"title": "Platform Pack"}]},
        client_name="ACME",
        assumptions={"monthly_ai_subscription_cost": 200_000},
        buyer_brief=_buyer_brief(),
    )

    assert report["client"]["name"] == "ACME"
    assert report["client"]["configuration"] == "DemoERP"
    assert report["assumptions"]["monthly_ai_subscription_cost"] == 200_000
    assert report["summary"]["ai_subscription_year"] == 2_400_000
    assert report["summary"]["three_year_ai_subscription"] == 7_200_000
    assert report["summary"]["local_license_anchor"] >= 1_800_000
    assert report["summary"]["subscription_escape_months"] > 0
    assert report["summary"]["first_year_visible_value"] > 4_000_000
    assert report["summary"]["work_packages"] == 1
    assert report["summary"]["business_room_roles"] == 5
    assert report["summary"]["business_room_proofs"] == 4
    assert report["summary"]["business_room_steps"] == 4
    assert report["summary"]["business_room_open_first"] == 4
    assert report["subscription_escape_plan"]["annual_ai_rent"] == 2_400_000
    assert report["business_room_bridge"]["source"] == "management-buyer-brief"
    assert report["business_room_bridge"]["primary_motion"]["route"] == "/board-pack"
    assert report["business_room_bridge"]["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in report["business_room_bridge"]["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in report["business_room_bridge"]["routes"]
    assert "local 1C evidence asset" in report["subscription_escape_plan"]["headline"]
    assert any(item["role"] == "Finance" for item in report["subscription_escape_plan"]["stakeholder_lines"])
    assert any(item["filename"] == "OPEN_FIRST.md" for item in report["subscription_escape_plan"]["evidence_files"])
    assert any(item["id"] == "subscription-displacement" for item in report["business_levers"])
    assert any(item["role"] == "Director" and item["route"] == "/business-case" for item in report["buyer_committee"])
    assert "Subscription escape" in report["markdown"]
    assert "Business Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
    assert "Business Case" in report["markdown"]


def test_business_case_room_bridge_has_fallback_without_buyer_brief():
    report = build_business_case(
        executive=_executive_report(),
        platform=_platform_report(),
        intake=_intake_report(),
        assumptions={"monthly_ai_subscription_cost": 200_000},
    )

    assert report["business_room_bridge"]["source"] == "business-case-derived"
    assert report["business_room_bridge"]["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in report["business_room_bridge"]["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert report["summary"]["business_room_roles"] == 5


def test_business_case_assumptions_are_bounded():
    assumptions = normalize_assumptions(
        {
            "monthly_ai_subscription_cost": -10,
            "hourly_rate": "bad",
            "manual_review_hours_month": 10_000_000,
            "currency": "RUB-VERY-LONG-CODE",
        }
    )

    assert assumptions["monthly_ai_subscription_cost"] == 0
    assert assumptions["hourly_rate"] == 2_500
    assert assumptions["manual_review_hours_month"] == 20_000
    assert assumptions["currency"] == "RUB-VERY-LON"
