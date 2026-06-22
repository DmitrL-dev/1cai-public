from src.services.rentgen.board_pack import build_board_pack


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
    }


def _buyer_concierge(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "default_next_action": {"route": "/commercial-offer-studio"},
        "persona_cards": [
            {
                "role": "Developer",
                "first_question": "Can it catch a real bug?",
                "start_route": "/quality",
                "proof": "Show LEFT JOIN/NULL proof.",
                "buy_trigger": "A real review is saved.",
            },
            {
                "role": "Director",
                "first_question": "Why buy?",
                "start_route": "/business-case",
                "proof": "Show value and offer.",
                "buy_trigger": "Local product value beats AI rent.",
            },
            {
                "role": "Security / CIO",
                "first_question": "Can it stay local?",
                "start_route": "/enterprise-trust-center",
                "proof": "Show trust artifacts.",
                "buy_trigger": "Pilot artifacts are named.",
            },
        ],
    }


def _buyer_brief(status="ready", score=88):
    return {
        "status": status,
        "score": score,
        "purchase_status": status,
        "source": "management-buyer-brief",
        "primary_motion": {
            "label": "Ask for local license",
            "route": "/board-pack",
            "status": status,
            "ask": "Move from demo proof to a local product purchase.",
            "reason": "Board, offer and evidence routes can support the close.",
        },
        "room_line": "Ask for local license: move from demo proof to a local product purchase.",
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
                "label": "Ask",
                "route": "/board-pack",
                "line": "Ask for local license.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward packet.",
            },
        ],
    }


def _commercial_offer(status="ready", score=88):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "first_year_visible_value": 4_800_000,
            "currency": "RUB",
            "close_ready": status == "ready",
            "checkout_gates": 4,
        },
        "offers": [
            {
                "id": "proof-sprint",
                "title": "24-hour proof sprint",
                "commercial_frame": "fixed proof from 180 000 RUB",
                "route": "/scenario-hub",
                "acceptance": "Buyer can repeat proof.",
            },
            {
                "id": "enterprise-local-license",
                "title": "Enterprise local license",
                "commercial_frame": "annual local license anchor 1 800 000 RUB",
                "route": "/commercial-offer-studio",
                "acceptance": "Finance and security approve.",
            },
            {
                "id": "platform-trust-pack",
                "title": "Platform and trust hardening pack",
                "commercial_frame": "scoped hardening package from 450 000 RUB",
                "route": "/enterprise-trust-center",
                "acceptance": "Trust blockers have owners.",
            },
        ],
        "stakeholder_closers": [
            {
                "role": "Developer",
                "buy_trigger": "A real defect is caught.",
                "proof_route": "/quality",
                "close_line": "Start with LEFT JOIN/NULL proof.",
            },
            {
                "role": "Director",
                "buy_trigger": "Local value is larger than AI rent.",
                "proof_route": "/business-case",
                "close_line": "Use value as license anchor.",
            },
        ],
        "deal_risks": [
            {
                "risk": "Finance treats it as another AI line.",
                "route": "/business-case",
                "mitigation": "Separate local value and AI credits.",
            }
        ],
        "close_packet": {
            "ready_to_close": status == "ready",
            "close_mode": "open_enterprise_purchase"
            if status == "ready"
            else "sell_paid_proof_sprint",
            "primary_ask": "Open enterprise local-license procurement with the proof packet attached.",
            "one_page_order": {
                "product": "1C Rentgen local evidence control plane",
                "recommended_purchase": "Enterprise local license",
                "commercial_frame": "annual local license anchor 1 800 000 RUB",
                "value_anchor": "4 800 000 RUB first-year visible value",
                "ai_rent_baseline": "1 440 000 RUB annual AI rent",
                "three_year_ai_rent": "4 320 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even": "5 months by visible value",
                "first_invoice_trigger": "Board names owner, scope, date and accepted proof artifacts.",
                "route": "/commercial-offer-studio",
            },
            "buyer_commitments": [
                {
                    "role": "finance",
                    "commitment": "Accept local value anchor.",
                    "route": "/business-case",
                },
                {
                    "role": "security",
                    "commitment": "Confirm approval and audit evidence.",
                    "route": "/approvals",
                },
                {
                    "role": "sponsor",
                    "commitment": "Approve paid next step.",
                    "route": "/commercial-offer-studio",
                },
            ],
            "evidence_requirements": [
                {
                    "artifact": "Evidence Bundle ZIP",
                    "route": "/evidence-bundle",
                    "why": "Forwardable proof.",
                },
                {
                    "artifact": "Governance proof",
                    "route": "/approvals",
                    "why": "Approval records.",
                },
                {
                    "artifact": "Audit verify",
                    "route": "/audit",
                    "why": "Hash-chain proof.",
                },
            ],
            "checkout": [
                {
                    "gate": "Approval record exists",
                    "route": "/approvals",
                    "evidence": "Scoped approval record.",
                },
                {
                    "gate": "Audit chain is valid",
                    "route": "/audit",
                    "evidence": "valid=true broken=0.",
                },
                {
                    "gate": "Proof archive is exportable",
                    "route": "/evidence-bundle",
                    "evidence": "ZIP with manifest.",
                },
                {
                    "gate": "Trust caveats are visible",
                    "route": "/enterprise-trust-center",
                    "evidence": "Named caveats.",
                },
            ],
            "close_script": [
                "Approve the paid next step only with evidence attached.",
                "The price is anchored to local evidence value, not token usage.",
            ],
        },
    }


def _trust_center(status="ready", score=84, failed_controls=0):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "failed_controls": failed_controls,
            "passed_controls": 8,
            "controls": 9,
        },
        "risk_register": [
            {
                "owner": "security",
                "severity": "medium" if status == "ready" else "high",
                "risk": "SBOM must be attached.",
                "route": "/productization",
                "next_action": "Attach SBOM before rollout.",
            }
        ],
    }


def test_board_pack_builds_board_level_buying_motion():
    report = build_board_pack(
        executive=_decision(),
        buyer_concierge=_buyer_concierge(),
        commercial_offer_studio=_commercial_offer(),
        enterprise_trust_center=_trust_center(),
        business_case=_business_case(),
        scenario_hub=_decision(score=83),
        pilot_launchpad=_decision(score=84),
        demo_command_center=_decision(score=85),
        productization={"status": "pass", "score": 90},
        evidence_artifacts=[{"id": "business-case"}, {"id": "commercial-offer-studio"}],
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["decision"]["status"] == "ready"
    assert report["summary"]["recommended_offer"] == "enterprise-local-license"
    assert report["summary"]["decision_items"] >= 6
    assert any(
        item["question"] == "What does procurement need?"
        for item in report["decision_brief"]
    )
    assert any(
        item["question"] == "What must pass before signature?"
        for item in report["decision_brief"]
    )
    assert report["summary"]["committee_roles"] >= 3
    assert report["summary"]["first_year_visible_value"] == 4_800_000
    assert report["board_snapshot"]["three_year_ai_rent"] == "4 320 000 RUB"
    assert report["board_snapshot"]["local_license_anchor"] == "1 800 000 RUB"
    assert report["board_snapshot"]["break_even"] == "5 months by visible value"
    assert report["summary"]["close_ready"] is True
    assert report["summary"]["checkout_gates"] == 4
    assert report["summary"]["board_room_roles"] == 5
    assert report["summary"]["board_room_proofs"] == 4
    assert report["summary"]["board_room_steps"] == 4
    assert report["summary"]["board_room_open_first"] == 4
    assert report["board_room_bridge"]["source"] == "management-buyer-brief"
    assert report["board_room_bridge"]["primary_motion"]["route"] == "/board-pack"
    assert report["board_room_bridge"]["files"][:3] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
    ]
    assert [
        item["stage"] for item in report["board_room_bridge"]["open_first_path"]
    ] == ["orient", "prove", "close", "verify"]
    assert any(
        item["id"] == "audit-siem"
        for item in report["board_room_bridge"]["proof_readiness"]
    )
    assert any(
        item["route"] == "/killer-demo"
        for item in report["board_room_bridge"]["meeting_flow"]
    )
    assert [item["filename"] for item in report["proof_packet"][:2]] == [
        "buyer-brief.md",
        "buyer-pulse.md",
    ]
    assert any(item["route"] == "/evidence-bundle" for item in report["proof_packet"])
    assert any(item["route"] == "/approvals" for item in report["proof_packet"])
    assert any(item["route"] == "/audit" for item in report["proof_packet"])
    assert report["board_close_packet"]["ready_to_close"] is True
    assert report["board_close_packet"]["close_mode"] == "open_enterprise_purchase"
    assert (
        report["board_close_packet"]["one_page_order"]["three_year_ai_rent"]
        == "4 320 000 RUB"
    )
    assert (
        report["board_close_packet"]["one_page_order"]["local_license_anchor"]
        == "1 800 000 RUB"
    )
    assert (
        report["board_close_packet"]["one_page_order"]["break_even"]
        == "5 months by visible value"
    )
    assert {item["route"] for item in report["board_close_packet"]["checkout"]} >= {
        "/approvals",
        "/audit",
        "/evidence-bundle",
        "/enterprise-trust-center",
    }
    assert any(
        item["artifact"] == "Archive Acceptance Receipt"
        and item["route"] == "/evidence-bundle"
        for item in report["board_close_packet"]["evidence_requirements"]
    )
    assert "/board-pack" in report["proof_routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "Board Pack" in report["markdown"]
    assert "Board Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]
    assert "Board Close Packet" in report["markdown"]
    assert "archive-acceptance-receipt.md" in report["markdown"]


def test_board_pack_keeps_trust_risk_as_hardening_motion():
    report = build_board_pack(
        executive=_decision(status="watch", score=70),
        buyer_concierge=_buyer_concierge(status="watch", score=72),
        commercial_offer_studio=_commercial_offer(status="watch", score=76),
        enterprise_trust_center=_trust_center(
            status="risk", score=45, failed_controls=3
        ),
        business_case=_business_case(),
        scenario_hub=_decision(status="watch", score=70),
        pilot_launchpad=_decision(status="watch", score=70),
        demo_command_center=_decision(status="watch", score=70),
        productization={"status": "pass", "score": 80},
        client_name="ACME",
    )

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["recommended_offer"] == "platform-trust-pack"
    assert report["summary"]["severe_risks"] >= 1
    assert report["summary"]["close_ready"] is False
    assert any(
        item["route"] == "/enterprise-trust-center" for item in report["next_72_hours"]
    )
