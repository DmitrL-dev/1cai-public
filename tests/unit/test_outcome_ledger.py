from src.services.rentgen.outcome_ledger import build_outcome_ledger


def _decision(status="ready", score=86):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


def _business_case():
    return {
        "decision": {"status": "ready", "score": 88},
        "assumptions": {"currency": "RUB"},
        "summary": {
            "first_year_visible_value": 4_800_000,
            "ai_subscription_year": 1_440_000,
            "manual_review_year": 2_400_000,
            "release_delay_exposure": 720_000,
            "risk_exposure": 900_000,
            "platform_exposure": 500_000,
        },
    }


def _buyer_concierge(status="ready", score=86):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "persona_cards": [
            {
                "role": "Developer",
                "spark": "LEFT JOIN/NULL proof",
                "start_route": "/quality",
                "buy_trigger": "A real review is saved.",
            },
            {
                "role": "Director",
                "spark": "Local value beats AI rent.",
                "start_route": "/business-case",
                "buy_trigger": "Local product value is visible.",
            },
            {
                "role": "Security / CIO",
                "spark": "Local contour proof.",
                "start_route": "/enterprise-trust-center",
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
            "route": "/outcome-ledger",
            "status": status,
            "ask": "Move from proof to measured rollout outcomes.",
            "reason": "Outcome, board and evidence routes can support the claim.",
        },
        "room_line": "Ask for local license: move from proof to measured rollout outcomes.",
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
            {"step": 3, "label": "Measure", "route": "/outcome-ledger", "line": "Claim measured outcome."},
            {"step": 4, "label": "Forward", "route": "/evidence-bundle", "line": "Forward packet."},
        ],
        "open_first_path": [
            {"step": 1, "stage": "orient", "label": "Orient", "title": "Buyer room", "route": "/buyer-concierge", "line": "Pick role.", "file": "open-first-path.md", "status": status, "source": "test"},
            {"step": 2, "stage": "prove", "label": "Prove", "title": "Killer Demo", "route": "/killer-demo", "line": "Show proof.", "file": "OPEN_FIRST_KILLER_DEMO.md", "status": status, "source": "test"},
            {"step": 3, "stage": "close", "label": "Claim", "title": "Outcome Ledger", "route": "/outcome-ledger", "line": "Claim measured outcome.", "file": "rentgen-outcome-ledger.md", "status": status, "source": "test"},
            {"step": 4, "stage": "verify", "label": "Verify", "title": "Verification Packet ZIP", "route": "/evidence-bundle", "line": "Verify.", "file": "archive-verification-packet.zip", "status": "ready", "source": "test"},
        ],
    }


def _commercial_offer(status="ready", score=88):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "offers": [
            {
                "id": "enterprise-local-license",
                "title": "Enterprise local license",
                "commercial_frame": "annual local license anchor 1 800 000 RUB",
                "route": "/commercial-offer-studio",
                "why_buy": "Visible value anchors rollout.",
                "acceptance": "Finance and security approve.",
            },
            {
                "id": "platform-trust-pack",
                "title": "Platform and trust hardening pack",
                "commercial_frame": "scoped hardening package from 450 000 RUB",
                "route": "/enterprise-trust-center",
                "acceptance": "Trust blockers have owners.",
            },
            {
                "id": "vendor-portfolio-rollout",
                "title": "Vendor portfolio rollout",
                "commercial_frame": "partner rollout anchor 2 400 000 RUB",
                "route": "/vendor-portfolio",
            },
        ],
    }


def _trust_center(status="ready", score=84, failed_controls=0):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "failed_controls": failed_controls,
            "warning_controls": 1,
            "controls": 9,
        },
    }


def _board_pack(status="ready", score=86, recommended_offer="enterprise-local-license"):
    return {
        "decision": {"status": status, "score": score, "headline": "ok"},
        "summary": {
            "recommended_offer": recommended_offer,
            "proof_items": 6,
        },
        "recommended_offer": {
            "id": recommended_offer,
            "title": "Enterprise local license" if recommended_offer == "enterprise-local-license" else "Platform and trust hardening pack",
            "commercial_frame": "annual local license anchor 1 800 000 RUB",
            "route": "/commercial-offer-studio",
        },
        "risk_to_decision": [
            {
                "severity": "medium" if status == "ready" else "high",
                "owner": "security",
                "risk": "SBOM must be attached.",
                "route": "/productization",
                "decision": "Attach SBOM before rollout.",
            }
        ],
        "committee_map": [
            {
                "role": "Developer",
                "buy_trigger": "A real defect is caught.",
                "proof_route": "/quality",
                "close_line": "Start with LEFT JOIN/NULL proof.",
            }
        ],
        "board_close_packet": {
            "ready_to_close": status == "ready",
            "proof_routes": ["/approvals", "/audit", "/evidence-bundle", "/commercial-offer-studio"],
        },
    }


def _scenario_hub():
    return {
        "decision": {"status": "ready", "score": 83},
        "scenarios": [
            {"id": "left-join-null", "proof": "LEFT JOIN/NULL proof"},
            {"id": "release-go-no-go", "proof": "Release go/no-go proof"},
            {"id": "platform-upgrade", "proof": "Platform upgrade proof"},
        ],
    }


def _pilot_launchpad(status="ready", score=84):
    return {
        "decision": {"status": status, "score": score},
        "pilot_offers": [
            {
                "why_buy": "Pilot proves local license value.",
                "acceptance": "Owner, acceptance and next step are selected.",
            }
        ],
        "activation_contract": {
            "ready_to_activate": status == "ready",
            "proof_routes": ["/approvals", "/audit", "/evidence-bundle", "/pilot-launchpad"],
        },
    }


def test_outcome_ledger_builds_adoption_and_value_loop():
    report = build_outcome_ledger(
        executive=_decision(),
        board_pack=_board_pack(),
        buyer_concierge=_buyer_concierge(),
        commercial_offer_studio=_commercial_offer(),
        enterprise_trust_center=_trust_center(),
        business_case=_business_case(),
        scenario_hub=_scenario_hub(),
        pilot_launchpad=_pilot_launchpad(),
        demo_command_center=_decision(score=85),
        productization={"status": "pass", "score": 90},
        value_packs={"decision": {"status": "ready", "score": 82}, "packs": [{"title": "Developer proof pack"}]},
        vendor_portfolio={"decision": {"status": "ready", "score": 82}, "work_packages": [{"title": "Platform audit"}]},
        buyer_brief=_buyer_brief(),
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
    )

    assert report["client"]["name"] == "ACME"
    assert report["decision"]["status"] in {"ready", "watch"}
    assert report["summary"]["outcome_tiles"] >= 5
    assert report["summary"]["adoption_steps"] == 6
    assert report["summary"]["success_metrics"] >= 5
    assert report["summary"]["governance_gates"] == 4
    assert report["summary"]["governance_windows"] == 4
    assert report["summary"]["acceptance_rollup_items"] >= 1
    assert report["summary"]["acceptance_rollup_ready"] is True
    assert report["summary"]["acceptance_rollup_blocked"] == 0
    assert report["summary"]["outcome_room_roles"] == 5
    assert report["summary"]["outcome_room_proofs"] == 4
    assert report["summary"]["outcome_room_steps"] == 4
    assert report["summary"]["outcome_room_open_first"] == 4
    assert report["summary"]["first_year_visible_value"] == 4_800_000
    outcome_room = report["outcome_room_bridge"]
    assert outcome_room["source"] == "management-buyer-brief"
    assert outcome_room["primary_motion"]["route"] == "/outcome-ledger"
    assert outcome_room["outcome_motion"]["value_anchor"] == "4 800 000 RUB"
    assert outcome_room["files"][:4] == [
        "rentgen-buyer-room-packet.zip",
        "open-first-path.md",
        "buyer-brief.md",
        "buyer-pulse.md",
    ]
    assert [item["stage"] for item in outcome_room["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "MEETING_CLOSE_RECEIPT.md" in outcome_room["files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in outcome_room["files"]
    assert "archive-acceptance-receipt.md" in outcome_room["files"]
    assert "archive-verification-packet.zip" in outcome_room["files"]
    assert "/" in outcome_room["routes"]
    assert "/killer-demo" in outcome_room["routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["proof_packet"][0]["filename"] == "rentgen-buyer-room-packet.zip"
    assert report["proof_packet"][1]["filename"] == "buyer-brief.md"
    assert report["proof_packet"][2]["filename"] == "buyer-pulse.md"
    assert report["exports"][0]["filename"] == "rentgen-buyer-room-packet.zip"
    assert report["exports"][1]["filename"] == "buyer-brief.md"
    assert report["exports"][2]["filename"] == "buyer-pulse.md"
    proof_filenames = [item["filename"] for item in report["proof_packet"]]
    export_filenames = [item["filename"] for item in report["exports"]]
    assert "rentgen-buyer-room-packet.zip" in proof_filenames
    assert "rentgen-buyer-room-packet.zip" in export_filenames
    assert "MEETING_CLOSE_RECEIPT.md" in proof_filenames
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in proof_filenames
    assert "archive-acceptance-receipt.md" in proof_filenames
    assert "archive-verification-packet.zip" in proof_filenames
    assert "archive-verification-packet.zip" in export_filenames
    assert "archive-acceptance-receipt.json" in export_filenames
    assert "killer-demo-manifest.json" in export_filenames
    assert any(item["route"] == "/evidence-bundle" for item in report["proof_packet"])
    assert any(item["route"] == "/approvals" for item in report["proof_packet"])
    assert any(item["route"] == "/audit" for item in report["proof_packet"])
    assert report["governance_refresh"]["ready"] is True
    assert report["acceptance_rollup"]["ready_to_claim"] is True
    assert report["acceptance_rollup"]["ready_to_continue"] is True
    assert any(
        item["id"] == "day0-activation-baseline" and item["evidence_file"] == "archive-acceptance-receipt.md"
        for item in report["acceptance_rollup"]["items"]
    )
    assert any(
        item["id"] == "day0-verification-packet" and item["evidence_file"] == "archive-verification-packet.zip"
        for item in report["acceptance_rollup"]["items"]
    )
    assert any(item["evidence_route"] == "/pilot-launchpad" for item in report["acceptance_rollup"]["items"])
    spine = report["post_purchase_proof_spine"]
    assert spine["ready_to_measure"] is True
    assert spine["ready_to_claim"] is True
    spine_filenames = [item["filename"] for item in spine["files"]]
    assert "rentgen-buyer-room-packet.zip" in spine_filenames
    assert "MEETING_CLOSE_RECEIPT.md" in spine_filenames
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in spine_filenames
    assert "archive-acceptance-receipt.md" in spine_filenames
    assert "archive-verification-packet.zip" in spine_filenames
    assert spine["buyer_room_packet"]["filename"] == "rentgen-buyer-room-packet.zip"
    assert spine["buyer_room_packet"]["hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert spine["archive_receipt"]["filename"] == "archive-acceptance-receipt.md"
    assert spine["verification_packet"]["filename"] == "archive-verification-packet.zip"
    assert spine["verification_packet"]["hash_header"] == "X-Verification-Packet-Sha256"
    assert "/outcome-ledger" in spine["required_routes"]
    assert {item["route"] for item in report["governance_refresh"]["gates"]} >= {
        "/approvals",
        "/audit",
        "/evidence-bundle",
        "/enterprise-trust-center",
    }
    assert "/outcome-ledger" in report["proof_routes"]
    assert "/approvals" in report["proof_routes"]
    assert "/audit" in report["proof_routes"]
    assert "Outcome Ledger" in report["markdown"]
    assert "Outcome Room Bridge" in report["markdown"]
    assert "Governance Refresh" in report["markdown"]
    assert "Acceptance Rollup" in report["markdown"]
    assert "Post-Purchase Proof Spine" in report["markdown"]
    assert "rentgen-buyer-room-packet.zip" in report["markdown"]
    assert "MEETING_CLOSE_RECEIPT.md" in report["markdown"]
    assert "archive-acceptance-receipt.md" in report["markdown"]
    assert "archive-verification-packet.zip" in report["markdown"]
    assert "open-first-path.md" in report["markdown"]


def test_outcome_ledger_keeps_trust_risk_visible():
    report = build_outcome_ledger(
        executive=_decision(status="watch", score=70),
        board_pack=_board_pack(status="risk", score=50, recommended_offer="platform-trust-pack"),
        buyer_concierge=_buyer_concierge(status="watch", score=72),
        commercial_offer_studio=_commercial_offer(status="watch", score=76),
        enterprise_trust_center=_trust_center(status="risk", score=45, failed_controls=3),
        business_case=_business_case(),
        scenario_hub=_decision(status="watch", score=70),
        pilot_launchpad=_pilot_launchpad(status="watch", score=70),
        demo_command_center=_decision(status="watch", score=70),
        productization={"status": "pass", "score": 80},
        value_packs={"decision": {"status": "watch", "score": 70}, "packs": []},
        vendor_portfolio={"decision": {"status": "watch", "score": 70}, "work_packages": []},
        client_name="ACME",
    )

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["recommended_motion"] == "platform-trust-pack"
    assert report["summary"]["severe_risks"] >= 1
    assert report["outcome_room_bridge"]["source"] == "outcome-ledger-derived"
    assert report["outcome_room_bridge"]["files"][0] == "rentgen-buyer-room-packet.zip"
    assert report["outcome_room_bridge"]["files"][1] == "open-first-path.md"
    assert report["outcome_room_bridge"]["files"][2] == "buyer-brief.md"
    assert [item["stage"] for item in report["outcome_room_bridge"]["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert report["governance_refresh"]["ready"] is False
    assert any(item["route"] == "/enterprise-trust-center" for item in report["adoption_timeline"])


def test_outcome_ledger_rolls_up_blocked_pilot_acceptance():
    pilot = _pilot_launchpad(status="watch", score=70)
    pilot["acceptance_register"] = {
        "items": [
            {
                "id": "day1-architecture",
                "role": "Architect",
                "owner": "architecture board",
                "window": "Day 1",
                "decision": "Accept platform and rollout risks.",
                "acceptance": "Productization blockers must be scoped.",
                "evidence_route": "/enterprise-trust-center",
                "evidence_file": "rentgen-enterprise-trust-center.md",
                "required_routes": ["/enterprise-trust-center", "/productization"],
                "status": "blocked",
                "blocker": "Productization is blocked.",
                "next_action": "Convert rollout into hardening scope.",
            }
        ],
        "proof_routes": ["/enterprise-trust-center", "/productization"],
    }

    report = build_outcome_ledger(
        executive=_decision(status="watch", score=70),
        board_pack=_board_pack(status="risk", score=50, recommended_offer="platform-trust-pack"),
        buyer_concierge=_buyer_concierge(status="watch", score=72),
        commercial_offer_studio=_commercial_offer(status="watch", score=76),
        enterprise_trust_center=_trust_center(status="risk", score=45, failed_controls=3),
        business_case=_business_case(),
        scenario_hub=_decision(status="watch", score=70),
        pilot_launchpad=pilot,
        demo_command_center=_decision(status="watch", score=70),
        productization={"status": "blocked", "score": 40},
        value_packs={"decision": {"status": "watch", "score": 70}, "packs": []},
        vendor_portfolio={"decision": {"status": "watch", "score": 70}, "work_packages": []},
        client_name="ACME",
    )

    assert report["acceptance_rollup"]["ready_to_claim"] is False
    assert report["acceptance_rollup"]["ready_to_continue"] is False
    assert report["summary"]["acceptance_rollup_blocked"] == 1
    assert report["post_purchase_proof_spine"]["ready_to_measure"] is False
    assert any(item["evidence_file"] == "archive-acceptance-receipt.md" for item in report["acceptance_rollup"]["items"])
    assert any(item["evidence_file"] == "archive-verification-packet.zip" for item in report["acceptance_rollup"]["items"])
    assert any(item["outcome_route"] == "/platform-doctor" for item in report["acceptance_rollup"]["items"])
    assert "/productization" in report["proof_routes"]
