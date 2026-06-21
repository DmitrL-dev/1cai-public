import hashlib
import json
import zipfile
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.services import audit_log
from src.api import evidence_bundle_api
from src.services.rentgen import approval_workflow
from src.services.rentgen.evidence_bundle import (
    build_evidence_bundle,
    evidence_bundle_archive,
    verify_evidence_bundle_archive_payload,
)
from src.services.rentgen.killer_demo_path import (
    MEETING_CLOSE_RECEIPT_JSON,
    MEETING_CLOSE_RECEIPT_MD,
    POST_DEMO_ACTIVATION_JSON,
    POST_DEMO_ACTIVATION_MD,
)


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


def test_evidence_bundle_builds_hashed_manifest(tmp_path, monkeypatch):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>DemoERP</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    monkeypatch.setenv("ONEC_PLATFORM_VERSION", "8.3.25.1000")
    monkeypatch.setattr(approval_workflow, "STORE_PATH", tmp_path / "approval_records.json")
    monkeypatch.setattr(audit_log, "LOG_PATH", tmp_path / "audit_log.ndjson")
    approval_workflow.create_approval_record(
        tool_name="write_module_source",
        actor="developer",
        approval_reason="Safe Autopilot reviewed the diff, tests and module scope.",
        risk="write",
        requested_by="developer",
        linked_record_type="safe_autopilot_plan",
        linked_record_id="sap_test",
        argument_constraints={"source": "safe-autopilot", "modulePath": "CommonModules/Sales/Ext/Module.bsl"},
        expires_in_hours=12,
    )
    audit_log.record_event(
        action="safe_autopilot.approval.requested",
        actor="developer",
        target="sap_test",
        category="approval",
        metadata={"source": "test"},
    )

    report = build_evidence_bundle(
        executive=_executive_report(),
        client_name="ACME",
        config_path=str(tmp_path),
        target_platform_version="8.3.26.1000",
        assumptions={"monthly_ai_subscription_cost": 200_000},
        include_update=False,
        include_rights=False,
    )

    assert report["client"]["name"] == "ACME"
    assert report["summary"]["artifacts"] >= 4
    assert report["manifest"]["bundle_sha256"]
    assert report["summary"]["procurement_required_files"] >= 10
    assert report["summary"]["procurement_missing_files"] == 0
    assert report["summary"]["procurement_recipients"] >= 4
    assert report["summary"]["archive_acceptance_steps"] == 3
    assert all(len(item["sha256"]) == 64 for item in report["manifest"]["files"])
    assert any(item["id"] == "buyer-pulse" for item in report["artifacts"])
    assert any(item["id"] == "vendor-portfolio" for item in report["artifacts"])
    assert any(item["id"] == "business-case" for item in report["artifacts"])
    assert any(item["id"] == "launch-room" for item in report["artifacts"])
    assert any(item["id"] == "killer-demo" for item in report["artifacts"])
    assert any(item["id"] == "test-factory" for item in report["artifacts"])
    assert any(item["id"] == "safe-autopilot" for item in report["artifacts"])
    assert any(item["id"] == "board-pack" for item in report["artifacts"])
    assert any(item["id"] == "outcome-ledger" for item in report["artifacts"])
    assert any(item["id"] == "buyer-concierge" for item in report["artifacts"])
    assert any(item["id"] == "commercial-offer-studio" for item in report["artifacts"])
    assert any(item["id"] == "demo-command-center" for item in report["artifacts"])
    assert any(item["id"] == "role-report-developer" for item in report["artifacts"])
    assert any(item["id"] == "role-report-architect" for item in report["artifacts"])
    assert any(item["id"] == "role-report-director" for item in report["artifacts"])
    assert any(item["id"] == "role-report-qa" for item in report["artifacts"])
    assert any(item["id"] == "guided-demo" for item in report["artifacts"])
    assert any(item["id"] == "scenario-hub" for item in report["artifacts"])
    assert any(item["id"] == "pilot-launchpad" for item in report["artifacts"])
    assert any(item["id"] == "enterprise-trust-center" for item in report["artifacts"])
    assert any(item["id"] == "security-questionnaire" for item in report["artifacts"])
    assert any(item["id"] == "productization" for item in report["artifacts"])
    assert any(item["id"] == "governance-proof" for item in report["artifacts"])
    assert any(item["id"] == "buyer-brief" for item in report["artifacts"])
    assert any(item["id"] == "buyer-room-plan" for item in report["artifacts"])
    questionnaire_artifact = next(item for item in report["artifacts"] if item["id"] == "security-questionnaire")
    questionnaire_report = json.loads(questionnaire_artifact["json"])
    assert questionnaire_report["summary"]["sections"] >= 8
    assert "Security Questionnaire" in questionnaire_artifact["markdown"]
    governance_artifact = next(item for item in report["artifacts"] if item["id"] == "governance-proof")
    assert governance_artifact["route"] == "/approvals"
    governance_report = json.loads(governance_artifact["json"])
    assert governance_report["summary"]["approval_records"] == 1
    assert governance_report["summary"]["audit_events"] == 1
    assert governance_report["audit"]["valid"] is True
    assert governance_report["summary"]["siem_events"] == 1
    assert governance_report["summary"]["siem_ready"] is True
    assert governance_report["siem_handoff"]["endpoint"] == "/api/v1/audit/siem-export"
    assert governance_report["siem_handoff"]["schema"] == "rentgen.audit.siem.v1"
    assert governance_report["siem_handoff"]["content_sha256"]
    assert governance_report["decision"]["status"] == "ready"
    killer_artifact = next(item for item in report["artifacts"] if item["id"] == "killer-demo")
    killer_report = json.loads(killer_artifact["json"])
    assert killer_report["proof_packet"]["bundle_id"] == report["bundle_id"]
    assert killer_report["proof_packet"]["file_count"] >= 1
    business_artifact = next(item for item in report["artifacts"] if item["id"] == "business-case")
    business_report = json.loads(business_artifact["json"])
    buyer_pulse_artifact = next(item for item in report["artifacts"] if item["id"] == "buyer-pulse")
    buyer_pulse_report = json.loads(buyer_pulse_artifact["json"])
    assert buyer_pulse_report["buyer_pulse"]["commercial"]["monthly_ai_rent"] == "200 000 RUB"
    assert buyer_pulse_report["buyer_pulse"]["commercial"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert buyer_pulse_report["buyer_pulse"]["purchase_path"]["primary_route"] == "/killer-demo"
    assert "rentgen-buyer-room-packet.zip" in buyer_pulse_report["buyer_pulse"]["purchase_path"]["send_files"]
    assert "MEETING_CLOSE_RECEIPT.md" in buyer_pulse_report["buyer_pulse"]["purchase_path"]["send_files"]
    assert "archive-acceptance-receipt.md" in buyer_pulse_report["buyer_pulse"]["purchase_path"]["send_files"]
    assert "archive-verification-packet.zip" in buyer_pulse_report["buyer_pulse"]["purchase_path"]["send_files"]
    assert "archive-acceptance-receipt.md" in buyer_pulse_artifact["markdown"]
    assert buyer_pulse_report["summary"]["proof_routes"] == 12
    assert "Buyer Pulse" in buyer_pulse_artifact["markdown"]
    buyer_brief_artifact = next(item for item in report["artifacts"] if item["id"] == "buyer-brief")
    buyer_brief_report = json.loads(buyer_brief_artifact["json"])
    assert buyer_brief_report["buyer_brief"]["commercial"]["monthly_ai_rent"] == "200 000 RUB"
    assert buyer_brief_report["buyer_brief"]["commercial"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert buyer_brief_report["summary"]["roles"] == 5
    assert buyer_brief_report["summary"]["proof_items"] == 4
    assert buyer_brief_report["summary"]["open_first_steps"] == 4
    assert buyer_brief_report["summary"]["purchase_path_steps"] == 5
    assert [item["stage"] for item in buyer_brief_report["buyer_brief"]["open_first_path"]] == [
        "orient",
        "prove",
        "close",
        "verify",
    ]
    assert buyer_brief_report["buyer_brief"]["purchase_path"]["close_artifact"]["file"] == "MEETING_CLOSE_RECEIPT.md"
    assert buyer_brief_report["buyer_brief"]["purchase_path"]["activation_artifact"]["file"] == "POST_DEMO_ACTIVATION_HANDOFF.md"
    assert buyer_brief_report["buyer_brief"]["purchase_path"]["archive_receipt_artifact"]["file"] == "archive-acceptance-receipt.md"
    assert buyer_brief_report["buyer_brief"]["purchase_path"]["buyer_room_packet_artifact"]["file"] == "rentgen-buyer-room-packet.zip"
    assert buyer_brief_report["buyer_brief"]["purchase_path"]["verification_packet_artifact"]["file"] == "archive-verification-packet.zip"
    assert "archive-acceptance-receipt.json" in buyer_brief_report["buyer_brief"]["purchase_path"]["send_files"]
    assert "rentgen-buyer-room-packet.zip" in buyer_brief_report["buyer_brief"]["purchase_path"]["send_files"]
    assert "archive-verification-packet.zip" in buyer_brief_report["buyer_brief"]["purchase_path"]["send_files"]
    assert "archive-acceptance-receipt.md" in buyer_brief_artifact["markdown"]
    assert "Open-First Path" in buyer_brief_artifact["markdown"]
    assert "archive-verification-packet.zip" in buyer_brief_artifact["markdown"]
    assert any(item["role"] == "security" for item in buyer_brief_report["buyer_brief"]["role_cards"])
    assert any(item["id"] == "audit-siem" for item in buyer_brief_report["buyer_brief"]["proof_readiness"])
    assert "Buyer Brief" in buyer_brief_artifact["markdown"]
    assert "Buyer Room Plan" in buyer_brief_artifact["markdown"]
    buyer_room_plan_artifact = next(item for item in report["artifacts"] if item["id"] == "buyer-room-plan")
    buyer_room_plan_report = json.loads(buyer_room_plan_artifact["json"])
    assert buyer_room_plan_report["decision"]["status"] == "ready"
    assert buyer_room_plan_report["summary"]["evidence_contract"] == "buyer_room_plan_v1"
    assert buyer_room_plan_report["summary"]["mode"] == "developer-spark"
    assert buyer_room_plan_report["summary"]["role"] == "developer"
    assert buyer_room_plan_report["summary"]["route"] == "/change"
    assert buyer_room_plan_report["summary"]["proof_file"] == "rentgen-developer-report.md"
    assert buyer_room_plan_report["summary"]["sequence_steps"] == 3
    assert buyer_room_plan_report["summary"]["send_files"] >= 4
    assert "buyer-brief.md" in buyer_room_plan_report["buyer_room_plan"]["send_files"]
    assert "MEETING_CLOSE_RECEIPT.md" in buyer_room_plan_report["buyer_room_plan"]["send_files"]
    assert "Would this remove" in buyer_room_plan_report["buyer_room_plan"]["close_question"]
    assert "Buyer Room Plan" in buyer_room_plan_artifact["markdown"]
    assert "buyer-room-plan.md" in buyer_room_plan_artifact["markdown"]
    open_first_path_artifact = next(item for item in report["artifacts"] if item["id"] == "open-first-path")
    open_first_path_report = json.loads(open_first_path_artifact["json"])
    assert open_first_path_report["decision"]["status"] == "ready"
    assert open_first_path_report["summary"]["steps"] == 4
    assert open_first_path_report["summary"]["stages"] == ["orient", "prove", "close", "verify"]
    assert "Open-First Path" in open_first_path_artifact["markdown"]
    assert "archive-verification-packet.zip" in open_first_path_artifact["markdown"]
    board_artifact = next(item for item in report["artifacts"] if item["id"] == "board-pack")
    board_report = json.loads(board_artifact["json"])
    assert business_report["summary"]["three_year_ai_subscription"] == 7_200_000
    assert board_report["board_snapshot"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert killer_report["commercial_close_packet"]["one_page_order"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert killer_report["deal_readiness"]["local_asset_case"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert report["summary"]["commercial_assumption_source"] == "business-case"
    assert report["commercial_assumptions"]["monthly_ai_rent_label"] == "200 000 RUB"
    assert report["commercial_assumptions"]["three_year_ai_rent_label"] == "7 200 000 RUB"
    assert "7 200 000 RUB" in report["open_first_markdown"]
    assert "7 200 000 RUB" in report["procurement_handoff"]["markdown"]
    assert "buyer-brief.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "buyer-room-plan.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "buyer-room-plan.json" in [item["filename"] for item in report["manifest"]["files"]]
    assert "buyer-pulse.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "business-case.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "launch-room.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "killer-demo.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "test-factory.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "board-pack.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "outcome-ledger.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "buyer-concierge.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "commercial-offer-studio.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "demo-command-center.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "rentgen-developer-report.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "rentgen-architect-report.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "rentgen-director-report.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "rentgen-qa-report.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "guided-demo.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "scenario-hub.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "pilot-launchpad.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "enterprise-trust-center.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "rentgen-security-questionnaire.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "productization-readiness.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "governance-proof.md" in [item["filename"] for item in report["manifest"]["files"]]
    assert "Evidence Bundle" in report["markdown"]
    assert "Procurement Handoff" in report["markdown"]
    assert "Archive Acceptance Receipt" in report["markdown"]
    assert "Role Packets" in report["open_first_markdown"]
    assert "buyer-room-plan.md" in report["open_first_markdown"]
    assert "open-first-path.md" in report["open_first_markdown"]
    assert "archive-acceptance-receipt.md" in report["open_first_markdown"]
    assert "archive-verification-packet.zip" in report["open_first_markdown"]
    assert "OPEN_FIRST.md" not in [item["filename"] for item in report["manifest"]["files"]]
    handoff = report["procurement_handoff"]
    assert handoff["bundle_id"] == report["bundle_id"]
    assert handoff["bundle_sha256"] == report["manifest"]["bundle_sha256"]
    assert handoff["archive_endpoint"] == "/api/v1/evidence-bundle/archive"
    assert handoff["archive_filename"].endswith("-evidence-archive.zip")
    assert handoff["archive_hash_header"] == "X-Archive-Sha256"
    assert handoff["open_first_file"] == "OPEN_FIRST.md"
    killer_bridge = handoff["killer_demo_handoff"]
    assert killer_bridge["status"] == "ready"
    assert killer_bridge["route"] == "/killer-demo"
    assert killer_bridge["archive_endpoint"] == "/api/v1/killer-demo/archive"
    assert killer_bridge["archive_filename"].endswith("-killer-demo-archive.zip")
    assert killer_bridge["archive_hash_header"] == "X-Killer-Demo-Archive-Sha256"
    assert killer_bridge["open_first_file"] == "OPEN_FIRST_KILLER_DEMO.md"
    assert killer_bridge["manifest_file"] == "killer-demo-manifest.json"
    assert "killer-demo-manifest.json" in killer_bridge["files"]
    assert MEETING_CLOSE_RECEIPT_MD in killer_bridge["post_demo_files"]
    assert MEETING_CLOSE_RECEIPT_JSON in killer_bridge["post_demo_files"]
    assert POST_DEMO_ACTIVATION_MD in killer_bridge["post_demo_files"]
    assert POST_DEMO_ACTIVATION_JSON in killer_bridge["post_demo_files"]
    assert any(item["role"] == "Director / sponsor" for item in killer_bridge["recipient_overlays"])
    assert any(item["id"] == "killer-demo-zip" for item in handoff["gates"])
    assert any(item["id"] == "archive-verification-packet" for item in handoff["gates"])
    assert any(item["id"] == "killer-demo-linked-archive" for item in handoff["verification_steps"])
    assert any(item["id"] == "archive-verification-packet" for item in handoff["verification_steps"])
    verification_packet = handoff["verification_packet"]
    assert verification_packet["filename"] == "archive-verification-packet.zip"
    assert verification_packet["endpoint"] == "/api/v1/evidence-bundle/archive/verification-packet"
    assert verification_packet["hash_header"] == "X-Verification-Packet-Sha256"
    assert verification_packet["open_first_file"] == "OPEN_FIRST_VERIFICATION_PACKET.md"
    assert "hash-table.json" in verification_packet["contains"]
    assert "archive-verification-packet.zip" in handoff["control_attachments"]
    assert "Linked Killer Demo ZIP" in handoff["markdown"]
    assert "Verification Packet ZIP" in handoff["markdown"]
    assert MEETING_CLOSE_RECEIPT_MD in handoff["markdown"]
    assert POST_DEMO_ACTIVATION_MD in report["open_first_markdown"]
    archive_receipt = report["archive_acceptance_receipt"]
    expected_receipt_status = "ready" if handoff["ready_to_forward"] and killer_bridge["available"] else "review_required"
    assert archive_receipt["status"] == expected_receipt_status
    assert archive_receipt["buyer_line"].startswith("Record both archive downloads")
    assert archive_receipt["acceptance_steps"][0]["id"] == "record-evidence-archive"
    assert any(item["id"] == "evidence-archive" for item in archive_receipt["archives"])
    assert any(item["id"] == "linked-killer-demo-archive" for item in archive_receipt["archives"])
    assert archive_receipt["control_packets"][0]["filename"] == "archive-verification-packet.zip"
    evidence_archive = next(item for item in archive_receipt["archives"] if item["id"] == "evidence-archive")
    linked_archive = next(item for item in archive_receipt["archives"] if item["id"] == "linked-killer-demo-archive")
    assert evidence_archive["hash_header"] == "X-Archive-Sha256"
    assert evidence_archive["archive_manifest_file"] == "archive-manifest.json"
    assert "archive-manifest.json" in evidence_archive["contains"]
    assert "VERIFY_ARCHIVE.md" in evidence_archive["contains"]
    assert linked_archive["hash_header"] == "X-Killer-Demo-Archive-Sha256"
    assert linked_archive["manifest_file"] == "killer-demo-manifest.json"
    assert "archive-acceptance-receipt.md" in evidence_archive["contains"]
    assert "buyer-room-plan.md" in evidence_archive["contains"]
    assert "ROLE_DIRECTOR_SPONSOR.md" in evidence_archive["contains"]
    assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in evidence_archive["contains"]
    assert "ROLE_DEVELOPER_QA.md" in evidence_archive["contains"]
    assert "ROLE_DEVELOPER_QA-forwarding-note.txt" in evidence_archive["contains"]
    assert MEETING_CLOSE_RECEIPT_MD in evidence_archive["excludes"]
    assert POST_DEMO_ACTIVATION_MD in evidence_archive["excludes"]
    assert "killer-demo-manifest.json" in linked_archive["contains"]
    assert MEETING_CLOSE_RECEIPT_MD in linked_archive["contains"]
    assert POST_DEMO_ACTIVATION_MD in linked_archive["contains"]
    assert "Archive Acceptance Receipt" in archive_receipt["markdown"]
    assert handoff["missing_files"] == []
    assert len(handoff["required_files"]) == report["summary"]["procurement_required_files"]
    assert any(item["filename"] == "commercial-offer-studio.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "buyer-brief.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "buyer-room-plan.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "buyer-pulse.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "rentgen-developer-report.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "rentgen-architect-report.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "rentgen-director-report.md" and item["present"] for item in handoff["required_files"])
    assert any(item["filename"] == "rentgen-security-questionnaire.md" and item["present"] for item in handoff["required_files"])
    assert any(item["role"] == "Security / procurement" for item in handoff["recipients"])
    director_recipient = next(item for item in handoff["recipients"] if item["role"] == "Director / sponsor")
    assert director_recipient["packet_file"] == "ROLE_DIRECTOR_SPONSOR.md"
    assert "buyer-brief.md" in director_recipient["send_files"]
    assert "buyer-room-plan.md" in director_recipient["send_files"]
    assert "buyer-pulse.md" in director_recipient["send_files"]
    assert "archive-verification-packet.zip" in director_recipient["send_files"]
    security_recipient = next(item for item in handoff["recipients"] if item["role"] == "Security / procurement")
    assert security_recipient["packet_file"] == "ROLE_SECURITY_PROCUREMENT.md"
    assert "buyer-brief.md" in security_recipient["send_files"]
    assert "buyer-room-plan.md" in security_recipient["send_files"]
    assert "buyer-pulse.md" in security_recipient["send_files"]
    assert "rentgen-security-questionnaire.md" in security_recipient["send_files"]
    assert "archive-verification-packet.zip" in security_recipient["send_files"]
    assert len(handoff["recipient_packets"]) == len(handoff["recipients"])
    director_packet = next(item for item in handoff["recipient_packets"] if item["role"] == "Director / sponsor")
    assert director_packet["filename"] == "ROLE_DIRECTOR_SPONSOR.md"
    assert director_packet["forwarding_filename"] == "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt"
    assert len(director_packet["markdown_sha256"]) == 64
    assert "Director / sponsor Evidence Packet" in director_packet["markdown"]
    assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in director_packet["markdown"]
    assert "buyer-room-plan.md" in director_packet["markdown"]
    assert "commercial-offer-studio.md" in director_packet["markdown"]
    assert "archive-verification-packet.zip" in director_packet["markdown"]
    assert "control-attachment" in director_packet["markdown"]
    assert director_packet["forwarding_subject"].endswith("evidence packet for Director / sponsor")
    assert "Start with ROLE_DIRECTOR_SPONSOR.md." in director_packet["forwarding_body"]
    assert "X-Archive-Sha256" in director_packet["forwarding_body"]
    assert "linked Killer Demo ZIP" in director_packet["forwarding_body"]
    assert "ROLE_DIRECTOR_SPONSOR.md" in director_packet["attachments"]
    assert "archive-acceptance-receipt.md" in director_packet["attachments"]
    assert "archive-verification-packet.zip" in director_packet["attachments"]
    assert "commercial-offer-studio.md" in director_packet["attachments"]
    assert any(item["id"] == "manifest" for item in handoff["verification_steps"])
    assert "OPEN_FIRST.md" in handoff["archive_contents"]
    assert "archive-manifest.json" in handoff["archive_contents"]
    assert "VERIFY_ARCHIVE.md" in handoff["archive_contents"]
    assert "procurement-handoff.md" in handoff["archive_contents"]
    assert "archive-acceptance-receipt.md" in handoff["archive_contents"]
    assert "ROLE_DIRECTOR_SPONSOR.md" in handoff["archive_contents"]
    assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in handoff["archive_contents"]
    assert "ROLE_ARCHITECT_CTO.md" in handoff["archive_contents"]
    assert "ROLE_ARCHITECT_CTO-forwarding-note.txt" in handoff["archive_contents"]
    assert "ROLE_SECURITY_PROCUREMENT.md" in handoff["archive_contents"]
    assert "ROLE_SECURITY_PROCUREMENT-forwarding-note.txt" in handoff["archive_contents"]
    assert "ROLE_DEVELOPER_QA.md" in handoff["archive_contents"]
    assert "ROLE_DEVELOPER_QA-forwarding-note.txt" in handoff["archive_contents"]
    assert "buyer-brief.md" in handoff["archive_contents"]
    assert "buyer-room-plan.md" in handoff["archive_contents"]
    assert "buyer-pulse.md" in handoff["archive_contents"]
    assert "rentgen-security-questionnaire.md" in handoff["archive_contents"]
    assert "archive-verification-packet.zip" not in handoff["archive_contents"]
    assert MEETING_CLOSE_RECEIPT_MD not in handoff["archive_contents"]
    assert POST_DEMO_ACTIVATION_MD not in handoff["archive_contents"]

    archive = evidence_bundle_archive(report)
    assert archive["filename"].endswith("-evidence-archive.zip")
    assert archive["sha256"]
    assert archive["archive_manifest_file"] == "archive-manifest.json"
    assert len(archive["archive_manifest_sha256"]) == 64
    assert archive["archive_manifest_files"] == archive["archive_manifest"]["file_count"]
    assert archive["files"] >= report["summary"]["files"] + 5
    verified = verify_evidence_bundle_archive_payload(archive["bytes"], filename=archive["filename"])
    assert verified["status"] == "pass"
    assert verified["archive_sha256"] == archive["sha256"]
    assert verified["checked_files"] == archive["archive_manifest_files"]
    assert verified["summary"]["findings"] == 0
    assert verified["verification_receipt"]["status"] == "pass"
    assert verified["verification_receipt"]["decision"]["status"] == "ready_to_record"
    assert "Archive Verification Receipt" in verified["verification_receipt_markdown"]
    with zipfile.ZipFile(BytesIO(archive["bytes"])) as zip_file:
        names = set(zip_file.namelist())
        assert "OPEN_FIRST.md" in names
        assert "manifest.json" in names
        assert "archive-manifest.json" in names
        assert "VERIFY_ARCHIVE.md" in names
        assert "bundle.json" in names
        assert "evidence-bundle.md" in names
        assert "README.md" in names
        assert "procurement-handoff.json" in names
        assert "procurement-handoff.md" in names
        assert "archive-acceptance-receipt.json" in names
        assert "archive-acceptance-receipt.md" in names
        assert "archive-verification-packet.zip" not in names
        assert "ROLE_DIRECTOR_SPONSOR.md" in names
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in names
        assert "ROLE_ARCHITECT_CTO.md" in names
        assert "ROLE_ARCHITECT_CTO-forwarding-note.txt" in names
        assert "ROLE_SECURITY_PROCUREMENT.md" in names
        assert "ROLE_SECURITY_PROCUREMENT-forwarding-note.txt" in names
        assert "ROLE_DEVELOPER_QA.md" in names
        assert "ROLE_DEVELOPER_QA-forwarding-note.txt" in names
        assert "business-case.md" in names
        assert "buyer-brief.json" in names
        assert "buyer-brief.md" in names
        assert "buyer-room-plan.json" in names
        assert "buyer-room-plan.md" in names
        assert "buyer-pulse.json" in names
        assert "buyer-pulse.md" in names
        assert "rentgen-developer-report.md" in names
        assert "rentgen-architect-report.md" in names
        assert "rentgen-director-report.md" in names
        assert "rentgen-qa-report.md" in names
        assert "rentgen-security-questionnaire.json" in names
        assert "rentgen-security-questionnaire.md" in names
        assert MEETING_CLOSE_RECEIPT_MD not in names
        assert MEETING_CLOSE_RECEIPT_JSON not in names
        assert POST_DEMO_ACTIVATION_MD not in names
        assert POST_DEMO_ACTIVATION_JSON not in names
        manifest = json.loads(zip_file.read("manifest.json").decode("utf-8"))
        assert manifest["bundle_sha256"] == report["manifest"]["bundle_sha256"]
        archive_manifest = json.loads(zip_file.read("archive-manifest.json").decode("utf-8"))
        assert archive_manifest["schema_version"] == "rentgen.evidence_archive_manifest.v1"
        assert archive_manifest["source_manifest_file"] == "manifest.json"
        assert archive_manifest["source_manifest_bundle_sha256"] == report["manifest"]["bundle_sha256"]
        archive_manifest_files = {item["filename"]: item for item in archive_manifest["files"]}
        assert "archive-manifest.json" not in archive_manifest_files
        assert "OPEN_FIRST.md" in archive_manifest_files
        assert "VERIFY_ARCHIVE.md" in archive_manifest_files
        assert "ROLE_DIRECTOR_SPONSOR.md" in archive_manifest_files
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in archive_manifest_files
        assert archive_manifest_files["ROLE_DIRECTOR_SPONSOR.md"]["sha256"] == hashlib.sha256(
            zip_file.read("ROLE_DIRECTOR_SPONSOR.md")
        ).hexdigest()
        assert archive_manifest_files["ROLE_DIRECTOR_SPONSOR-forwarding-note.txt"]["sha256"] == hashlib.sha256(
            zip_file.read("ROLE_DIRECTOR_SPONSOR-forwarding-note.txt")
        ).hexdigest()
        open_first = zip_file.read("OPEN_FIRST.md").decode("utf-8")
        assert "Role Packets" in open_first
        assert "archive-manifest.json" in open_first
        assert "VERIFY_ARCHIVE.md" in open_first
        assert "Linked Killer Demo ZIP" in open_first
        assert "buyer-brief.md" in open_first
        assert "buyer-room-plan.md" in open_first
        assert "open-first-path.md" in open_first
        assert "buyer-pulse.md" in open_first
        assert "ROLE_DIRECTOR_SPONSOR.md" in open_first
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in open_first
        assert "rentgen-developer-report.md" in open_first
        assert "rentgen-security-questionnaire.md" in open_first
        assert MEETING_CLOSE_RECEIPT_MD in open_first
        assert POST_DEMO_ACTIVATION_MD in open_first
        assert "Ready to forward" in open_first
        readme = zip_file.read("README.md").decode("utf-8")
        assert "OPEN_FIRST.md" in readme
        assert "archive-acceptance-receipt.md" in readme
        assert "archive-verification-packet.zip" in readme
        assert "archive-manifest.json" in readme
        assert "VERIFY_ARCHIVE.md" in readme
        assert "buyer-room-plan.md" in readme
        assert "ROLE_*.md" in readme
        assert "ROLE_*-forwarding-note.txt" in readme
        assert "Linked Killer Demo ZIP" in readme
        assert "killer-demo-manifest.json" in readme
        assert "not in this Evidence Archive" in readme
        assert "7 200 000 RUB" in readme
        archive_handoff = json.loads(zip_file.read("procurement-handoff.json").decode("utf-8"))
        assert archive_handoff["bundle_id"] == report["bundle_id"]
        assert archive_handoff["commercial_assumptions"]["three_year_ai_rent_label"] == "7 200 000 RUB"
        assert archive_handoff["killer_demo_handoff"]["archive_endpoint"] == "/api/v1/killer-demo/archive"
        director_packet_md = zip_file.read("ROLE_DIRECTOR_SPONSOR.md").decode("utf-8")
        assert "Director / sponsor Evidence Packet" in director_packet_md
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in director_packet_md
        assert "buyer-room-plan.md" in director_packet_md
        assert "commercial-offer-studio.md" in director_packet_md
        assert "Evidence archive hash header" in director_packet_md
        director_forwarding_note = zip_file.read("ROLE_DIRECTOR_SPONSOR-forwarding-note.txt").decode("utf-8")
        assert director_forwarding_note.startswith("Subject: ACME: 1C Rentgen evidence packet")
        assert "Start with ROLE_DIRECTOR_SPONSOR.md." in director_forwarding_note
        assert "X-Archive-Sha256" in director_forwarding_note
        verify_archive_md = zip_file.read("VERIFY_ARCHIVE.md").decode("utf-8")
        assert "Verify Evidence Bundle Archive" in verify_archive_md
        assert "X-Archive-Manifest-Sha256" in verify_archive_md
        assert MEETING_CLOSE_RECEIPT_MD in verify_archive_md
        archive_receipt_json = json.loads(zip_file.read("archive-acceptance-receipt.json").decode("utf-8"))
        assert archive_receipt_json["archives"][0]["hash_header"] == "X-Archive-Sha256"
        assert archive_receipt_json["archives"][0]["archive_manifest_file"] == "archive-manifest.json"
        assert "VERIFY_ARCHIVE.md" in archive_receipt_json["archives"][0]["contains"]
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in archive_receipt_json["archives"][0]["contains"]
        assert archive_receipt_json["archives"][1]["hash_header"] == "X-Killer-Demo-Archive-Sha256"
        archive_receipt_md = zip_file.read("archive-acceptance-receipt.md").decode("utf-8")
        assert "Archive Acceptance Receipt" in archive_receipt_md
        assert "archive-manifest.json" in archive_receipt_md
        assert "ROLE_DIRECTOR_SPONSOR-forwarding-note.txt" in archive_receipt_md
        assert "Not standalone files in this archive" in archive_receipt_md
        assert MEETING_CLOSE_RECEIPT_MD in archive_receipt_md

    tampered = BytesIO()
    with zipfile.ZipFile(BytesIO(archive["bytes"])) as source, zipfile.ZipFile(
        tampered,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as target:
        for item in source.infolist():
            if item.is_dir():
                continue
            content = source.read(item.filename)
            if item.filename == "VERIFY_ARCHIVE.md":
                content = b"# Tampered verify guide"
            target.writestr(item.filename, content)
    tampered_verified = verify_evidence_bundle_archive_payload(tampered.getvalue(), filename=archive["filename"])
    assert tampered_verified["status"] == "fail"
    assert tampered_verified["verification_receipt"]["decision"]["status"] == "reject_archive"
    assert any(item["code"] == "archive-entry-hash-mismatch" for item in tampered_verified["findings"])


def test_evidence_bundle_can_include_lock_radar(tmp_path):
    log_file = tmp_path / "rphost_1" / "26022200.log"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(
        "12:00:02.000000-200000,TLOCK,p:1:1:1,Usr=Admin,Context='CommonModule.Sales.Module : 50 : Write()'\n",
        encoding="utf-8",
    )

    report = build_evidence_bundle(
        executive=_executive_report(),
        changed_modules=["CommonModule.Sales.Module"],
        lock_radar_log_path=str(log_file.parent.parent),
        include_update=False,
        include_rights=False,
        include_vendor=False,
        include_lock_radar=True,
        include_governance_proof=False,
    )

    artifact = next(item for item in report["artifacts"] if item["id"] == "lock-radar")
    assert artifact["status"] == "watch"
    assert artifact["summary"]["lock_waits"] == 1
    assert "lock-radar.md" in [item["filename"] for item in report["manifest"]["files"]]


def test_evidence_bundle_can_include_extension_safety(tmp_path):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>DemoERP</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    module = tmp_path / "Extensions" / "SalesPatch" / "CommonModules" / "Sales" / "Ext" / "Module.bsl"
    module.parent.mkdir(parents=True)
    module.write_text("Procedure BeforeWrite()\nSetPrivilegedMode(True);\nEndProcedure\n", encoding="utf-8")

    report = build_evidence_bundle(
        executive=_executive_report(),
        config_path=str(tmp_path),
        include_update=False,
        include_rights=False,
        include_vendor=False,
        include_extension_safety=True,
        include_governance_proof=False,
    )

    artifact = next(item for item in report["artifacts"] if item["id"] == "extension-safety")
    assert artifact["status"] == "risk"
    assert artifact["summary"]["extensions"] == 1
    assert "extension-safety.md" in [item["filename"] for item in report["manifest"]["files"]]


def test_procurement_handoff_blocks_when_required_files_are_missing(tmp_path):
    report = build_evidence_bundle(
        executive=_executive_report(),
        client_name="ACME",
        config_path=str(tmp_path),
        include_demo=False,
        include_vendor=False,
        include_update=False,
        include_rights=False,
        include_value_packs=False,
        include_business_case=False,
        include_board_pack=False,
        include_outcome_ledger=False,
        include_launch_room=False,
        include_killer_demo=False,
        include_buyer_concierge=False,
        include_commercial_offer_studio=False,
        include_demo_command_center=False,
        include_enterprise_trust_center=False,
        include_guided_demo=False,
        include_scenario_hub=False,
        include_pilot_launchpad=False,
        include_productization=False,
        include_governance_proof=False,
    )

    handoff = report["procurement_handoff"]
    assert handoff["status"] == "blocked"
    assert handoff["ready_to_forward"] is False
    assert report["summary"]["procurement_missing_files"] > 0
    assert any(item["filename"] == "board-pack.md" for item in handoff["missing_files"])
    assert any("Missing required file" in item for item in handoff["blockers"])


def test_evidence_bundle_archive_api_exposes_archive_manifest_headers(tmp_path, monkeypatch):
    (tmp_path / "Configuration.xml").write_text(
        "<MetaDataObject><Configuration><Properties><Name>DemoERP</Name></Properties></Configuration></MetaDataObject>",
        encoding="utf-8",
    )
    report = build_evidence_bundle(
        executive=_executive_report(),
        client_name="ACME",
        config_path=str(tmp_path),
        target_platform_version="8.3.26.1000",
        assumptions={"monthly_ai_subscription_cost": 200_000},
        include_update=False,
        include_rights=False,
    )
    monkeypatch.setattr(evidence_bundle_api, "_compose_bundle", lambda req: report)

    app = FastAPI()
    app.include_router(evidence_bundle_api.router)
    client = TestClient(app)

    response = client.post("/api/v1/evidence-bundle/archive", json={"client_name": "ACME"})

    assert response.status_code == 200
    assert response.headers["x-archive-manifest"] == "archive-manifest.json"
    assert len(response.headers["x-archive-manifest-sha256"]) == 64
    assert int(response.headers["x-archive-manifest-files"]) >= report["summary"]["files"]
    with zipfile.ZipFile(BytesIO(response.content)) as zip_file:
        manifest_hash = hashlib.sha256(zip_file.read("archive-manifest.json")).hexdigest()
    assert response.headers["x-archive-manifest-sha256"] == manifest_hash

    verify_response = client.post("/api/v1/evidence-bundle/archive/verify", json={"client_name": "ACME"})

    assert verify_response.status_code == 200
    verified = verify_response.json()
    assert verified["status"] == "pass"
    assert verified["archive_sha256"] == verified["expected_headers"]["X-Archive-Sha256"]
    assert verified["expected_headers"]["X-Archive-Manifest"] == "archive-manifest.json"
    assert len(verified["expected_headers"]["X-Archive-Manifest-Sha256"]) == 64
    assert verified["summary"]["high"] == 0
    assert verified["verification_receipt"]["expected_headers"]["X-Archive-Manifest"] == "archive-manifest.json"
    assert verified["verification_receipt"]["receipt_files"]["markdown"] == "archive-verification-receipt.md"
    assert "X-Archive-Manifest-Sha256" in verified["verification_receipt_markdown"]

    dual_response = client.post("/api/v1/evidence-bundle/archive/verify-dual", json={"client_name": "ACME"})

    assert dual_response.status_code == 200
    dual = dual_response.json()
    assert dual["status"] == "pass"
    assert dual["schema_version"] == "rentgen.dual_archive_verification_packet.v1"
    assert dual["summary"]["archives"] == 2
    assert dual["pair"]["same_evidence_archive_hash"] is True
    assert dual["pair"]["evidence_archive_sha256"] == dual["killer_demo"]["expected_headers"]["X-Evidence-Archive-Sha256"]
    assert dual["evidence"]["verification_receipt"]["decision"]["status"] == "ready_to_record"
    assert dual["killer_demo"]["verification_receipt"]["embedded_evidence"]["status"] == "pass"
    assert "Dual Archive Verification Packet" in dual["verification_packet_markdown"]

    packet_response = client.post("/api/v1/evidence-bundle/archive/verification-packet", json={"client_name": "ACME"})

    assert packet_response.status_code == 200
    assert packet_response.headers["x-dual-verification-status"] == "pass"
    assert len(packet_response.headers["x-verification-packet-sha256"]) == 64
    assert packet_response.headers["x-verification-packet-sha256"] == hashlib.sha256(packet_response.content).hexdigest()
    with zipfile.ZipFile(BytesIO(packet_response.content)) as packet_zip:
        packet_names = set(packet_zip.namelist())
        assert "OPEN_FIRST_VERIFICATION_PACKET.md" in packet_names
        assert "dual-archive-verification-packet.json" in packet_names
        assert "dual-archive-verification-packet.md" in packet_names
        assert "evidence-archive-verification-receipt.json" in packet_names
        assert "killer-demo-archive-verification-receipt.md" in packet_names
        assert "hash-table.json" in packet_names
        packet_json = json.loads(packet_zip.read("dual-archive-verification-packet.json").decode("utf-8"))
        hash_table = json.loads(packet_zip.read("hash-table.json").decode("utf-8"))
    assert packet_json["pair"]["same_evidence_archive_hash"] is True
    assert hash_table["pair"]["same_evidence_archive_hash"] is True
    assert any(item["filename"] == "dual-archive-verification-packet.md" for item in hash_table["packet_files"])


def test_evidence_bundle_health_does_not_build_deep_bundle(monkeypatch):
    monkeypatch.setattr(evidence_bundle_api, "store_or_none", lambda: None)

    def fail_deep_build(*args, **kwargs):
        raise AssertionError("health must not build deep evidence bundle")

    monkeypatch.setattr(evidence_bundle_api, "build_evidence_bundle", fail_deep_build)

    app = FastAPI()
    app.include_router(evidence_bundle_api.router)
    client = TestClient(app)

    response = client.get("/api/v1/evidence-bundle/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "management-fast-pulse"
    assert payload["three_year_ai_rent"] == "4 320 000 RUB"
    assert payload["artifacts"] == 1
