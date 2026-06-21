import json
from copy import deepcopy

from src.services.rentgen.killer_demo_path import build_killer_demo_path


def _decision(status="ready", score=86):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


def _launch_room(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"phases": 6},
        "launch_summary": {
            "current_truth": "One route shows role, proof, trust and close.",
            "value_anchor": "4 800 000 RUB first-year visible value",
        },
        "next_best_action": {
            "label": "Open Board Pack",
            "route": "/board-pack",
            "reason": "Approval route is strong enough.",
        },
    }


def _demo_command_center(status="ready", score=85):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "live_stages": [
            {
                "id": "developer-spark",
                "proof": "Show the changed module and generated proof package.",
            }
        ],
    }


def _test_factory(status="ready", score=84):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "run_now": 2,
            "generation_tasks": 1,
            "gaps": 1,
        },
    }


def _buyer_concierge(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "persona_cards": [
            {
                "role": "Developer",
                "spark": "LEFT JOIN/NULL proof is visible.",
                "start_route": "/quality",
                "proof": "A real 1C defect class is caught.",
                "buy_trigger": "Review becomes faster.",
            },
            {
                "role": "Director",
                "spark": "Local product value beats AI rent.",
                "start_route": "/business-case",
                "proof": "Finance sees value and next motion.",
                "buy_trigger": "Approve local license.",
            },
        ],
    }


def _trust_center(status="ready", score=84):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"controls": 9},
    }


def _offer(status="ready", score=88):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {"offers": 3, "pricing_tiers": 3, "close_ready": True, "checkout_gates": 4},
        "close_packet": {
            "ready_to_close": status == "ready",
            "close_mode": "open_enterprise_purchase",
            "primary_ask": "Open enterprise local-license procurement and use the proof sprint as credited onboarding.",
            "one_page_order": {
                "product": "1C Rentgen local evidence control plane",
                "recommended_purchase": "Enterprise local license",
                "commercial_frame": "fixed enterprise purchase",
                "value_anchor": "4 800 000 RUB first-year visible value",
                "ai_rent_baseline": "1 200 000 RUB annual AI rent",
                "three_year_ai_rent": "3 600 000 RUB",
                "local_license_anchor": "1 800 000 RUB",
                "break_even": "5 months by visible value",
                "first_invoice_trigger": "Buyer names owner, scope, date and accepted proof artifacts.",
                "route": "/commercial-offer-studio",
            },
            "mutual_action_plan": [
                {
                    "window": "Today",
                    "owner": "sponsor + seller",
                    "action": "Choose enterprise local license.",
                    "artifact": "Commercial Offer Studio",
                    "route": "/commercial-offer-studio",
                    "exit": "Purchase motion is accepted.",
                },
                {
                    "window": "24 hours",
                    "owner": "tech lead",
                    "action": "Attach Evidence Bundle ZIP.",
                    "artifact": "Evidence Bundle",
                    "route": "/evidence-bundle",
                    "exit": "Buyer can forward one archive.",
                },
            ],
            "buyer_commitments": [
                {"role": "finance", "commitment": "Accept local value anchor.", "route": "/business-case"},
                {"role": "security", "commitment": "Confirm approval and audit evidence.", "route": "/approvals"},
                {"role": "architect", "commitment": "Name rollout blockers.", "route": "/platform-doctor"},
                {"role": "sponsor", "commitment": "Approve paid next step.", "route": "/commercial-offer-studio"},
            ],
            "evidence_requirements": [
                {"artifact": "Evidence Bundle ZIP", "route": "/evidence-bundle", "why": "Forwardable proof."},
                {"artifact": "Governance proof", "route": "/approvals", "why": "Approval records."},
                {"artifact": "Audit verify", "route": "/audit", "why": "Tamper-evident hash chain."},
                {"artifact": "Business Case", "route": "/business-case", "why": "Value anchor."},
            ],
            "checkout": [
                {"gate": "Approval record exists", "route": "/approvals", "evidence": "Scoped approval record."},
                {"gate": "Audit chain is valid", "route": "/audit", "evidence": "valid=true broken=0."},
                {"gate": "Proof archive is exportable", "route": "/evidence-bundle", "evidence": "ZIP with manifest."},
                {"gate": "Trust caveats are visible", "route": "/enterprise-trust-center", "evidence": "Named caveats."},
            ],
            "close_script": [
                "The price is anchored to local evidence value, not token usage.",
                "If proof archive is accepted, open enterprise purchase.",
            ],
        },
    }


def _board_pack(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "decision_items": 6,
            "recommended_offer": "enterprise-local-license",
            "first_year_visible_value": 4_800_000,
        },
        "board_snapshot": {"value_anchor": "4 800 000 RUB first-year visible value"},
        "recommended_offer": {"id": "enterprise-local-license"},
        "committee_map": [
            {
                "role": "Developer",
                "must_believe": "The defect is real.",
                "close_line": "Start with the first changed module.",
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
    }


def _outcome_ledger(status="ready", score=82):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "success_metrics": 5,
            "expansion_paths": 2,
            "risk_items": 3,
            "recommended_motion": "enterprise-local-license",
        },
        "role_scorecards": [
            {
                "role": "Developer",
                "spark": "Test proof is actionable.",
                "proof_route": "/testing",
                "owner_action": "Fix the first risky module.",
            },
            {
                "role": "Director",
                "spark": "Value is measurable.",
                "proof_route": "/outcome-ledger",
                "owner_action": "Book Day 30 acceptance.",
            },
        ],
    }


def _open_first_path_payload():
    path = [
        {
            "step": 1,
            "stage": "orient",
            "label": "Orient",
            "title": "Buyer Room Map",
            "route": "/",
            "line": "Open the Buyer Brief and room packet before role-specific proof.",
            "file": "buyer-brief.md",
            "status": "ready",
            "source": "buyer_brief",
        },
        {
            "step": 2,
            "stage": "prove",
            "label": "Prove",
            "title": "Killer Demo",
            "route": "/killer-demo",
            "line": "Show the close-room proof packet and role handoffs.",
            "file": "OPEN_FIRST_KILLER_DEMO.md",
            "status": "ready",
            "source": "evidence_bundle",
        },
        {
            "step": 3,
            "stage": "close",
            "label": "Close",
            "title": "Meeting Close Receipt",
            "route": "/killer-demo",
            "line": "Capture accepted roles, blockers and next paid step.",
            "file": "MEETING_CLOSE_RECEIPT.md",
            "status": "ready",
            "source": "purchase_path.close_artifact",
        },
        {
            "step": 4,
            "stage": "verify",
            "label": "Verify",
            "title": "Verification Packet ZIP",
            "route": "/evidence-bundle",
            "line": "Attach the pair-level archive verification packet.",
            "file": "archive-verification-packet.zip",
            "status": "ready",
            "source": "purchase_path.verification_packet_artifact",
        },
    ]
    return {
        "decision": {"status": "ready", "score": 88, "headline": "Open-first path is export-ready."},
        "summary": {
            "steps": 4,
            "stages": [item["stage"] for item in path],
            "routes": [item["route"] for item in path],
            "files": [item["file"] for item in path],
        },
        "open_first_path": path,
    }


def _evidence_bundle():
    return {
        "bundle_id": "evb_test",
        "manifest": {
            "bundle_sha256": "a" * 64,
            "files": [
                {
                    "id": "buyer-brief",
                    "filename": "buyer-brief.md",
                    "media_type": "text/markdown",
                    "sha256": "01" * 32,
                },
                {
                    "id": "buyer-brief",
                    "filename": "buyer-brief.json",
                    "media_type": "application/json",
                    "sha256": "02" * 32,
                },
                {
                    "id": "buyer-room-plan",
                    "filename": "buyer-room-plan.md",
                    "media_type": "text/markdown",
                    "sha256": "04" * 32,
                },
                {
                    "id": "buyer-room-plan",
                    "filename": "buyer-room-plan.json",
                    "media_type": "application/json",
                    "sha256": "05" * 32,
                },
                {
                    "id": "buyer-pulse",
                    "filename": "buyer-pulse.md",
                    "media_type": "text/markdown",
                    "sha256": "06" * 32,
                },
                {
                    "id": "open-first-path",
                    "filename": "open-first-path.md",
                    "media_type": "text/markdown",
                    "sha256": "07" * 32,
                },
                {
                    "id": "open-first-path",
                    "filename": "open-first-path.json",
                    "media_type": "application/json",
                    "sha256": "08" * 32,
                },
                {
                    "id": "killer-demo",
                    "filename": "killer-demo.md",
                    "media_type": "text/markdown",
                    "sha256": "b" * 64,
                },
                {
                    "id": "test-factory",
                    "filename": "test-factory.md",
                    "media_type": "text/markdown",
                    "sha256": "c" * 64,
                },
                {
                    "id": "governance-proof",
                    "filename": "governance-proof.md",
                    "media_type": "text/markdown",
                    "sha256": "f" * 64,
                },
                {
                    "id": "security-questionnaire",
                    "filename": "rentgen-security-questionnaire.md",
                    "media_type": "text/markdown",
                    "sha256": "a1" * 32,
                },
                {
                    "id": "security-questionnaire",
                    "filename": "rentgen-security-questionnaire.json",
                    "media_type": "application/json",
                    "sha256": "a2" * 32,
                },
                {
                    "id": "role-report-developer",
                    "filename": "rentgen-developer-report.md",
                    "media_type": "text/markdown",
                    "sha256": "a3" * 32,
                },
                {
                    "id": "role-report-architect",
                    "filename": "rentgen-architect-report.md",
                    "media_type": "text/markdown",
                    "sha256": "a4" * 32,
                },
                {
                    "id": "role-report-director",
                    "filename": "rentgen-director-report.md",
                    "media_type": "text/markdown",
                    "sha256": "a5" * 32,
                },
                {
                    "id": "role-report-qa",
                    "filename": "rentgen-qa-report.md",
                    "media_type": "text/markdown",
                    "sha256": "a6" * 32,
                },
            ],
        },
        "artifacts": [
            {
                "id": "buyer-brief",
                "title": "Buyer Brief",
                "route": "/",
                "filename": "buyer-brief",
                "status": "ready",
                "score": 88,
                "json_sha256": "02" * 32,
                "markdown_sha256": "01" * 32,
            },
            {
                "id": "open-first-path",
                "title": "Open-First Path",
                "filename": "open-first-path.md",
                "route": "/",
                "status": "ready",
                "score": 88,
                "json_sha256": "08" * 32,
                "markdown_sha256": "07" * 32,
                "json": json.dumps(_open_first_path_payload()),
            },
            {
                "id": "buyer-pulse",
                "title": "Buyer Pulse",
                "route": "/",
                "filename": "buyer-pulse",
                "status": "ready",
                "score": 88,
                "json_sha256": "04" * 32,
                "markdown_sha256": "06" * 32,
            },
            {
                "id": "buyer-room-plan",
                "title": "Buyer Room Plan",
                "route": "/change",
                "filename": "buyer-room-plan",
                "status": "ready",
                "score": 88,
                "json_sha256": "05" * 32,
                "markdown_sha256": "04" * 32,
            },
            {
                "id": "killer-demo",
                "title": "Killer Demo Path",
                "route": "/killer-demo",
                "filename": "killer-demo",
                "status": "ready",
                "score": 90,
                "json_sha256": "d" * 64,
                "markdown_sha256": "b" * 64,
            },
            {
                "id": "test-factory",
                "title": "Test Factory",
                "route": "/testing",
                "filename": "test-factory",
                "status": "ready",
                "score": 84,
                "json_sha256": "e" * 64,
                "markdown_sha256": "c" * 64,
            },
            {
                "id": "governance-proof",
                "title": "Governance Proof",
                "route": "/approvals",
                "filename": "governance-proof",
                "status": "ready",
                "score": 90,
                "json_sha256": "f" * 64,
                "markdown_sha256": "f" * 64,
            },
            {
                "id": "security-questionnaire",
                "title": "Security Questionnaire",
                "route": "/enterprise-trust-center",
                "filename": "rentgen-security-questionnaire",
                "status": "watch",
                "score": 75,
                "json_sha256": "a2" * 32,
                "markdown_sha256": "a1" * 32,
            },
            {
                "id": "role-report-developer",
                "title": "Developer Role Report",
                "route": "/",
                "filename": "rentgen-developer-report",
                "status": "ready",
                "score": 82,
                "json_sha256": "a7" * 32,
                "markdown_sha256": "a3" * 32,
            },
            {
                "id": "role-report-architect",
                "title": "Architect Role Report",
                "route": "/",
                "filename": "rentgen-architect-report",
                "status": "watch",
                "score": 75,
                "json_sha256": "a8" * 32,
                "markdown_sha256": "a4" * 32,
            },
            {
                "id": "role-report-director",
                "title": "Director Role Report",
                "route": "/",
                "filename": "rentgen-director-report",
                "status": "ready",
                "score": 86,
                "json_sha256": "a9" * 32,
                "markdown_sha256": "a5" * 32,
            },
            {
                "id": "role-report-qa",
                "title": "QA Role Report",
                "route": "/",
                "filename": "rentgen-qa-report",
                "status": "watch",
                "score": 73,
                "json_sha256": "aa" * 32,
                "markdown_sha256": "a6" * 32,
            },
        ],
        "procurement_handoff": {
            "status": "ready_to_forward",
            "ready_to_forward": True,
            "buyer_line": "Forward the ZIP archive with OPEN_FIRST.md, manifest.json and procurement-handoff.md.",
            "archive_endpoint": "/api/v1/evidence-bundle/archive",
            "archive_filename": "evb_test-evidence-archive.zip",
            "bundle_sha256": "a" * 64,
            "archive_hash_header": "X-Archive-Sha256",
            "open_first_file": "OPEN_FIRST.md",
            "missing_files": [],
            "blockers": [],
            "review_items": [],
            "recipients": [
                {"role": "Director / sponsor"},
                {"role": "Security / procurement"},
                {"role": "Developer / QA"},
            ],
            "recipient_packets": [
                {
                    "role": "Director / sponsor",
                    "filename": "ROLE_DIRECTOR_SPONSOR.md",
                    "forwarding_subject": "ACME: 1C Rentgen evidence packet for Director / sponsor",
                    "attachments": ["ROLE_DIRECTOR_SPONSOR.md", "buyer-room-plan.md", "commercial-offer-studio.md"],
                    "routes": ["/board-pack", "/commercial-offer-studio"],
                },
                {
                    "role": "Developer / QA",
                    "filename": "ROLE_DEVELOPER_QA.md",
                    "forwarding_subject": "ACME: 1C Rentgen evidence packet for Developer / QA",
                    "attachments": ["ROLE_DEVELOPER_QA.md", "test-factory.md", "safe-autopilot.md"],
                    "routes": ["/testing", "/safe-autopilot"],
                },
            ],
            "verification_steps": [{"id": "manifest"}],
        },
    }


def _build(**overrides):
    data = {
        "launch_room": _launch_room(),
        "demo_command_center": _demo_command_center(),
        "test_factory": _test_factory(),
        "buyer_concierge": _buyer_concierge(),
        "scenario_hub": _decision(score=83),
        "enterprise_trust_center": _trust_center(),
        "commercial_offer_studio": _offer(),
        "board_pack": _board_pack(),
        "outcome_ledger": _outcome_ledger(),
        "client_name": "ACME",
        "config_path": "data/configs/unpacked",
        "target_platform_version": "8.3.26.1000",
        "evidence_bundle": _evidence_bundle(),
    }
    data.update(overrides)
    return build_killer_demo_path(**data)


def test_killer_demo_path_builds_buyer_ready_route():
    report = _build()

    assert report["client"]["name"] == "ACME"
    assert report["decision"]["status"] == "ready"
    assert report["primary_route"]["route"] == "/board-pack"
    assert report["summary"]["stages"] == 6
    assert report["summary"]["demo_modes"] == 4
    assert report["summary"]["role_sparks"] >= 3
    assert report["summary"]["proof_files"] >= 5
    assert "deal_readiness_score" in report["summary"]
    assert report["summary"]["committee_roles"] >= 3
    assert report["summary"]["committee_blocked_roles"] >= 1
    assert report["summary"]["opening_roles"] >= 3
    assert report["summary"]["objection_items"] >= 7
    assert report["summary"]["objection_watch"] >= 1
    assert report["summary"]["close_ready"] is True
    assert report["summary"]["close_receipt_ready"] is True
    assert report["summary"]["activation_handoff_ready"] is True
    assert report["summary"]["open_first_steps"] == 4
    assert report["summary"]["checkout_gates"] == 4
    assert report["opening_brief"]["first_click"]["route"] == report["primary_route"]["route"]
    assert len(report["opening_brief"]["first_30_seconds"]) == 3
    assert len(report["opening_brief"]["role_entries"]) >= 3
    assert report["opening_brief"]["anti_confusion"]
    assert report["opening_brief"]["success_signal"]
    router = report["objection_router"]
    assert router["status"] in {"ready", "watch"}
    assert len(router["items"]) >= 7
    assert any(item["id"] == "ai-subscription" and item["route"] == "/business-case" for item in router["items"])
    assert any(item["id"] == "security" and item["proof_file"] == "rentgen-security-questionnaire.md" for item in router["items"])
    assert any(item["id"] == "proof-forwarding" and item["proof_file"] == "buyer-room-plan.md" for item in router["items"])
    assert "/evidence-bundle" in router["proof_routes"]
    assert report["deal_readiness"]["next_paid_step"]["route"] in {
        "/commercial-offer-studio",
        "/enterprise-trust-center",
        "/testing",
        "/pilot-launchpad",
    }
    assert report["deal_readiness"]["local_asset_case"]["headline"]
    assert "/business-case" in report["deal_readiness"]["local_asset_case"]["proof_routes"]
    assert "/commercial-offer-studio" in report["deal_readiness"]["local_asset_case"]["proof_routes"]
    assert "/approvals" in report["deal_readiness"]["local_asset_case"]["proof_routes"]
    assert "/audit" in report["deal_readiness"]["local_asset_case"]["proof_routes"]
    assert "/evidence-bundle" in report["deal_readiness"]["local_asset_case"]["proof_routes"]
    assert report["deal_readiness"]["role_acceptance"]
    committee = report["deal_readiness"]["committee_close_board"]
    assert committee["status"] == "proof_first"
    assert committee["accepted_roles"] >= 1
    assert committee["blocked_roles"] >= 1
    assert committee["final_question"]
    assert all(item["send"] for item in committee["roles"])
    assert len(report["deal_readiness"]["customer_can_repeat"]) >= 3
    assert len(report["deal_readiness"]["close_checklist"]) >= 4
    assert report["proof_packet"]["bundle_id"] == "evb_test"
    assert report["proof_packet"]["bundle_sha256"] == "a" * 64
    assert report["proof_packet"]["ready_to_forward"] is True
    assert report["proof_packet"]["archive"]["ready"] is True
    assert report["proof_packet"]["archive"]["endpoint"] == "/api/v1/evidence-bundle/archive"
    assert report["proof_packet"]["archive"]["filename"] == "evb_test-evidence-archive.zip"
    assert report["proof_packet"]["killer_archive"]["ready"] is True
    assert report["proof_packet"]["killer_archive"]["endpoint"] == "/api/v1/killer-demo/archive"
    assert report["proof_packet"]["killer_archive"]["filename"] == "evb_test-killer-demo-archive.zip"
    assert report["proof_packet"]["killer_archive"]["manifest"] == "killer-demo-manifest.json"
    assert report["proof_packet"]["killer_archive"]["open_first"] == "OPEN_FIRST_KILLER_DEMO.md"
    assert set(report["proof_packet"]["killer_archive"]["role_packets"]) >= {
        "ROLE_DEVELOPER_QA.md",
        "ROLE_ARCHITECT_SECURITY.md",
        "ROLE_DIRECTOR_SPONSOR.md",
    }
    assert report["proof_packet"]["verification_packet"]["ready"] is True
    assert report["proof_packet"]["verification_packet"]["filename"] == "archive-verification-packet.zip"
    assert report["proof_packet"]["verification_packet"]["endpoint"] == "/api/v1/evidence-bundle/archive/verification-packet"
    assert report["proof_packet"]["verification_packet"]["sha256_header"] == "X-Verification-Packet-Sha256"
    assert report["proof_packet"]["verification_packet"]["open_first"] == "OPEN_FIRST_VERIFICATION_PACKET.md"
    assert "hash-table.json" in report["proof_packet"]["verification_packet"]["contains"]
    assert report["proof_packet"]["close_receipt"]["ready"] is True
    assert report["proof_packet"]["close_receipt"]["filename"] == "MEETING_CLOSE_RECEIPT.md"
    assert report["proof_packet"]["close_receipt"]["json_filename"] == "meeting-close-receipt.json"
    assert report["proof_packet"]["close_receipt"]["next_paid_step"] == report["deal_readiness"]["next_paid_step"]["label"]
    assert report["proof_packet"]["activation_handoff"]["ready"] is True
    assert report["proof_packet"]["activation_handoff"]["filename"] == "POST_DEMO_ACTIVATION_HANDOFF.md"
    assert report["proof_packet"]["activation_handoff"]["json_filename"] == "post-demo-activation-handoff.json"
    assert report["proof_packet"]["activation_handoff"]["next_window"]
    receipt = report["meeting_close_receipt"]
    assert receipt["ready_to_send"] is True
    assert receipt["ready_to_ask"] is True
    assert receipt["next_paid_step"]["label"] == report["deal_readiness"]["next_paid_step"]["label"]
    assert receipt["committee"]["accepted_roles"] == report["deal_readiness"]["committee_close_board"]["accepted_roles"]
    assert "rentgen-buyer-room-packet.zip" in receipt["send_files"]
    assert "MEETING_CLOSE_RECEIPT.md" in receipt["send_files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in receipt["send_files"]
    assert "archive-verification-packet.zip" in receipt["send_files"]
    assert "proof-packet.json" in receipt["send_files"]
    assert receipt["proof_packet"]["buyer_room_packet"] == "rentgen-buyer-room-packet.zip"
    assert receipt["proof_packet"]["buyer_room_packet_hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert receipt["proof_packet"]["verification_packet"] == "archive-verification-packet.zip"
    assert receipt["proof_packet"]["verification_packet_hash_header"] == "X-Verification-Packet-Sha256"
    assert receipt["forwarding_kit"]["ready"] is True
    assert receipt["forwarding_kit"]["packet_count"] == 2
    assert receipt["forwarding_kit"]["packets"][0]["forwarding_subject"].endswith("Director / sponsor")
    activation = report["post_demo_activation_handoff"]
    assert activation["ready_to_start"] is True
    assert activation["next_paid_step"]["label"] == report["deal_readiness"]["next_paid_step"]["label"]
    assert "/pilot-launchpad" in activation["route_chain"]
    assert "/outcome-ledger" in activation["route_chain"]
    assert "rentgen-buyer-room-packet.zip" in activation["proof_files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in activation["proof_files"]
    assert "archive-verification-packet.zip" in activation["proof_files"]
    assert any(item["gate"] == "Verification packet is attached" for item in activation["gates"])
    assert activation["forwarding_kit"]["packet_count"] == 2
    assert "ROLE_DIRECTOR_SPONSOR.md" in activation["proof_files"]
    assert any(item["window"] == "Day 0" for item in activation["timeline"])
    rollup = report["proof_packet"]["role_packet_rollup"]
    assert rollup["status"] == "partial"
    assert rollup["total"] == 3
    assert rollup["ready"] == 0
    assert rollup["partial"] == 3
    assert rollup["missing"] == 0
    assert rollup["missing_files"] > 0
    assert report["summary"]["role_packets_partial"] == 3
    assert report["summary"]["role_packet_missing_files"] == rollup["missing_files"]
    assert report["proof_packet"]["procurement_handoff"]["ready"] is True
    assert report["proof_packet"]["procurement_handoff"]["status"] == "ready_to_forward"
    assert report["proof_packet"]["procurement_handoff"]["missing_files"] == 0
    assert report["proof_packet"]["procurement_handoff"]["blockers"] == 0
    assert report["proof_packet"]["procurement_handoff"]["recipients"] >= 3
    assert report["proof_packet"]["procurement_handoff"]["verification_steps"] == 1
    assert report["proof_packet"]["procurement_handoff"]["first_file"] == "procurement-handoff.md"
    assert report["proof_packet"]["procurement_handoff"]["buyer_room_packet_filename"] == "rentgen-buyer-room-packet.zip"
    assert report["proof_packet"]["procurement_handoff"]["buyer_room_packet_hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert report["proof_packet"]["procurement_handoff"]["verification_packet_filename"] == "archive-verification-packet.zip"
    assert report["proof_packet"]["procurement_handoff"]["verification_packet_hash_header"] == "X-Verification-Packet-Sha256"
    assert report["proof_packet"]["procurement_handoff"]["acceptance"]
    assert report["proof_packet"]["procurement_handoff"]["open_order"][0]["hash_header"] == (
        "X-Buyer-Room-Packet-Sha256"
    )
    assert report["proof_packet"]["procurement_handoff"]["open_order"][0]["endpoint"] == (
        "/api/v1/management/buyer-room-packet"
    )
    assert report["proof_packet"]["procurement_handoff"]["open_order"][1]["hash_header"] == "X-Archive-Sha256"
    assert report["proof_packet"]["procurement_handoff"]["open_order"][2]["hash_header"] == (
        "X-Killer-Demo-Archive-Sha256"
    )
    assert any(
        item["file"] == "rentgen-buyer-room-packet.zip"
        for item in report["proof_packet"]["procurement_handoff"]["attachments"]
    )
    assert any(
        item["file"] == "archive-verification-packet.zip"
        for item in report["proof_packet"]["procurement_handoff"]["attachments"]
    )
    assert report["proof_packet"]["forwarding_kit"]["ready"] is True
    assert report["proof_packet"]["forwarding_kit"]["packet_count"] == 2
    assert report["proof_packet"]["forwarding_kit"]["first_packet"] == "ROLE_DIRECTOR_SPONSOR.md"
    assert report["proof_packet"]["room_map"]["ready"] is True
    assert report["proof_packet"]["room_map"]["filename"] == "buyer-brief.md"
    assert report["proof_packet"]["room_map"]["packet_filename"] == "rentgen-buyer-room-packet.zip"
    assert report["proof_packet"]["room_map"]["packet_hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert report["proof_packet"]["room_map"]["plan_ready"] is True
    assert report["proof_packet"]["room_map"]["plan_filename"] == "buyer-room-plan.md"
    assert report["proof_packet"]["room_map"]["plan_route"] == "/change"
    assert report["proof_packet"]["room_map"]["open_first_path_ready"] is True
    assert report["proof_packet"]["room_map"]["open_first_path_filename"] == "open-first-path.md"
    assert report["proof_packet"]["room_map"]["pulse_filename"] == "buyer-pulse.md"
    assert [item["stage"] for item in report["proof_packet"]["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert [item["file"] for item in report["proof_packet"]["open_first_path"]] == [
        "buyer-brief.md",
        "OPEN_FIRST_KILLER_DEMO.md",
        "MEETING_CLOSE_RECEIPT.md",
        "archive-verification-packet.zip",
    ]
    assert "Open-First Path" in report["markdown"]
    assert "archive-verification-packet.zip" in report["markdown"]
    assert [item["filename"] for item in report["proof_packet"]["files"][:4]] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
        "buyer-room-plan.md",
    ]
    assert any(item["filename"] == "rentgen-security-questionnaire.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "buyer-brief.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "open-first-path.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "buyer-room-plan.md" for item in report["proof_packet"]["files"])
    assert any(item["id"] == "buyer-brief" for item in report["proof_packet"]["artifacts"])
    assert any(item["id"] == "open-first-path" for item in report["proof_packet"]["artifacts"])
    assert any(item["id"] == "buyer-room-plan" for item in report["proof_packet"]["artifacts"])
    assert any(item["filename"] == "test-factory.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "rentgen-security-questionnaire.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "rentgen-developer-report.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "rentgen-architect-report.md" for item in report["proof_packet"]["files"])
    assert any(item["filename"] == "rentgen-director-report.md" for item in report["proof_packet"]["files"])
    assert any(item["id"] == "security-questionnaire" for item in report["proof_packet"]["artifacts"])
    assert any(item["id"] == "role-report-developer" for item in report["proof_packet"]["artifacts"])
    assert any(item["id"] == "governance-proof" for item in report["proof_packet"]["files"])
    assert any(item["id"] == "governance-proof" for item in report["proof_packet"]["artifacts"])
    assert {item["recipient"] for item in report["proof_packet"]["handoff"]} >= {
        "developer / QA",
        "architect / security",
        "director / sponsor",
    }
    developer_handoff = next(item for item in report["proof_packet"]["handoff"] if item["recipient"] == "developer / QA")
    assert developer_handoff["role_packet"] == "ROLE_DEVELOPER_QA.md"
    assert developer_handoff["availability_status"] == "partial"
    assert developer_handoff["send"][0] == "open-first-path.md"
    assert developer_handoff["send"][1] == "buyer-brief.md"
    assert developer_handoff["send"][2] == "buyer-room-plan.md"
    assert "open-first-path.md" in developer_handoff["available_files"]
    assert "buyer-brief.md" in developer_handoff["available_files"]
    assert "buyer-room-plan.md" in developer_handoff["available_files"]
    assert "rentgen-developer-report.md" in developer_handoff["send"]
    assert "rentgen-developer-report.md" in developer_handoff["available_files"]
    assert "archive-verification-packet.zip" in developer_handoff["available_files"]
    assert "rentgen-qa-report.md" in developer_handoff["send"]
    assert "safe-autopilot.md" in developer_handoff["missing_files"]
    architect_handoff = next(item for item in report["proof_packet"]["handoff"] if item["recipient"] == "architect / security")
    assert architect_handoff["role_packet"] == "ROLE_ARCHITECT_SECURITY.md"
    assert architect_handoff["availability_status"] == "partial"
    assert architect_handoff["send"][0] == "open-first-path.md"
    assert architect_handoff["send"][1] == "buyer-brief.md"
    assert architect_handoff["send"][2] == "buyer-room-plan.md"
    assert "rentgen-security-questionnaire.md" in architect_handoff["send"]
    assert "rentgen-security-questionnaire.md" in architect_handoff["available_files"]
    assert "rentgen-architect-report.md" in architect_handoff["send"]
    assert "archive-verification-packet.zip" in architect_handoff["available_files"]
    assert "rights-rls.md" in architect_handoff["missing_files"]
    director_handoff = next(item for item in report["proof_packet"]["handoff"] if item["recipient"] == "director / sponsor")
    assert director_handoff["role_packet"] == "ROLE_DIRECTOR_SPONSOR.md"
    assert director_handoff["availability_status"] == "partial"
    assert director_handoff["send"][0] == "open-first-path.md"
    assert director_handoff["send"][1] == "buyer-brief.md"
    assert director_handoff["send"][2] == "buyer-room-plan.md"
    assert "rentgen-director-report.md" in director_handoff["send"]
    assert "rentgen-director-report.md" in director_handoff["available_files"]
    assert "archive-verification-packet.zip" in director_handoff["available_files"]
    assert report["commercial_close_packet"]["ready_to_close"] is True
    assert report["commercial_close_packet"]["ready_to_ask"] is True
    assert report["commercial_close_packet"]["close_mode"] == "open_enterprise_purchase"
    assert report["commercial_close_packet"]["one_page_order"]["recommended_purchase"] == "Enterprise local license"
    assert report["commercial_close_packet"]["one_page_order"]["three_year_ai_rent"] == "3 600 000 RUB"
    assert report["deal_readiness"]["local_asset_case"]["local_license_anchor"] == "1 800 000 RUB"
    assert report["deal_readiness"]["local_asset_case"]["break_even"] == "5 months by visible value"
    assert {item["route"] for item in report["commercial_close_packet"]["checkout"]} >= {
        "/approvals",
        "/audit",
        "/evidence-bundle",
        "/enterprise-trust-center",
    }
    assert {item["route"] for item in report["commercial_close_packet"]["evidence_requirements"]} >= {
        "/killer-demo",
        "/approvals",
        "/audit",
        "/evidence-bundle",
    }
    assert report["commercial_close_packet"]["evidence_requirements"][0]["artifact"] == "Buyer Room Packet ZIP"
    assert report["commercial_close_packet"]["evidence_requirements"][1]["artifact"] == "Killer Demo ZIP"
    assert report["commercial_close_packet"]["evidence_requirements"][2]["artifact"] == "Meeting Close Receipt"
    assert report["commercial_close_packet"]["evidence_requirements"][3]["artifact"] == "Post-Demo Activation Handoff"
    assert report["commercial_close_packet"]["evidence_requirements"][4]["artifact"] == "Verification Packet ZIP"
    assert report["proof_packet"]["killer_archive"]["sha256_header"] == "X-Killer-Demo-Archive-Sha256"
    assert report["meeting_close_receipt"]["proof_packet"]["archive_hash_header"] == "X-Killer-Demo-Archive-Sha256"
    assert report["meeting_close_receipt"]["proof_packet"]["buyer_room_packet_hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert report["meeting_close_receipt"]["proof_packet"]["verification_packet_hash_header"] == "X-Verification-Packet-Sha256"
    assert {item["id"] for item in report["killer_stages"]} >= {
        "single-door",
        "developer-proof",
        "trust-proof",
        "board-proof",
        "outcome-proof",
        "evidence-close",
    }
    assert {item["id"] for item in report["demo_modes"]} >= {
        "three-minute",
        "five-minute",
        "eight-minute-board",
        "security-first",
    }
    assert "/killer-demo" in report["proof_routes"]
    assert "/testing" in report["proof_routes"]
    assert "/safe-autopilot" in report["proof_routes"]
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "Killer Demo Path" in report["markdown"]
    assert "ZIP archive" in report["markdown"]
    assert "Verification Packet ZIP" in report["markdown"]
    assert "rentgen-buyer-room-packet.zip" in report["markdown"]
    assert "X-Buyer-Room-Packet-Sha256" in report["markdown"]
    assert "Killer Demo ZIP" in report["markdown"]
    assert "Procurement acceptance" in report["markdown"]
    assert "X-Killer-Demo-Archive-Sha256" in report["markdown"]
    assert "ROLE_ARCHITECT_SECURITY.md" in report["markdown"]
    assert "Buyer room map" in report["markdown"]
    assert "Opening Brief" in report["markdown"]
    assert "Commercial Close Packet" in report["markdown"]
    assert "Meeting Close Receipt" in report["markdown"]
    assert "Post-Demo Activation Handoff" in report["markdown"]
    assert "Customer Can Repeat" in report["markdown"]
    assert "Role Acceptance" in report["markdown"]
    assert "Committee Close Board" in report["markdown"]
    assert "Objection Router" in report["markdown"]


def test_killer_demo_path_leads_with_trust_when_trust_is_risky():
    report = _build(
        enterprise_trust_center=_trust_center(status="risk", score=42),
        board_pack=_board_pack(status="watch", score=72),
        outcome_ledger=_outcome_ledger(status="watch", score=70),
    )

    assert report["decision"]["status"] == "risk"
    assert report["primary_route"]["route"] == "/enterprise-trust-center"
    assert report["deal_readiness"]["status"] == "risk"
    assert report["deal_readiness"]["next_paid_step"]["route"] == "/enterprise-trust-center"
    assert report["deal_readiness"]["committee_close_board"]["status"] == "scope_first"
    assert report["deal_readiness"]["committee_close_board"]["blocked_roles"] >= 1
    assert report["opening_brief"]["first_click"]["route"] == "/enterprise-trust-center"
    assert report["objection_router"]["status"] == "blocked"
    assert report["objection_router"]["primary_objection"]["id"] == "security"
    assert any(item["id"] == "trust" for item in report["deal_readiness"]["blockers"])
    assert report["summary"]["trust_status"] == "risk"
    assert any(item["route"] == "/enterprise-trust-center" for item in report["proof_moments"])


def test_killer_demo_path_adds_self_export_when_bundle_excludes_current_demo():
    bundle = _evidence_bundle()
    bundle["manifest"]["files"] = [
        item for item in bundle["manifest"]["files"] if item["id"] != "killer-demo"
    ]
    bundle["artifacts"] = [
        item for item in bundle["artifacts"] if item["id"] != "killer-demo"
    ]
    bundle["procurement_handoff"].update(
        {
            "status": "blocked",
            "ready_to_forward": False,
            "missing_files": [
                {
                    "id": "killer-demo",
                    "title": "Killer Demo Path",
                    "filename": "killer-demo.md",
                    "route": "/killer-demo",
                }
            ],
            "blockers": ["Missing required file: killer-demo.md (Killer Demo Path)"],
        }
    )

    report = _build(evidence_bundle=bundle)

    assert [item["filename"] for item in report["proof_packet"]["files"][:4]] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
        "buyer-room-plan.md",
    ]
    assert report["proof_packet"]["ready_to_forward"] is True
    assert report["proof_packet"]["procurement_handoff"]["status"] == "ready_with_current_demo"
    assert report["proof_packet"]["procurement_handoff"]["missing_files"] == 0
    assert report["proof_packet"]["procurement_handoff"]["raw_missing_files"] == 1
    assert report["proof_packet"]["procurement_handoff"]["covered_by_current_demo"] == ["killer-demo.md"]
    developer_handoff = next(item for item in report["proof_packet"]["handoff"] if item["recipient"] == "developer / QA")
    assert "rentgen-killer-demo-path.md" in developer_handoff["available_files"]
    assert "killer-demo.md" not in developer_handoff["missing_files"]


def test_killer_demo_path_blocks_close_when_procurement_handoff_has_blockers():
    bundle = deepcopy(_evidence_bundle())
    bundle["procurement_handoff"].update(
        {
            "status": "blocked",
            "ready_to_forward": False,
            "missing_files": [
                {
                    "id": "board-pack",
                    "title": "Board Pack",
                    "filename": "board-pack.md",
                    "route": "/board-pack",
                }
            ],
            "blockers": ["Missing required file: board-pack.md (Board Pack)"],
            "review_items": [{"id": "enterprise-trust-center", "status": "risk"}],
        }
    )

    report = _build(evidence_bundle=bundle)

    assert report["proof_packet"]["ready_to_forward"] is False
    assert report["proof_packet"]["procurement_handoff"]["ready"] is False
    assert report["proof_packet"]["procurement_handoff"]["missing_files"] == 1
    assert report["proof_packet"]["procurement_handoff"]["raw_missing_files"] == 1
    assert report["proof_packet"]["procurement_handoff"]["blockers"] == 1
    assert report["proof_packet"]["procurement_handoff"]["risk_review_items"] == 1
    assert report["commercial_close_packet"]["forward_ready"] is False
    assert report["commercial_close_packet"]["ready_to_ask"] is False
    assert any(item["id"] == "packet" for item in report["deal_readiness"]["blockers"])
    packet_blocker = next(item for item in report["deal_readiness"]["blockers"] if item["id"] == "packet")
    assert "1 missing files" in packet_blocker["action"]
    assert report["objection_router"]["primary_objection"]["id"] in {
        "developer-proof",
        "proof-forwarding",
    }


def test_killer_demo_proof_packet_surfaces_enterprise_artifacts():
    bundle = deepcopy(_evidence_bundle())
    for artifact_id, filename, title, route in [
        ("productization", "productization-readiness", "Productization Readiness", "/productization"),
        ("rights-rls", "rights-rls", "Rights & RLS", "/rights-rls"),
        ("update-war-room", "update-war-room", "Update War Room", "/update-war-room"),
        ("lock-radar", "lock-radar", "Lock Radar", "/lock-radar"),
        ("extension-safety", "extension-safety", "Extension Safety", "/extension-safety"),
    ]:
        bundle["manifest"]["files"].append(
            {
                "id": artifact_id,
                "filename": f"{filename}.md",
                "media_type": "text/markdown",
                "sha256": "ab" * 32,
            }
        )
        bundle["artifacts"].append(
            {
                "id": artifact_id,
                "title": title,
                "route": route,
                "filename": filename,
                "status": "watch",
                "score": 74,
                "json_sha256": "cd" * 32,
                "markdown_sha256": "ab" * 32,
            }
        )

    report = _build(evidence_bundle=bundle)
    filenames = [item["filename"] for item in report["proof_packet"]["files"]]
    artifact_ids = {item["id"] for item in report["proof_packet"]["artifacts"]}

    assert "productization-readiness.md" in filenames
    assert "rights-rls.md" in filenames
    assert "update-war-room.md" in filenames
    assert "lock-radar.md" in filenames
    assert "extension-safety.md" in filenames
    assert artifact_ids >= {
        "productization",
        "rights-rls",
        "update-war-room",
        "lock-radar",
        "extension-safety",
    }
