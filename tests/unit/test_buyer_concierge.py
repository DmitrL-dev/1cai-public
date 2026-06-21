from src.services.rentgen.buyer_concierge import build_buyer_concierge


def _decision(status="ready", score=86):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


def _scenario_hub():
    return {
        "decision": {"status": "ready", "score": 84},
        "scenarios": [
            {
                "id": "left-join-null",
                "title": "LEFT JOIN field without NULL guard",
                "pain": "Wrong totals after missing joined rows.",
                "primary_role": "developer",
                "route": "/quality",
                "why_buy_now": "Concrete 1C bug class.",
                "minutes": 1,
            },
            {
                "id": "local-enterprise-proof",
                "title": "We do not want another endless AI subscription",
                "pain": "Token rent and cloud exposure.",
                "primary_role": "director",
                "route": "/business-case",
                "why_buy_now": "Board-level reason to buy.",
                "minutes": 1,
            },
        ],
    }


def _business_case():
    return {
        "decision": {"status": "ready", "score": 88},
        "assumptions": {"currency": "RUB", "monthly_ai_subscription_cost": 120_000},
        "summary": {
            "first_year_visible_value": 4_800_000,
            "ai_subscription_year": 1_440_000,
            "three_year_ai_subscription": 4_320_000,
            "local_license_anchor": 1_800_000,
            "subscription_escape_months": 15,
            "subscription_break_even_months": 5,
        },
        "subscription_escape_plan": {
            "headline": "Buy a local 1C evidence asset; keep AI credits optional.",
            "monthly_ai_rent": 120_000,
            "annual_ai_rent": 1_440_000,
            "three_year_ai_rent": 4_320_000,
            "local_license_anchor": 1_800_000,
            "break_even_months": 5,
            "ai_rent_equivalent_months": 15,
            "currency": "RUB",
            "decision_line": "Local license beats endless AI rent.",
            "guardrails": ["AI credits stay optional."],
            "evidence_files": [
                {"title": "Business Case", "filename": "business-case.md", "route": "/business-case"},
                {"title": "Evidence Bundle", "filename": "OPEN_FIRST.md", "route": "/evidence-bundle"},
            ],
        },
    }


def _trust(status="ready", score=84):
    return {
        "decision": {"status": status, "score": score},
        "summary": {"controls": 9, "failed_controls": 0},
    }


def _offer(score=86):
    return {
        "decision": {"status": "ready", "score": score},
        "summary": {"offers": 5},
        "offers": [{"id": "vendor-portfolio-rollout", "commercial_frame": "partner rollout anchor 2 400 000 RUB"}],
        "procurement_dossier": {
            "recommended_purchase": {
                "id": "enterprise-local-license",
                "title": "Enterprise local license",
                "route": "/commercial-offer-studio",
                "commercial_frame": "fixed local license",
                "acceptance": "Owner, scope and proof artifacts accepted.",
            },
            "subscription_escape": {
                "annual_ai_rent": "1 440 000 RUB",
                "three_year_ai_rent": "4 320 000 RUB",
                "local_value_anchor": "4 800 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even_months": 5,
                "ai_rent_equivalent_months": 15,
                "guardrails": ["AI credits stay optional."],
            },
        },
        "close_packet": {
            "ready_to_close": True,
            "close_mode": "open_enterprise_purchase",
            "primary_ask": "Open enterprise local-license procurement.",
            "one_page_order": {
                "recommended_purchase": "Enterprise local license",
                "commercial_frame": "fixed local license",
                "value_anchor": "4 800 000 RUB",
                "three_year_ai_rent": "4 320 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even": "5 months by visible value",
                "first_invoice_trigger": "Buyer names owner, scope, date and accepted proof artifacts.",
                "route": "/commercial-offer-studio",
            },
        },
    }


def _buyer_brief():
    return {
        "status": "ready",
        "score": 91,
        "purchase_status": "ready",
        "source": "management-buyer-brief",
        "room_line": "Ask for local license: move from proof to product. AI baseline: 4 320 000 RUB over three years.",
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


def test_buyer_concierge_builds_first_click_guidance():
    report = build_buyer_concierge(
        executive=_decision(),
        scenario_hub=_scenario_hub(),
        guided_demo=_decision(score=82),
        pilot_launchpad={"decision": {"status": "ready", "score": 85}, "summary": {"offers": 4}},
        enterprise_trust_center=_trust(),
        commercial_offer_studio=_offer(),
        business_case=_business_case(),
        productization={"status": "pass", "score": 90},
        vendor_portfolio={"decision": {"status": "ready", "score": 80}, "work_packages": [{"id": "audit"}]},
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["persona_cards"] >= 7
    assert report["summary"]["shortest_paths"] >= 4
    assert report["summary"]["guardrails"] >= 6
    assert report["summary"]["purchase_router_status"] == "ready"
    assert report["summary"]["concierge_room_roles"] == 5
    assert report["summary"]["concierge_room_proofs"] == 4
    assert report["summary"]["concierge_room_steps"] == 4
    assert report["summary"]["concierge_room_open_first"] == 4
    assert report["default_next_action"]["route"] == "/commercial-offer-studio"
    assert {item["id"] for item in report["persona_cards"]} >= {"developer", "architect", "director", "security"}
    director = next(item for item in report["persona_cards"] if item["id"] == "director")
    assert director["purchase_route"] == "/launch-room"
    assert director["proof_file"] == "launch-room.md"
    assert report["purchase_router"]["status"] == "ready"
    assert report["purchase_router"]["primary_route"] == "/launch-room"
    bridge = report["concierge_room_bridge"]
    assert [item["stage"] for item in bridge["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert bridge["files"][2] == "open-first-path.md"
    assert "Open-First Path" in report["markdown"]
    assert report["purchase_router"]["recommended_purchase"] == "Enterprise local license"
    assert report["purchase_router"]["three_year_ai_rent"] == "4 320 000 RUB"
    assert report["purchase_router"]["local_license_anchor"] == "1 800 000 RUB"
    assert report["purchase_router"]["break_even"] == "5 months by visible value"
    assert "/launch-room" in report["purchase_router"]["proof_routes"]
    assert report["concierge_room_bridge"]["source"] == "management-buyer-brief"
    assert report["concierge_room_bridge"]["primary_motion"]["route"] == "/board-pack"
    assert report["concierge_room_bridge"]["files"][:2] == ["buyer-brief.md", "buyer-pulse.md"]
    assert report["exports"][:2] == [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
    ]
    assert any(item["scenario_id"] == "left-join-null" for item in report["pain_picker"])
    assert "/buyer-concierge" in report["proof_routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert "/launch-room" in report["proof_routes"]
    assert "Concierge Room Bridge" in report["markdown"]
    assert "Purchase Router" in report["markdown"]
    assert "4 320 000 RUB" in report["markdown"]


def test_buyer_concierge_starts_with_trust_when_trust_is_risky():
    report = build_buyer_concierge(
        executive=_decision(status="watch", score=70),
        scenario_hub=_scenario_hub(),
        guided_demo=_decision(status="watch", score=72),
        pilot_launchpad={"decision": {"status": "watch", "score": 70}, "summary": {"offers": 4}},
        enterprise_trust_center=_trust(status="risk", score=45),
        commercial_offer_studio=_offer(score=60),
        business_case=_business_case(),
        productization={"status": "fail", "score": 40},
        vendor_portfolio={"decision": {"status": "watch", "score": 70}, "work_packages": []},
        client_name="ACME",
    )

    assert report["decision"]["status"] == "risk"
    assert report["default_next_action"]["route"] == "/enterprise-trust-center"
    assert report["summary"]["trust_controls"] == 9
    assert report["purchase_router"]["status"] == "watch"
    assert report["concierge_room_bridge"]["source"] == "buyer-concierge-derived"
