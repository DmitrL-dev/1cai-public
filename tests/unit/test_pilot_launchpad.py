from src.services.rentgen.pilot_launchpad import build_pilot_launchpad


def _executive_report():
    return {
        "decision": {"status": "watch", "score": 78, "headline": "Track yellow areas."},
        "kpis": {"review_queue": 3, "red_areas": 1},
        "risk_summary": {"high_hotspots": 2},
    }


def _scenario_hub():
    return {
        "decision": {"status": "watch", "score": 80, "headline": "Scenarios ready."},
        "scenarios": [
            {
                "id": "left-join-null",
                "title": "LEFT JOIN field without ЕстьNULL",
                "pain": "NULL risk",
                "buyer_line": "Fix it.",
                "route": "/quality",
            },
            {
                "id": "local-enterprise-proof",
                "title": "Local enterprise proof",
                "pain": "AI rent",
                "buyer_line": "Buy local.",
                "route": "/business-case",
            },
        ],
        "recommended_path": [
            {
                "scenario_id": "left-join-null",
                "title": "LEFT JOIN field without ЕстьNULL",
                "route": "/quality",
                "why": "real defect",
            },
            {
                "scenario_id": "local-enterprise-proof",
                "title": "Local enterprise proof",
                "route": "/business-case",
                "why": "local asset",
            },
        ],
    }


def _guided_demo():
    return {"decision": {"status": "watch", "score": 80}, "summary": {"steps": 9}}


def _business_case():
    return {
        "decision": {"status": "ready", "score": 86},
        "assumptions": {"currency": "RUB"},
        "summary": {
            "first_year_visible_value": 4_800_000,
            "ai_subscription_year": 1_440_000,
            "review_queue": 3,
        },
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
            "route": "/pilot-launchpad",
            "status": status,
            "ask": "Move from demo proof to paid activation.",
            "reason": "Pilot, offer and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: move from demo proof to paid activation.",
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
                "label": "Prove",
                "route": "/killer-demo",
                "line": "Show proof.",
            },
            {
                "step": 3,
                "label": "Activate",
                "route": "/pilot-launchpad",
                "line": "Start paid activation.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward packet.",
            },
        ],
        "open_first_path": [
            {
                "step": 1,
                "stage": "orient",
                "label": "Orient",
                "title": "Buyer room",
                "route": "/buyer-concierge",
                "line": "Pick role.",
                "file": "open-first-path.md",
                "status": status,
                "source": "test",
            },
            {
                "step": 2,
                "stage": "prove",
                "label": "Prove",
                "title": "Killer Demo",
                "route": "/killer-demo",
                "line": "Show proof.",
                "file": "OPEN_FIRST_KILLER_DEMO.md",
                "status": status,
                "source": "test",
            },
            {
                "step": 3,
                "stage": "close",
                "label": "Close",
                "title": "Activation",
                "route": "/pilot-launchpad",
                "line": "Start paid activation.",
                "file": "POST_DEMO_ACTIVATION_HANDOFF.md",
                "status": status,
                "source": "test",
            },
            {
                "step": 4,
                "stage": "verify",
                "label": "Verify",
                "title": "Verification Packet ZIP",
                "route": "/evidence-bundle",
                "line": "Verify.",
                "file": "archive-verification-packet.zip",
                "status": "ready",
                "source": "test",
            },
        ],
    }


def test_pilot_launchpad_builds_offers_acceptance_and_procurement_pack():
    report = build_pilot_launchpad(
        executive=_executive_report(),
        scenario_hub=_scenario_hub(),
        guided_demo=_guided_demo(),
        business_case=_business_case(),
        productization=_productization(),
        value_packs={"decision": {"status": "ready", "score": 83}, "packs": [{}, {}]},
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
    assert report["summary"]["pilot_days"] == 30
    assert report["summary"]["offers"] == 4
    assert report["summary"]["acceptance_checks"] >= 6
    assert report["summary"]["procurement_items"] >= 7
    assert report["summary"]["activation_ready"] is True
    assert report["summary"]["activation_gates"] == 7
    assert report["summary"]["acceptance_register_items"] >= 8
    assert report["summary"]["acceptance_register_ready"] is True
    assert report["summary"]["acceptance_register_blocked"] == 0
    assert report["summary"]["pilot_room_roles"] == 5
    assert report["summary"]["pilot_room_proofs"] == 4
    assert report["summary"]["pilot_room_steps"] == 4
    assert report["summary"]["pilot_room_open_first"] == 4
    assert {item["id"] for item in report["pilot_offers"]} >= {
        "day-one-proof",
        "release-pilot",
        "enterprise-local-license",
        "vendor-rollout",
    }
    assert (
        report["activation_contract"]["selected_offer_id"] == "enterprise-local-license"
    )
    assert report["activation_contract"]["ready_to_activate"] is True
    assert any(
        item["filename"] == "rentgen-buyer-room-packet.zip"
        for item in report["activation_contract"]["handoff_files"]
    )
    assert any(
        item["filename"] == "MEETING_CLOSE_RECEIPT.md"
        for item in report["activation_contract"]["handoff_files"]
    )
    assert any(
        item["filename"] == "POST_DEMO_ACTIVATION_HANDOFF.md"
        for item in report["activation_contract"]["handoff_files"]
    )
    assert any(
        item["filename"] == "archive-acceptance-receipt.md"
        for item in report["activation_contract"]["handoff_files"]
    )
    assert any(
        item["filename"] == "archive-verification-packet.zip"
        for item in report["activation_contract"]["handoff_files"]
    )
    pilot_room = report["pilot_room_bridge"]
    assert pilot_room["source"] == "management-buyer-brief"
    assert pilot_room["primary_motion"]["route"] == "/pilot-launchpad"
    assert pilot_room["activation_motion"]["label"] == "30-day local license pilot"
    assert pilot_room["files"][:4] == [
        "rentgen-buyer-room-packet.zip",
        "open-first-path.md",
        "buyer-brief.md",
        "buyer-pulse.md",
    ]
    assert [item["stage"] for item in pilot_room["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert "MEETING_CLOSE_RECEIPT.md" in pilot_room["files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in pilot_room["files"]
    assert "archive-acceptance-receipt.md" in pilot_room["files"]
    assert "archive-verification-packet.zip" in pilot_room["files"]
    assert "/" in pilot_room["routes"]
    assert "/killer-demo" in pilot_room["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["exports"][0]["filename"] == "rentgen-buyer-room-packet.zip"
    assert report["exports"][1]["filename"] == "buyer-brief.md"
    assert report["exports"][2]["filename"] == "buyer-pulse.md"
    assert "MEETING_CLOSE_RECEIPT.md" in [
        item["filename"] for item in report["exports"]
    ]
    assert "archive-acceptance-receipt.json" in [
        item["filename"] for item in report["exports"]
    ]
    assert "archive-verification-packet.zip" in [
        item["filename"] for item in report["exports"]
    ]
    assert {item["route"] for item in report["activation_contract"]["gates"]} >= {
        "/approvals",
        "/audit",
        "/evidence-bundle",
        "/enterprise-trust-center",
    }
    assert {
        item["route"] for item in report["activation_contract"]["buyer_commitments"]
    } >= {
        "/business-case",
        "/approvals",
        "/evidence-bundle",
    }
    assert any(item["role"] == "Developer" for item in report["acceptance_matrix"])
    assert any(
        item["artifact"] == "Buyer Room Packet ZIP"
        for item in report["procurement_pack"]
    )
    assert any(item["owner"] == "Security" for item in report["procurement_pack"])
    assert any(
        item["artifact"] == "Archive Acceptance Receipt"
        for item in report["procurement_pack"]
    )
    assert any(
        item["artifact"] == "Verification Packet ZIP"
        for item in report["procurement_pack"]
    )
    assert any(item["route"] == "/approvals" for item in report["procurement_pack"])
    assert any(item["route"] == "/audit" for item in report["procurement_pack"])
    register = report["acceptance_register"]
    assert register["ready_to_sign"] is True
    assert register["blocked_items"] == 0
    assert any(
        item["id"] == "day0-owner-scope" and item["status"] == "ready"
        for item in register["items"]
    )
    assert any(
        item["id"] == "day0-close-packet"
        and "rentgen-buyer-room-packet.zip" in item["acceptance"]
        for item in register["items"]
    )
    assert any(
        item["id"] == "day0-close-packet"
        and item["evidence_file"] == "archive-acceptance-receipt.md"
        for item in register["items"]
    )
    assert any(
        item["id"] == "day0-verification-packet"
        and item["evidence_file"] == "archive-verification-packet.zip"
        for item in register["items"]
    )
    assert any(
        item["id"] == "day30-conversion" and item["evidence_route"] == "/outcome-ledger"
        for item in register["items"]
    )
    assert "/evidence-bundle" in register["proof_routes"]
    assert any(item["route"] == "/pilot-launchpad" for item in report["exports"])
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "Pilot Launchpad" in report["markdown"]
    assert "Pilot Room Bridge" in report["markdown"]
    assert "Activation Contract" in report["markdown"]
    assert "rentgen-buyer-room-packet.zip" in report["markdown"]
    assert "MEETING_CLOSE_RECEIPT.md" in report["markdown"]
    assert "archive-acceptance-receipt.md" in report["markdown"]
    assert "archive-verification-packet.zip" in report["markdown"]
    assert "open-first-path.md" in report["markdown"]
    assert "Acceptance Register" in report["markdown"]


def test_pilot_launchpad_acceptance_register_blocks_productization_failure():
    report = build_pilot_launchpad(
        executive=_executive_report(),
        scenario_hub=_scenario_hub(),
        guided_demo=_guided_demo(),
        business_case=_business_case(),
        productization={"status": "blocked", "score": 40, "summary": {"findings": 9}},
        value_packs={"decision": {"status": "ready", "score": 83}, "packs": [{}, {}]},
        vendor_portfolio={
            "decision": {"status": "watch", "score": 79},
            "work_packages": [{"id": "platform"}],
        },
        client_name="ACME",
    )

    register = report["acceptance_register"]
    assert register["ready_to_sign"] is False
    assert register["blocked_items"] >= 2
    assert report["pilot_room_bridge"]["source"] == "pilot-launchpad-derived"
    assert report["pilot_room_bridge"]["files"][0] == "rentgen-buyer-room-packet.zip"
    assert report["pilot_room_bridge"]["files"][1] == "open-first-path.md"
    assert report["pilot_room_bridge"]["files"][2] == "buyer-brief.md"
    assert [
        item["stage"] for item in report["pilot_room_bridge"]["open_first_path"]
    ] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert report["summary"]["acceptance_register_ready"] is False
    assert report["summary"]["acceptance_register_blocked"] == register["blocked_items"]
    assert any(
        item["status"] == "blocked" and item["role"] == "Architect"
        for item in register["items"]
    )
