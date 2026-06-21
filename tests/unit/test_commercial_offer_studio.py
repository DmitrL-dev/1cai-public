from src.services.rentgen.commercial_offer_studio import build_commercial_offer_studio


def _decision(status="ready", score=86):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


def _business_case():
    return {
        "decision": {"status": "ready", "score": 88},
        "assumptions": {"currency": "RUB"},
        "summary": {
            "first_year_visible_value": 4_800_000,
            "ai_subscription_year": 1_440_000,
        },
        "subscription_escape_plan": {
            "headline": "Buy a local 1C evidence asset; keep AI credits optional.",
            "annual_ai_rent": 1_440_000,
            "three_year_ai_rent": 4_320_000,
            "local_license_anchor": 1_800_000,
            "break_even_months": 5,
            "ai_rent_equivalent_months": 15,
            "decision_line": "Local license anchor equals about 15 months of current AI rent.",
            "guardrails": ["No mandatory external AI subscription for baseline value."],
            "stakeholder_lines": [{"role": "Finance", "line": "Compare rent and local license.", "route": "/business-case"}],
            "evidence_files": [{"title": "Business Case", "filename": "business-case.md", "route": "/business-case"}],
        },
    }


def _buyer_brief(status="ready", score=88):
    return {
        "status": status,
        "score": score,
        "purchase_status": status,
        "source": "management-buyer-brief",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/commercial-offer-studio",
            "status": status,
            "ask": "Move from demo proof to a local product purchase.",
            "reason": "Board, offer and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: move from demo proof to a local product purchase.",
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
            {"step": 3, "label": "Ask", "route": "/commercial-offer-studio", "line": "Ask for local license."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
    }


def test_commercial_offer_studio_builds_buyable_offer_stack():
    report = build_commercial_offer_studio(
        executive=_decision(),
        business_case=_business_case(),
        pilot_launchpad={"decision": {"status": "ready", "score": 85}, "summary": {"offers": 4}},
        enterprise_trust_center={"decision": {"status": "ready", "score": 84}, "summary": {"security_questions": 6}},
        productization={"status": "pass", "score": 90},
        scenario_hub={"decision": {"status": "ready", "score": 83}},
        value_packs={"decision": {"status": "ready", "score": 82}, "packs": [{"title": "Developer Pack"}]},
        vendor_portfolio={
            "decision": {"status": "watch", "score": 79},
            "work_packages": [{"title": "Platform upgrade audit"}],
        },
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["decision"]["status"] == "ready"
    assert report["summary"]["offers"] >= 5
    assert report["summary"]["pricing_tiers"] == 4
    assert report["summary"]["procurement_items"] >= 5
    assert report["summary"]["approval_roles"] >= 4
    assert report["summary"]["checkout_gates"] >= 4
    assert report["summary"]["close_ready"] is True
    assert report["summary"]["offer_room_roles"] == 5
    assert report["summary"]["offer_room_proofs"] == 4
    assert report["summary"]["offer_room_steps"] == 4
    assert report["summary"]["offer_room_open_first"] == 4
    assert report["summary"]["first_year_visible_value"] == 4_800_000
    assert report["procurement_dossier"]["headline"]
    assert report["procurement_dossier"]["recommended_purchase"]["id"] == "enterprise-local-license"
    assert report["procurement_dossier"]["subscription_escape"]["annual_ai_rent"] == "1 440 000 RUB"
    assert report["procurement_dossier"]["subscription_escape"]["three_year_ai_rent"] == "4 320 000 RUB"
    assert report["procurement_dossier"]["subscription_escape"]["local_value_anchor"] == "4 800 000 RUB"
    assert report["procurement_dossier"]["subscription_escape"]["local_license_anchor"] == "1 800 000 RUB"
    assert report["procurement_dossier"]["subscription_escape"]["break_even_months"] == 5
    assert report["subscription_escape_plan"]["local_license_anchor"] == 1_800_000
    assert any(item["owner"] == "security" for item in report["procurement_dossier"]["procurement_pack"])
    assert any(item["role"] == "finance" for item in report["procurement_dossier"]["approval_matrix"])
    assert {item["model"] for item in report["procurement_dossier"]["license_model"]} >= {
        "per installation",
        "per configuration",
        "portfolio",
    }
    assert any(
        "No mandatory external AI subscription" in item
        for item in report["procurement_dossier"]["red_lines"]
    )
    close_packet = report["close_packet"]
    assert close_packet["ready_to_close"] is True
    assert close_packet["close_mode"] == "open_enterprise_purchase"
    assert close_packet["one_page_order"]["value_anchor"] == "4 800 000 RUB"
    assert close_packet["one_page_order"]["three_year_ai_rent"] == "4 320 000 RUB"
    assert close_packet["one_page_order"]["local_license_anchor"] == "1 800 000 RUB"
    assert close_packet["one_page_order"]["break_even"] == "5 months by visible value"
    assert {item["route"] for item in close_packet["checkout"]} >= {
        "/approvals",
        "/audit",
        "/evidence-bundle",
    }
    assert {item["route"] for item in close_packet["evidence_requirements"]} >= {
        "/approvals",
        "/audit",
        "/productization",
    }
    assert any(
        item["artifact"] == "Archive Acceptance Receipt" and item["route"] == "/evidence-bundle"
        for item in close_packet["evidence_requirements"]
    )
    assert any(
        item["artifact"] == "Archive Acceptance Receipt"
        for item in report["procurement_dossier"]["procurement_pack"]
    )
    offer_room = report["offer_room_bridge"]
    assert offer_room["source"] == "management-buyer-brief"
    assert offer_room["primary_motion"]["route"] == "/commercial-offer-studio"
    assert offer_room["recommended_purchase"]["title"] == "Enterprise local license"
    assert offer_room["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in offer_room["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in offer_room["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["exports"][0]["filename"] == "buyer-brief.md"
    assert report["exports"][1]["filename"] == "buyer-pulse.md"
    assert {item["id"] for item in report["offers"]} >= {
        "proof-sprint",
        "enterprise-local-license",
        "vendor-portfolio-rollout",
    }
    assert any(item["route"] == "/commercial-offer-studio" for item in report["exports"])
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "/enterprise-trust-center" in report["proof_routes"]
    assert "Commercial Offer Studio" in report["markdown"]
    assert "Procurement Dossier" in report["markdown"]
    assert "Offer Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
    assert "Close Packet" in report["markdown"]
    assert "archive-acceptance-receipt.md" in report["markdown"]
    assert "License model" in report["markdown"]
    assert "Three-year AI rent" in report["markdown"]


def test_commercial_offer_studio_keeps_caveats_visible_when_trust_is_risky():
    report = build_commercial_offer_studio(
        executive=_decision(status="watch", score=70),
        business_case=_business_case(),
        pilot_launchpad={"decision": {"status": "watch", "score": 70}, "summary": {"offers": 4}},
        enterprise_trust_center={"decision": {"status": "risk", "score": 45}, "summary": {"security_questions": 6}},
        productization={"status": "fail", "score": 40},
        scenario_hub={"decision": {"status": "watch", "score": 74}},
        value_packs={"decision": {"status": "watch", "score": 72}, "packs": []},
        vendor_portfolio={"decision": {"status": "watch", "score": 70}, "work_packages": []},
        client_name="ACME",
    )

    assert report["decision"]["status"] == "risk"
    assert report["procurement_dossier"]["recommended_purchase"]["id"] == "platform-trust-pack"
    assert report["offer_room_bridge"]["source"] == "commercial-offer-derived"
    assert report["offer_room_bridge"]["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert report["close_packet"]["ready_to_close"] is False
    assert report["close_packet"]["close_mode"] == "sell_hardening_before_rollout"
    assert report["summary"]["deal_risks"] >= 4
    assert any(item["route"] == "/productization" for item in report["deal_risks"])
