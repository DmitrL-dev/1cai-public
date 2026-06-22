import hashlib
import json
import zipfile
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import killer_demo_api


def _artifact(artifact_id: str) -> dict[str, str]:
    return {
        "id": artifact_id,
        "json": json.dumps({"decision": {"status": "ready", "score": 90}}),
    }


def _wire_app(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(killer_demo_api, "store_or_none", lambda: None)
    monkeypatch.setattr(
        killer_demo_api,
        "build_executive_dashboard",
        lambda *args, **kwargs: {"decision": {"status": "ready", "score": 90}},
    )

    def fake_bundle(**kwargs):
        captured["bundle_kwargs"] = kwargs
        return {
            "bundle_id": "evb_api",
            "manifest": {"bundle_sha256": "a" * 64, "files": []},
            "artifacts": [
                _artifact("launch-room"),
                _artifact("demo-command-center"),
                _artifact("test-factory"),
                _artifact("buyer-concierge"),
                _artifact("scenario-hub"),
                _artifact("enterprise-trust-center"),
                _artifact("commercial-offer-studio"),
                _artifact("board-pack"),
                _artifact("outcome-ledger"),
            ],
        }

    def fake_killer_path(**kwargs):
        captured["path_kwargs"] = kwargs
        return {
            "ok": True,
            "client": {"name": "ACME"},
            "decision": {"status": "ready", "score": 90},
            "download_name": "rentgen-killer-demo-path.md",
            "markdown": "# Killer Demo Path\n\nReady.",
            "proof_packet": {
                "ready_to_forward": True,
                "handoff": [
                    {
                        "recipient": "developer / QA",
                        "role_packet": "ROLE_DEVELOPER_QA.md",
                        "route": "/testing",
                        "send": [
                            "buyer-brief.md",
                            "rentgen-developer-report.md",
                            "test-factory.md",
                        ],
                        "available_files": [
                            "buyer-brief.md",
                            "rentgen-developer-report.md",
                        ],
                        "missing_files": ["test-factory.md"],
                        "availability_status": "partial",
                        "why": "Developer proof and test handoff.",
                    },
                    {
                        "recipient": "architect / security",
                        "role_packet": "ROLE_ARCHITECT_SECURITY.md",
                        "route": "/enterprise-trust-center",
                        "send": [
                            "buyer-brief.md",
                            "enterprise-trust-center.md",
                            "rights-rls.md",
                        ],
                        "available_files": [
                            "buyer-brief.md",
                            "enterprise-trust-center.md",
                        ],
                        "missing_files": ["rights-rls.md"],
                        "availability_status": "partial",
                        "why": "Trust, locality and access review.",
                    },
                    {
                        "recipient": "director / sponsor",
                        "role_packet": "ROLE_DIRECTOR_SPONSOR.md",
                        "route": "/board-pack",
                        "send": [
                            "buyer-brief.md",
                            "board-pack.md",
                            "commercial-offer-studio.md",
                        ],
                        "available_files": ["buyer-brief.md", "board-pack.md"],
                        "missing_files": ["commercial-offer-studio.md"],
                        "availability_status": "partial",
                        "why": "Decision and paid ask.",
                    },
                ],
                "procurement_handoff": {
                    "status": "ready_to_forward",
                    "missing_files": 0,
                    "blockers": 0,
                },
                "close_receipt": {
                    "ready": True,
                    "status": "ready_to_ask",
                    "route": "/killer-demo",
                    "filename": "MEETING_CLOSE_RECEIPT.md",
                    "json_filename": "meeting-close-receipt.json",
                    "next_paid_step": "Enterprise local license",
                    "why": "Post-demo receipt.",
                },
                "activation_handoff": {
                    "ready": True,
                    "status": "ready_to_start",
                    "route": "/pilot-launchpad",
                    "filename": "POST_DEMO_ACTIVATION_HANDOFF.md",
                    "json_filename": "post-demo-activation-handoff.json",
                    "next_window": "Day 7",
                    "why": "Post-demo activation route.",
                },
            },
            "meeting_close_receipt": {
                "schema_version": "1.0",
                "filename": "MEETING_CLOSE_RECEIPT.md",
                "json_filename": "meeting-close-receipt.json",
                "route": "/killer-demo",
                "client_name": "ACME",
                "status": "ready_to_ask",
                "ready_to_send": True,
                "ready_to_ask": True,
                "headline": "Proof and close are ready for the paid ask.",
                "decision": {"status": "ready", "score": 90, "headline": "Ready"},
                "primary_ask": "Approve enterprise local license.",
                "next_paid_step": {
                    "label": "Enterprise local license",
                    "route": "/commercial-offer-studio",
                    "owner": "director / CIO",
                    "acceptance": "Buyer names owner and accepted proof artifacts.",
                },
                "proof_packet": {
                    "forwardable": True,
                    "bundle_id": "evb_api",
                    "archive_filename": "evb_api-killer-demo-archive.zip",
                    "archive_endpoint": "/api/v1/killer-demo/archive",
                    "archive_hash_header": "X-Killer-Demo-Archive-Sha256",
                    "manifest": "killer-demo-manifest.json",
                    "open_first": "OPEN_FIRST_KILLER_DEMO.md",
                    "role_packet_rollup": "0/3 role packets fully covered; 3 partial.",
                    "procurement_status": "ready_to_forward",
                    "procurement_missing_files": 0,
                    "procurement_blockers": 0,
                },
                "committee": {
                    "status": "ready_to_ask",
                    "accepted_roles": 3,
                    "blocked_roles": 0,
                    "total_roles": 3,
                    "final_question": "Can we open procurement?",
                    "roles": [],
                },
                "role_packets": [],
                "blockers": [],
                "buyer_commitments": [],
                "checkout": [],
                "customer_can_repeat": ["Local evidence product."],
                "close_questions": ["Can we open procurement?"],
                "send_files": [
                    "MEETING_CLOSE_RECEIPT.md",
                    "meeting-close-receipt.json",
                ],
                "why": "Attach after the demo.",
            },
            "post_demo_activation_handoff": {
                "schema_version": "1.0",
                "filename": "POST_DEMO_ACTIVATION_HANDOFF.md",
                "json_filename": "post-demo-activation-handoff.json",
                "route": "/pilot-launchpad",
                "status": "ready_to_start",
                "ready_to_start": True,
                "headline": "Paid scope can start from the close receipt.",
                "activation_line": "Enterprise local license: Buyer names owner and accepted proof artifacts.",
                "next_paid_step": {
                    "label": "Enterprise local license",
                    "route": "/commercial-offer-studio",
                    "owner": "director / CIO",
                    "acceptance": "Buyer names owner and accepted proof artifacts.",
                },
                "invoice_trigger": "Buyer names owner and accepted proof artifacts.",
                "route_chain": [
                    "/killer-demo",
                    "/pilot-launchpad",
                    "/outcome-ledger",
                    "/evidence-bundle",
                ],
                "timeline": [
                    {
                        "window": "Day 0",
                        "owner": "director / CIO",
                        "action": "Start the paid scope.",
                        "route": "/commercial-offer-studio",
                        "proof_file": "MEETING_CLOSE_RECEIPT.md",
                        "exit": "Paid scope named.",
                        "status": "ready",
                    }
                ],
                "gates": [
                    {
                        "gate": "Close receipt is attached",
                        "status": "ready",
                        "route": "/killer-demo",
                        "evidence": "MEETING_CLOSE_RECEIPT.md",
                    }
                ],
                "role_packets": [],
                "proof_files": [
                    "MEETING_CLOSE_RECEIPT.md",
                    "POST_DEMO_ACTIVATION_HANDOFF.md",
                ],
                "outcome": {
                    "route": "/outcome-ledger",
                    "acceptance_rollup_ready": False,
                    "acceptance_items": 0,
                    "governance_refresh_ready": False,
                    "next_window": "Day 7",
                    "owner_line": "Day 7 proof.",
                },
                "blockers": [],
                "why": "Prevent post-demo drop.",
            },
        }

    monkeypatch.setattr(killer_demo_api, "build_evidence_bundle", fake_bundle)
    monkeypatch.setattr(killer_demo_api, "build_killer_demo_path", fake_killer_path)

    app = FastAPI()
    app.include_router(killer_demo_api.router)
    return TestClient(app), captured


def test_killer_demo_api_keeps_buyer_profile_light_by_default(monkeypatch):
    client, captured = _wire_app(monkeypatch)

    response = client.post("/api/v1/killer-demo/build", json={"client_name": "ACME"})

    assert response.status_code == 200
    kwargs = captured["bundle_kwargs"]
    assert kwargs["include_update"] is False
    assert kwargs["include_rights"] is False
    assert kwargs["include_lock_radar"] is False
    assert kwargs["include_extension_safety"] is False
    assert kwargs["include_killer_demo"] is False


def test_killer_demo_api_enterprise_profile_turns_on_deep_evidence(monkeypatch):
    client, captured = _wire_app(monkeypatch)

    response = client.post(
        "/api/v1/killer-demo/build",
        json={
            "client_name": "ACME",
            "evidence_profile": "enterprise",
            "lock_radar_log_path": "data/tj",
        },
    )

    assert response.status_code == 200
    kwargs = captured["bundle_kwargs"]
    assert kwargs["include_update"] is True
    assert kwargs["include_rights"] is True
    assert kwargs["include_lock_radar"] is True
    assert kwargs["include_extension_safety"] is True
    assert kwargs["lock_radar_log_path"] == "data/tj"


def test_killer_demo_api_allows_targeted_evidence_toggles(monkeypatch):
    client, captured = _wire_app(monkeypatch)

    response = client.post(
        "/api/v1/killer-demo/build",
        json={
            "client_name": "ACME",
            "include_rights": True,
            "include_lock_radar": True,
        },
    )

    assert response.status_code == 200
    kwargs = captured["bundle_kwargs"]
    assert kwargs["include_update"] is False
    assert kwargs["include_rights"] is True
    assert kwargs["include_lock_radar"] is True
    assert kwargs["include_extension_safety"] is False


def test_killer_demo_archive_merges_evidence_archive_and_current_demo(monkeypatch):
    client, _captured = _wire_app(monkeypatch)

    def fake_evidence_archive(bundle):
        evidence_files = {
            "manifest.json": "{}",
            "OPEN_FIRST.md": "# Evidence",
            "VERIFY_ARCHIVE.md": "# Verify Evidence",
            "bundle.json": "{}",
            "README.md": "# Evidence README",
            "procurement-handoff.md": "# Handoff",
            "procurement-handoff.json": "{}",
            "archive-acceptance-receipt.md": "# Receipt",
            "archive-acceptance-receipt.json": json.dumps(
                {
                    "archives": [
                        {
                            "id": "evidence-archive",
                            "contains": [
                                "manifest.json",
                                "OPEN_FIRST.md",
                                "VERIFY_ARCHIVE.md",
                                "bundle.json",
                                "README.md",
                                "procurement-handoff.md",
                                "procurement-handoff.json",
                                "archive-acceptance-receipt.md",
                                "archive-acceptance-receipt.json",
                            ],
                        }
                    ]
                }
            ),
        }
        archive_manifest = {
            "schema_version": "rentgen.evidence_archive_manifest.v1",
            "source_manifest_file": "manifest.json",
            "source_manifest_bundle_sha256": "",
            "file_count": len(evidence_files),
            "files": [
                {
                    "filename": filename,
                    "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "size_bytes": len(content.encode("utf-8")),
                }
                for filename, content in evidence_files.items()
            ],
        }
        buffer = BytesIO()
        with zipfile.ZipFile(
            buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for filename, content in evidence_files.items():
                archive.writestr(filename, content)
            archive.writestr("archive-manifest.json", json.dumps(archive_manifest))
        return {
            "filename": "evb_api-evidence-archive.zip",
            "media_type": "application/zip",
            "sha256": "b" * 64,
            "files": len(evidence_files) + 1,
            "bytes": buffer.getvalue(),
        }

    monkeypatch.setattr(
        killer_demo_api, "evidence_bundle_archive", fake_evidence_archive
    )

    response = client.post("/api/v1/killer-demo/archive", json={"client_name": "ACME"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-archive-sha256"]
    assert (
        response.headers["x-killer-demo-archive-sha256"]
        == response.headers["x-archive-sha256"]
    )
    assert response.headers["x-evidence-archive-sha256"] == "b" * 64
    assert response.headers["x-killer-demo-manifest"] == "killer-demo-manifest.json"
    assert len(response.headers["x-killer-demo-manifest-sha256"]) == 64
    with zipfile.ZipFile(BytesIO(response.content), mode="r") as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "OPEN_FIRST.md" in names
        assert "procurement-handoff.md" in names
        assert "archive-manifest.json" in names
        assert "README-KILLER-DEMO.md" in names
        assert "OPEN_FIRST_KILLER_DEMO.md" in names
        assert "VERIFY_ARCHIVE.md" in names
        assert "rentgen-killer-demo-path.md" in names
        assert "killer-demo.json" in names
        assert "proof-packet.json" in names
        assert "MEETING_CLOSE_RECEIPT.md" in names
        assert "meeting-close-receipt.json" in names
        assert "POST_DEMO_ACTIVATION_HANDOFF.md" in names
        assert "post-demo-activation-handoff.json" in names
        assert "killer-demo-manifest.json" in names
        assert "ROLE_DEVELOPER_QA.md" in names
        assert "ROLE_ARCHITECT_SECURITY.md" in names
        assert "ROLE_DIRECTOR_SPONSOR.md" in names
        demo_markdown = archive.read("rentgen-killer-demo-path.md")
        readme = archive.read("README-KILLER-DEMO.md").decode("utf-8")
        open_first = archive.read("OPEN_FIRST_KILLER_DEMO.md").decode("utf-8")
        verify_archive = archive.read("VERIFY_ARCHIVE.md").decode("utf-8")
        developer_packet = archive.read("ROLE_DEVELOPER_QA.md")
        close_receipt = archive.read("MEETING_CLOSE_RECEIPT.md")
        close_receipt_json = json.loads(
            archive.read("meeting-close-receipt.json").decode("utf-8")
        )
        activation_handoff = archive.read("POST_DEMO_ACTIVATION_HANDOFF.md")
        activation_handoff_json = json.loads(
            archive.read("post-demo-activation-handoff.json").decode("utf-8")
        )
        proof_packet = json.loads(archive.read("proof-packet.json").decode("utf-8"))
        demo_manifest_bytes = archive.read("killer-demo-manifest.json")
        demo_manifest = json.loads(demo_manifest_bytes.decode("utf-8"))
        demo_files = {item["filename"]: item for item in demo_manifest["files"]}
        handoff_packets = {item["role_packet"] for item in proof_packet["handoff"]}
        manifest_packets = {item["filename"] for item in demo_manifest["role_packets"]}
        assert "Killer Demo Path" in demo_markdown.decode("utf-8")
        assert "Role Packets" in open_first
        assert "ROLE_DEVELOPER_QA.md" in open_first
        assert "VERIFY_ARCHIVE.md" in open_first
        assert "X-Killer-Demo-Manifest-Sha256" in open_first
        assert "X-Killer-Demo-Manifest-Sha256" in readme
        assert "Verify Killer Demo Archive" in verify_archive
        assert "X-Killer-Demo-Manifest-Sha256" in verify_archive
        assert "archive-manifest.json" in verify_archive
        developer_packet_text = developer_packet.decode("utf-8")
        assert "Developer proof" in developer_packet_text
        assert "Available In This Archive" in developer_packet_text
        assert "Not Included In This Build" in developer_packet_text
        assert "test-factory.md" in developer_packet_text
        assert "Meeting Close Receipt" in close_receipt.decode("utf-8")
        assert (
            close_receipt_json["next_paid_step"]["label"] == "Enterprise local license"
        )
        assert "Post-Demo Activation Handoff" in activation_handoff.decode("utf-8")
        assert (
            activation_handoff_json["next_paid_step"]["label"]
            == "Enterprise local license"
        )
        assert demo_manifest["evidence_archive_sha256"] == "b" * 64
        assert demo_manifest["close_receipt"]["filename"] == "MEETING_CLOSE_RECEIPT.md"
        assert demo_manifest["close_receipt"]["ready_to_send"] is True
        assert (
            demo_manifest["activation_handoff"]["filename"]
            == "POST_DEMO_ACTIVATION_HANDOFF.md"
        )
        assert demo_manifest["activation_handoff"]["ready_to_start"] is True
        assert int(response.headers["x-killer-demo-manifest-files"]) == len(
            demo_manifest["files"]
        )
        assert (
            response.headers["x-killer-demo-manifest-sha256"]
            == hashlib.sha256(demo_manifest_bytes).hexdigest()
        )
        assert any(
            item["filename"] == "ROLE_DEVELOPER_QA.md"
            for item in demo_manifest["role_packets"]
        )
        assert handoff_packets == manifest_packets
        assert (
            demo_files["rentgen-killer-demo-path.md"]["sha256"]
            == hashlib.sha256(demo_markdown).hexdigest()
        )
        assert (
            demo_files["VERIFY_ARCHIVE.md"]["sha256"]
            == hashlib.sha256(verify_archive.encode("utf-8")).hexdigest()
        )
        assert (
            demo_files["ROLE_DEVELOPER_QA.md"]["sha256"]
            == hashlib.sha256(developer_packet).hexdigest()
        )
        assert (
            demo_files["MEETING_CLOSE_RECEIPT.md"]["sha256"]
            == hashlib.sha256(close_receipt).hexdigest()
        )
        assert (
            demo_files["POST_DEMO_ACTIVATION_HANDOFF.md"]["sha256"]
            == hashlib.sha256(activation_handoff).hexdigest()
        )
        embedded_archive_manifest = json.loads(
            archive.read("archive-manifest.json").decode("utf-8")
        )
        embedded_files = {
            item["filename"]: item for item in embedded_archive_manifest["files"]
        }
        assert (
            embedded_files["VERIFY_ARCHIVE.md"]["sha256"]
            == hashlib.sha256(verify_archive.encode("utf-8")).hexdigest()
        )

    verify_response = client.post(
        "/api/v1/killer-demo/archive/verify", json={"client_name": "ACME"}
    )

    assert verify_response.status_code == 200
    verified = verify_response.json()
    assert verified["status"] == "pass"
    assert (
        verified["archive_sha256"]
        == verified["expected_headers"]["X-Killer-Demo-Archive-Sha256"]
    )
    assert (
        verified["expected_headers"]["X-Killer-Demo-Manifest"]
        == "killer-demo-manifest.json"
    )
    assert verified["expected_headers"]["X-Evidence-Archive-Sha256"] == "b" * 64
    assert verified["embedded_evidence_verify"]["status"] == "pass"
    assert verified["summary"]["high"] == 0
    assert verified["verification_receipt"]["archive_type"] == "killer-demo"
    assert verified["verification_receipt"]["decision"]["status"] == "ready_to_record"
    assert verified["verification_receipt"]["embedded_evidence"]["status"] == "pass"
    assert "Embedded Evidence" in verified["verification_receipt_markdown"]
