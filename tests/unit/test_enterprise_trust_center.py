from src.api.enterprise_trust_center_api import _soften_preview_risk
from src.services.rentgen.enterprise_trust_center import build_enterprise_trust_center


def _decision(status="ready", score=88):
    return {"decision": {"status": status, "score": score, "headline": "ok"}}


def _productization(status="pass", score=90):
    return {
        "status": status,
        "score": score,
        "summary": {"findings": 0, "deliverables": 4},
        "deliverables": [
            {"id": "sbom-inventory-guide", "status": "pass"},
            {"id": "sbom-inventory-service", "status": "pass"},
            {"id": "offline-bundle-guide", "status": "pass"},
            {"id": "offline-bundle-service", "status": "pass"},
        ],
        "findings": [],
    }


def _offline(status="pass", score=92):
    return {
        "decision": {"status": status, "score": score},
        "summary": {"external_env": 0},
        "checks": [],
        "caveats": [],
    }


def _security(status="pass", score=91):
    return {
        "decision": {"status": status, "score": score},
        "summary": {"findings": 0, "external_exposure": 0},
        "recommendations": [],
        "caveats": [],
    }


def _rights(status="ready", score=89):
    return {
        "decision": {"status": status, "score": score},
        "summary": {"dangerous_rights": 0, "findings": 0},
        "findings": [],
        "caveats": [],
    }


def _buyer_brief():
    return {
        "status": "ready",
        "score": 89,
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


def test_enterprise_trust_center_builds_security_and_procurement_pack():
    report = build_enterprise_trust_center(
        executive=_decision(),
        platform={**_decision(), "checks": []},
        business_case=_decision(score=86),
        productization=_productization(),
        offline_readiness=_offline(),
        security_posture=_security(),
        rights_rls=_rights(),
        demo_command_center=_decision(score=84),
        pilot_launchpad=_decision(score=85),
        scenario_hub=_decision(score=83),
        vendor_portfolio={"decision": {"status": "ready", "score": 84}, "work_packages": [{"id": "platform"}]},
        evidence_artifacts=[{"id": "business-case"}, {"id": "demo-command-center"}],
        client_name="ACME",
        config_path="data/configs/unpacked",
        target_platform_version="8.3.26.1000",
        analysis_depth="preview",
        scan_limits={"security_module_limit": 1, "rights_role_limit": 10},
        buyer_brief=_buyer_brief(),
    )

    assert report["client"]["name"] == "ACME"
    assert report["decision"]["status"] == "ready"
    assert report["summary"]["controls"] >= 9
    assert report["summary"]["security_questions"] >= 6
    assert report["summary"]["questionnaire_sections"] >= 8
    assert report["summary"]["questionnaire_blocked"] == 0
    assert report["summary"]["procurement_items"] >= 8
    assert report["summary"]["install_modes"] >= 3
    assert report["summary"]["evidence_artifacts"] == 2
    assert report["summary"]["trust_room_roles"] == 5
    assert report["summary"]["trust_room_proofs"] == 4
    assert report["summary"]["trust_room_steps"] == 4
    assert report["summary"]["trust_room_open_first"] == 4
    assert report["security_questionnaire"]["status"] == "ready"
    assert report["trust_room_bridge"]["source"] == "management-buyer-brief"
    assert report["trust_room_bridge"]["files"][:3] == ["buyer-brief.md", "buyer-pulse.md", "open-first-path.md"]
    assert [item["stage"] for item in report["trust_room_bridge"]["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert "/killer-demo" in report["trust_room_bridge"]["routes"]
    assert report["security_questionnaire"]["ready_to_send"] is True
    assert report["security_questionnaire"]["ready_to_approve"] is True
    assert report["source_signals"]["analysis_depth"] == "preview"
    assert report["source_signals"]["security_module_limit"] == 1
    assert any("Preview depth" in item for item in report["caveats"])
    section_ids = {item["id"] for item in report["security_questionnaire"]["sections"]}
    assert {"data-locality", "artifact-integrity", "platform-upgrade"} <= section_ids
    assert "rentgen-security-questionnaire.md" in report["security_questionnaire"]["send_files"]
    control_ids = {item["id"] for item in report["trust_controls"]}
    assert {"local-contour", "sbom-inventory", "offline-bundle", "rights-rls"} <= control_ids
    assert "/enterprise-trust-center" in report["proof_routes"]
    assert "/killer-demo" in report["proof_routes"]
    assert report["exports"][:2] == [
        {"title": "Buyer Brief markdown", "filename": "buyer-brief.md", "route": "/"},
        {"title": "Buyer Pulse markdown", "filename": "buyer-pulse.md", "route": "/"},
    ]
    assert any(item["route"] == "/enterprise-trust-center" for item in report["exports"])
    assert "Enterprise Trust Center" in report["markdown"]
    assert "Security Questionnaire" in report["markdown"]
    assert "Trust Room Bridge" in report["markdown"]
    assert "Open-First Path" in report["markdown"]


def test_enterprise_trust_center_surfaces_blocking_trust_risk():
    report = build_enterprise_trust_center(
        executive=_decision(status="watch", score=70),
        platform={**_decision(status="watch", score=72), "checks": [{"status": "warn", "title": "Platform caveat"}]},
        business_case=_decision(status="watch", score=75),
        productization=_productization(status="fail", score=40),
        offline_readiness=_offline(status="fail", score=45),
        security_posture=_security(status="warn", score=60),
        rights_rls=_rights(status="risk", score=50),
        demo_command_center=_decision(status="watch", score=75),
        pilot_launchpad=_decision(status="watch", score=72),
        scenario_hub=_decision(status="watch", score=74),
        vendor_portfolio={"decision": {"status": "watch", "score": 70}, "work_packages": []},
        client_name="ACME",
    )

    assert report["decision"]["status"] == "risk"
    assert report["summary"]["failed_controls"] >= 3
    assert report["trust_room_bridge"]["source"] == "enterprise-trust-derived"
    assert report["trust_room_bridge"]["files"][2] == "open-first-path.md"
    assert report["summary"]["questionnaire_blocked"] >= 3
    assert report["summary"]["risk_items"] >= 1
    assert report["security_questionnaire"]["status"] == "blocked"
    assert report["security_questionnaire"]["ready_to_send"] is False
    assert any(item["status"] == "fail" for item in report["trust_controls"])


def test_preview_depth_softens_missing_fact_risk():
    report = {"decision": {"status": "risk", "score": 19, "headline": "missing facts"}, "caveats": []}

    softened = _soften_preview_risk(report, headline="Preview keeps this navigable.", score_floor=60)

    assert softened["decision"]["status"] == "watch"
    assert softened["decision"]["score"] == 60
    assert "Preview keeps this navigable." == softened["decision"]["headline"]
    assert any("Preview depth" in item for item in softened["caveats"])
