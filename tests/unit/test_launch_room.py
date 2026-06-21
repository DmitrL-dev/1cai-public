from src.services.rentgen.launch_room import build_launch_room


def _decision(status="ready", score=86):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


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
            "headline": "Buy the local asset.",
            "monthly_ai_rent": 120_000,
            "annual_ai_rent": 1_440_000,
            "three_year_ai_rent": 4_320_000,
            "local_license_anchor": 1_800_000,
            "break_even_months": 5,
            "ai_rent_equivalent_months": 15,
            "currency": "RUB",
            "decision_line": "Three-year AI rent can fund the local evidence asset.",
            "guardrails": ["External AI remains optional."],
            "evidence_files": [
                {"title": "Business Case", "filename": "business-case.md", "route": "/business-case"},
                {"title": "Evidence Bundle", "filename": "OPEN_FIRST.md", "route": "/evidence-bundle"},
            ],
        },
    }


def _buyer_concierge(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"persona_cards": 3},
        "default_next_action": {
            "label": "Open Buyer Concierge",
            "route": "/buyer-concierge",
            "reason": "Start from role.",
        },
        "persona_cards": [
            {
                "role": "Developer",
                "spark": "LEFT JOIN/NULL proof",
                "start_route": "/quality",
                "second_route": "/scenario-hub",
                "proof": "A real defect is caught.",
                "buy_trigger": "Review is saved.",
            },
            {
                "role": "Director",
                "spark": "Local value beats AI rent.",
                "start_route": "/business-case",
                "second_route": "/board-pack",
                "proof": "Value is visible.",
                "buy_trigger": "Board motion is clear.",
            },
        ],
        "confusion_guardrails": [
            {
                "signal": "Too many reports.",
                "response": "Use the next action.",
                "route": "/launch-room",
            }
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
            "reason": "Buyer pulse is ready.",
        },
        "room_line": "Ask for local license: move from demo proof to a local product purchase.",
        "commercial": {"three_year_ai_rent": "4 320 000 RUB"},
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
            {"step": 3, "label": "Ask", "route": "/board-pack", "line": "Ask for local license."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
        "open_first_path": [
            {"step": 1, "stage": "orient", "label": "Orient", "title": "Buyer room", "route": "/buyer-concierge", "line": "Pick role.", "file": "buyer-brief.md", "status": status, "source": "test"},
            {"step": 2, "stage": "prove", "label": "Prove", "title": "Killer Demo", "route": "/killer-demo", "line": "Show proof.", "file": "OPEN_FIRST_KILLER_DEMO.md", "status": status, "source": "test"},
            {"step": 3, "stage": "close", "label": "Close", "title": "Receipt", "route": "/killer-demo", "line": "Close.", "file": "MEETING_CLOSE_RECEIPT.md", "status": status, "source": "test"},
            {"step": 4, "stage": "verify", "label": "Verify", "title": "Verification Packet ZIP", "route": "/evidence-bundle", "line": "Verify.", "file": "archive-verification-packet.zip", "status": "ready", "source": "test"},
        ],
    }


def _commercial_offer(status="ready", score=88):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"offers": 3, "close_ready": status == "ready", "checkout_gates": 4},
        "close_packet": {
            "ready_to_close": status == "ready",
            "primary_ask": "Open enterprise local-license procurement.",
            "one_page_order": {
                "recommended_purchase": "Enterprise local license",
                "commercial_frame": "fixed enterprise purchase",
                "value_anchor": "4 800 000 RUB first-year visible value",
                "three_year_ai_rent": "4 320 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even": "5 months by visible value",
                "first_invoice_trigger": "Buyer names owner, scope, date and accepted proof artifacts.",
                "route": "/commercial-offer-studio",
            },
            "checkout": [
                {"route": "/approvals"},
                {"route": "/audit"},
                {"route": "/evidence-bundle"},
                {"route": "/enterprise-trust-center"},
            ],
        },
        "procurement_dossier": {
            "subscription_escape": {
                "annual_ai_rent": "1 440 000 RUB",
                "three_year_ai_rent": "4 320 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even_months": 5,
            }
        },
    }


def _trust_center(status="ready", score=84, controls=9):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"controls": controls},
    }


def _board_pack(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "decision_items": 4,
            "recommended_offer": "enterprise-local-license",
            "first_year_visible_value": 4_800_000,
        },
        "board_snapshot": {
            "value_anchor": "4 800 000 RUB first-year visible value",
            "three_year_ai_rent": "4 320 000 RUB",
            "local_license_anchor": "1 800 000 RUB",
            "break_even": "5 months by visible value",
        },
        "committee_map": [
            {
                "role": "Developer",
                "must_believe": "The defect is real.",
                "close_line": "Start with a proof fix.",
            },
            {
                "role": "Director",
                "must_believe": "The buying motion is clear.",
                "close_line": "Approve the local license motion.",
            },
        ],
        "board_room_script": [
            {"speaker": "context", "route": "/buyer-concierge"},
            {"speaker": "proof", "route": "/scenario-hub"},
            {"speaker": "trust", "route": "/enterprise-trust-center"},
            {"speaker": "money", "route": "/board-pack"},
            {"speaker": "close", "route": "/commercial-offer-studio"},
        ],
        "board_close_packet": {
            "ready_to_close": status == "ready",
            "primary_ask": "Approve the paid motion.",
            "one_page_order": {"recommended_purchase": "Enterprise local license"},
            "checkout": [
                {"route": "/approvals"},
                {"route": "/audit"},
                {"route": "/evidence-bundle"},
                {"route": "/enterprise-trust-center"},
            ],
            "proof_routes": ["/approvals", "/audit", "/evidence-bundle"],
        },
    }


def _outcome_ledger(status="ready", score=82):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "success_metrics": 5,
            "recommended_motion": "enterprise-local-license",
            "first_year_visible_value": 4_800_000,
            "currency": "RUB",
            "acceptance_rollup_items": 7,
            "acceptance_rollup_ready": status == "ready",
            "acceptance_rollup_watch": 0 if status == "ready" else 2,
            "acceptance_rollup_blocked": 0,
        },
        "role_scorecards": [
            {
                "role": "Developer",
                "spark": "Null guards are visible.",
                "proof_route": "/quality",
                "owner_action": "Fix first query.",
            },
            {
                "role": "Director",
                "spark": "Value is measurable.",
                "proof_route": "/outcome-ledger",
                "owner_action": "Book Day 30 review.",
            },
        ],
        "adoption_timeline": [
            {"window": "Day 0", "route": "/board-pack"},
            {"window": "Day 7", "route": "/outcome-ledger"},
            {"window": "Day 30", "route": "/outcome-ledger"},
        ],
        "governance_refresh": {
            "ready": status == "ready",
            "refresh_line": "Governance proof is ready.",
            "gates": [
                {"route": "/approvals"},
                {"route": "/audit"},
                {"route": "/evidence-bundle"},
                {"route": "/enterprise-trust-center"},
            ],
            "windows": [{"route": "/approvals"}, {"route": "/audit"}, {"route": "/evidence-bundle"}],
            "proof_routes": ["/approvals", "/audit", "/evidence-bundle"],
        },
        "acceptance_rollup": {
            "ready_to_claim": status == "ready",
            "ready_to_continue": True,
            "items": [
                {
                    "id": "day30-conversion",
                    "status": "ready" if status == "ready" else "watch",
                    "evidence_route": "/pilot-launchpad",
                    "outcome_route": "/outcome-ledger",
                }
            ],
            "ready_items": 7 if status == "ready" else 5,
            "watch_items": 0 if status == "ready" else 2,
            "blocked_items": 0,
            "proof_routes": ["/pilot-launchpad", "/outcome-ledger", "/evidence-bundle"],
        },
    }


def _pilot_launchpad(status="ready", score=84):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "activation_contract": {
            "ready_to_activate": status == "ready",
            "selected_offer_title": "30-day local license pilot",
            "primary_ask": "Start the paid local license pilot.",
            "gates": [
                {"route": "/pilot-launchpad"},
                {"route": "/approvals"},
                {"route": "/audit"},
                {"route": "/evidence-bundle"},
                {"route": "/enterprise-trust-center"},
            ],
            "proof_routes": ["/pilot-launchpad", "/approvals", "/audit", "/evidence-bundle"],
        },
    }


def _build(**overrides):
    data = {
        "executive": _decision(),
        "buyer_concierge": _buyer_concierge(),
        "scenario_hub": {**_decision(score=83), "summary": {"scenarios": 4}},
        "demo_command_center": _decision(score=85),
        "enterprise_trust_center": _trust_center(),
        "commercial_offer_studio": _commercial_offer(),
        "board_pack": _board_pack(),
        "outcome_ledger": _outcome_ledger(),
        "pilot_launchpad": _pilot_launchpad(),
        "business_case": _business_case(),
        "buyer_brief": _buyer_brief(),
        "evidence_bundle_artifacts": [{"id": "board-pack"}, {"id": "outcome-ledger"}],
        "client_name": "ACME",
        "config_path": "data/configs/unpacked",
        "target_platform_version": "8.3.26.1000",
    }
    data.update(overrides)
    return build_launch_room(**data)


def test_launch_room_builds_single_buyer_cockpit():
    report = _build()

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["phases"] == 6
    assert report["summary"]["journey_steps"] == 4
    assert report["summary"]["journey_ready"] >= 3
    assert report["summary"]["checkout_gates"] == 4
    assert report["summary"]["activation_gates"] == 5
    assert report["summary"]["governance_gates"] == 4
    assert report["summary"]["acceptance_items"] == 7
    assert report["summary"]["claim_ready"] is True
    assert report["summary"]["purchase_spine_status"] == "ready"
    assert report["summary"]["procurement_handoff_steps"] == 6
    assert report["summary"]["buyer_room_roles"] == 5
    assert report["summary"]["buyer_room_proofs"] == 4
    assert report["summary"]["buyer_room_steps"] == 4
    assert report["summary"]["buyer_room_open_first"] == 4
    assert [item["id"] for item in report["path_phases"]] == [
        "orient",
        "prove",
        "trust",
        "approve",
        "adopt",
        "export",
    ]
    assert report["next_best_action"]["route"] == "/board-pack"
    assert report["purchase_spine"]["status"] == "ready"
    assert report["purchase_spine"]["three_year_ai_rent"] == "4 320 000 RUB"
    assert report["purchase_spine"]["local_license_anchor"] == "1 800 000 RUB"
    assert report["purchase_spine"]["break_even"] == "5 months by visible value"
    assert report["purchase_spine"]["route"] == "/commercial-offer-studio"
    handoff = report["purchase_spine"]["procurement_handoff"]
    assert handoff["title"] == "Procurement-ready handoff"
    assert handoff["open_order"][0]["hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert handoff["open_order"][0]["endpoint"] == "/api/v1/management/buyer-room-packet"
    assert handoff["open_order"][1]["hash_header"] == "X-Archive-Sha256"
    assert handoff["open_order"][2]["hash_header"] == "X-Killer-Demo-Archive-Sha256"
    assert any(item["file"] == "rentgen-buyer-room-packet.zip" for item in handoff["attachments"])
    assert any(item["file"] == "archive-verification-packet.zip" for item in handoff["attachments"])
    assert "/" in report["purchase_spine"]["proof_routes"]
    assert "/killer-demo" in report["purchase_spine"]["proof_routes"]
    assert "/business-case" in report["purchase_spine"]["proof_routes"]
    assert "/commercial-offer-studio" in report["purchase_spine"]["proof_routes"]
    assert "/pilot-launchpad" in report["purchase_spine"]["proof_routes"]
    assert "/outcome-ledger" in report["purchase_spine"]["proof_routes"]
    assert [item["filename"] for item in report["purchase_spine"]["evidence_files"][:4]] == [
        "rentgen-buyer-room-packet.zip",
        "OPEN_FIRST_KILLER_DEMO.md",
        "MEETING_CLOSE_RECEIPT.md",
        "POST_DEMO_ACTIVATION_HANDOFF.md",
    ]
    assert "rentgen-buyer-room-packet.zip" in [
        item["filename"] for item in report["purchase_spine"]["evidence_files"]
    ]
    assert "archive-acceptance-receipt.md" in [
        item["filename"] for item in report["purchase_spine"]["evidence_files"]
    ]
    assert "archive-verification-packet.zip" in [
        item["filename"] for item in report["purchase_spine"]["evidence_files"]
    ]
    assert report["buyer_room_bridge"]["source"] == "management-buyer-brief"
    assert report["buyer_room_bridge"]["primary_motion"]["route"] == "/board-pack"
    assert report["buyer_room_bridge"]["files"][:3] == [
        "rentgen-buyer-room-packet.zip",
        "buyer-brief.md",
        "buyer-pulse.md",
    ]
    assert "MEETING_CLOSE_RECEIPT.md" in report["buyer_room_bridge"]["files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in report["buyer_room_bridge"]["files"]
    assert "archive-acceptance-receipt.md" in report["buyer_room_bridge"]["files"]
    assert "archive-verification-packet.zip" in report["buyer_room_bridge"]["files"]
    assert any(item["id"] == "audit-siem" for item in report["buyer_room_bridge"]["proof_readiness"])
    assert any(item["route"] == "/killer-demo" for item in report["buyer_room_bridge"]["meeting_flow"])
    assert [item["stage"] for item in report["buyer_room_bridge"]["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert "open-first-path.md" in report["buyer_room_bridge"]["files"]
    assert "Open-First Path" in report["markdown"]
    assert [item["filename"] for item in report["proof_packet"][:3]] == [
        "rentgen-buyer-room-packet.zip",
        "buyer-brief.md",
        "buyer-pulse.md",
    ]
    assert [item["filename"] for item in report["proof_packet"][3:6]] == [
        "OPEN_FIRST_KILLER_DEMO.md",
        "MEETING_CLOSE_RECEIPT.md",
        "POST_DEMO_ACTIVATION_HANDOFF.md",
    ]
    assert "archive-acceptance-receipt.md" in [item["filename"] for item in report["proof_packet"]]
    assert "archive-acceptance-receipt.json" in [item["filename"] for item in report["proof_packet"]]
    assert "archive-verification-packet.zip" in [item["filename"] for item in report["proof_packet"]]
    assert [item["id"] for item in report["buyer_journey"]["steps"]] == ["close", "activate", "govern", "realize"]
    assert report["buyer_journey"]["buyer_line"]
    assert report["buyer_journey"]["acceptance_items"] == 7
    assert report["buyer_journey"]["claim_ready"] is True
    assert any(item["title"] == "Evidence Bundle" for item in report["route_health"])
    assert "/launch-room" in report["proof_routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "Launch Room" in report["markdown"]
    assert "Purchase Spine" in report["markdown"]
    assert "Purchase Artifacts" in report["markdown"]
    assert "Procurement Handoff" in report["markdown"]
    assert "rentgen-buyer-room-packet.zip" in report["markdown"]
    assert "X-Buyer-Room-Packet-Sha256" in report["markdown"]
    assert "X-Killer-Demo-Archive-Sha256" in report["markdown"]
    assert "X-Verification-Packet-Sha256" in report["markdown"]
    assert "MEETING_CLOSE_RECEIPT.md" in report["markdown"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in report["markdown"]
    assert "archive-acceptance-receipt.md" in report["markdown"]
    assert "archive-verification-packet.zip" in report["markdown"]
    assert "Buyer Room Bridge" in report["markdown"]
    assert "4 320 000 RUB" in report["markdown"]
    assert "Buyer Journey" in report["markdown"]
    assert "Claim ready" in report["markdown"]


def test_launch_room_keeps_trust_risk_as_next_action():
    report = _build(
        enterprise_trust_center=_trust_center(status="risk", score=42),
        board_pack=_board_pack(status="watch", score=72),
        outcome_ledger=_outcome_ledger(status="watch", score=70),
    )

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["risk_phases"] >= 1
    assert report["next_best_action"]["route"] == "/enterprise-trust-center"
