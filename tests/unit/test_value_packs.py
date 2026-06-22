from src.services.rentgen.value_packs import build_value_packs


def _buyer_brief():
    return {
        "status": "ready",
        "score": 88,
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
            {
                "role": "developer",
                "title": "Developer",
                "route": "/change",
                "status": "ready",
                "spark": "impact proof",
                "proof_file": "rentgen-developer-report.md",
            },
            {
                "role": "architect",
                "title": "Architect",
                "route": "/platform-doctor",
                "status": "ready",
                "spark": "platform proof",
                "proof_file": "rentgen-architect-report.md",
            },
            {
                "role": "director",
                "title": "Director",
                "route": "/board-pack",
                "status": "ready",
                "spark": "money proof",
                "proof_file": "board-pack.md",
            },
            {
                "role": "security",
                "title": "Security",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "spark": "trust proof",
                "proof_file": "rentgen-security-questionnaire.md",
            },
            {
                "role": "vendor",
                "title": "Vendor",
                "route": "/vendor-portfolio",
                "status": "ready",
                "spark": "audit proof",
                "proof_file": "vendor-portfolio.md",
            },
        ],
        "proof_readiness": [
            {
                "id": "bundle",
                "title": "Evidence Bundle",
                "route": "/evidence-bundle",
                "status": "ready",
                "signal": "hashed proof",
                "file": "OPEN_FIRST.md",
            },
            {
                "id": "approval",
                "title": "Approval gates",
                "route": "/approvals",
                "status": "ready",
                "signal": "governance proof",
                "file": "governance-proof.md",
            },
            {
                "id": "audit",
                "title": "Audit / SIEM",
                "route": "/audit",
                "status": "ready",
                "signal": "hash chain",
                "file": "rentgen-audit-siem.jsonl",
            },
            {
                "id": "trust",
                "title": "Enterprise Trust",
                "route": "/enterprise-trust-center",
                "status": "ready",
                "signal": "questionnaire",
                "file": "rentgen-security-questionnaire.md",
            },
        ],
        "meeting_flow": [
            {
                "step": 1,
                "label": "Orient",
                "route": "/buyer-concierge",
                "line": "Pick the role.",
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
                "line": "Ask for purchase.",
            },
            {
                "step": 4,
                "label": "Forward",
                "route": "/evidence-bundle",
                "line": "Forward packet.",
            },
        ],
    }


def test_value_packs_turn_features_into_buyer_outcomes():
    report = build_value_packs(
        {
            "decision": {"score": 78},
            "kpis": {
                "call_edges": 540,
                "red_areas": 1,
                "review_queue": 3,
                "offline_score": 92,
                "modules_with_issues": 17,
                "coverage_score": 89,
            },
            "coverage": {"score": 89},
            "risk_summary": {"high_hotspots": 2},
        },
        buyer_brief=_buyer_brief(),
    )

    assert report["summary"]["packs"] == 6
    assert report["summary"]["pilot_ready"] >= 5
    assert {pack["id"] for pack in report["packs"]} >= {
        "developer",
        "architect",
        "release-qa",
        "platform",
        "vendor",
    }
    assert "/vendor-portfolio" in report["markdown"]
    assert "token burn" in report["licensing_story"]
    assert report["summary"]["value_room_roles"] == 5
    assert report["summary"]["value_room_proofs"] == 4
    assert report["summary"]["value_room_steps"] == 4
    assert report["summary"]["value_room_open_first"] == 4
    assert report["value_room_bridge"]["source"] == "management-buyer-brief"
    assert report["value_room_bridge"]["files"][:3] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
    ]
    assert [
        item["stage"] for item in report["value_room_bridge"]["open_first_path"]
    ] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in report["value_room_bridge"]["routes"]
    assert "Value Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]


def test_value_packs_room_bridge_has_fallback_without_buyer_brief():
    report = build_value_packs({"decision": {"score": 70}, "kpis": {}, "coverage": {}})

    assert report["value_room_bridge"]["source"] == "value-packs-derived"
    assert report["value_room_bridge"]["files"][:3] == [
        "buyer-brief.md",
        "buyer-pulse.md",
        "open-first-path.md",
    ]
    assert [
        item["stage"] for item in report["value_room_bridge"]["open_first_path"]
    ] == ["orient", "prove", "close", "verify"]
    assert report["summary"]["value_room_roles"] == 5
