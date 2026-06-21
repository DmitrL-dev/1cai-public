import hashlib
import io
import json
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import buyer_concierge_api, launch_room_api
from src.api.management_api import router
from src.services.rentgen.executive_dashboard import build_executive_dashboard


class FakeStore:
    def summary(self):
        return {
            "total_modules": 4,
            "avg_maintainability": 62.5,
            "modules_with_issues": 2,
            "by_domain": [
                {"domain": "Sales", "count": 3, "avg_maintainability": 44.0},
                {"domain": "HR", "count": 1, "avg_maintainability": 82.0},
            ],
        }

    def get_stats(self):
        return {"call_edges": 1234, "modules": 4, "quality_modules": 4}

    def hotspots(self, limit=40, domain=None, min_fan_in=0):
        return [
            {
                "module_path": "CommonModules/Sales/Ext/Module.bsl",
                "domain": "Sales",
                "risk": 84,
                "fan_in": 18,
                "maintainability_score": 41,
                "reasons": [{"factor": "fan_in", "detail": "18"}],
            },
            {
                "module_path": "CommonModules/HR/Ext/Module.bsl",
                "domain": "HR",
                "risk": 35,
                "fan_in": 2,
                "maintainability_score": 82,
                "reasons": [],
            },
        ][:limit]


def fake_offline_readiness(strict=False, include_metadata=True):
    return {
        "decision": {"status": "pass", "score": 96, "fails": 0, "warnings": 0},
        "summary": {"checks": 6, "passes": 6, "warnings": 0, "fails": 0, "external_env": 0},
        "runtime": {
            "its_rag_mode": "offline",
            "metadata_scan": "included" if include_metadata else "skipped",
        },
    }


def test_executive_dashboard_builds_manager_decision(monkeypatch):
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    report = build_executive_dashboard(
        FakeStore(),
        coverage_items=[
            {"id": "quality", "status": "done", "stage": "review", "priority": "P0"},
            {"id": "governance", "status": "partial", "stage": "governance", "priority": "P1"},
        ],
    )

    assert report["available"] is True
    assert report["kpis"]["modules"] == 4
    assert report["kpis"]["call_edges"] == 1234
    assert report["risk_summary"]["high_hotspots"] == 1
    assert report["governance"]["summary"]["red_areas"] == 1
    # HONESTY: coverage reflects the real mix (done=1.0 + partial=0.55)/2 = 77.5 -> 78,
    # never a hardcoded 100/fixed +25.
    assert report["coverage"]["score"] == round((1.0 + 0.55) / 2 * 100)
    assert report["coverage"]["score"] < 100
    assert report["kpis"]["coverage_score"] == report["coverage"]["score"]
    coverage_ws = next(w for w in report["workstreams"] if w["id"] == "coverage")
    assert coverage_ws["status"] == "watch"
    assert report["coverage_ledger"]["summary"]["items"] >= 5
    assert report["coverage_ledger"]["summary"]["caveats"] >= 1
    assert report["offline"]["runtime"]["metadata_scan"] == "skipped"
    assert any(action["owner"] == "delivery lead" for action in report["manager_actions"])
    assert "Executive Dashboard" in report["markdown"]


def test_executive_dashboard_coverage_na_without_items(monkeypatch):
    # No coverage signal -> score is n/a (None), weight is dropped and the rest is
    # re-normalised, instead of fabricating a 0 or 100 coverage contribution.
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    report = build_executive_dashboard(FakeStore(), coverage_items=[])

    assert report["coverage"]["score"] is None
    assert report["coverage"]["available"] is False
    assert report["kpis"]["coverage_score"] is None
    coverage_ws = next(w for w in report["workstreams"] if w["id"] == "coverage")
    assert coverage_ws["status"] == "unknown"
    # Decision score is still produced from the other (available) signals.
    assert report["decision"]["score"] > 0


def test_executive_dashboard_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/management/executive")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["score"] > 0
    assert payload["kpis"]["modules"] == 4
    assert payload["manager_actions"]


def test_management_buyer_pulse_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/management/buyer-pulse", params={"monthly_ai_subscription_cost": 200_000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "management-fast-pulse"
    assert payload["commercial"]["monthly_ai_rent"] == "200 000 RUB"
    assert payload["commercial"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert payload["commercial"]["local_license_anchor"] == "1 800 000 RUB"
    assert payload["purchase_path"]["primary_route"] == "/killer-demo"
    assert payload["purchase_path"]["procurement_handoff"]["title"] == "Procurement-ready handoff"
    assert payload["purchase_path"]["procurement_handoff"]["open_order"][0]["hash_header"] == (
        "X-Buyer-Room-Packet-Sha256"
    )
    assert payload["purchase_path"]["procurement_handoff"]["open_order"][0]["endpoint"] == (
        "/api/v1/management/buyer-room-packet"
    )
    assert payload["purchase_path"]["procurement_handoff"]["open_order"][1]["hash_header"] == "X-Archive-Sha256"
    assert payload["purchase_path"]["procurement_handoff"]["open_order"][2]["hash_header"] == (
        "X-Killer-Demo-Archive-Sha256"
    )
    assert payload["purchase_path"]["procurement_handoff"]["open_order"][3]["endpoint"] == (
        "/api/v1/evidence-bundle/archive/verification-packet"
    )
    assert len(payload["purchase_path"]["steps"]) == 5
    assert payload["purchase_path"]["steps"][2]["file"] == "MEETING_CLOSE_RECEIPT.md"
    assert "rentgen-buyer-room-packet.zip" in payload["purchase_path"]["send_files"]
    assert "POST_DEMO_ACTIVATION_HANDOFF.md" in payload["purchase_path"]["send_files"]
    assert "archive-acceptance-receipt.md" in payload["purchase_path"]["send_files"]
    assert "archive-verification-packet.zip" in payload["purchase_path"]["send_files"]
    assert "killer-demo-manifest.json" in payload["purchase_path"]["send_files"]
    assert payload["purchase_path"]["buyer_room_packet_artifact"]["endpoint"] == (
        "/api/v1/management/buyer-room-packet"
    )
    assert payload["purchase_path"]["buyer_room_packet_artifact"]["hash_header"] == "X-Buyer-Room-Packet-Sha256"
    assert payload["purchase_path"]["verification_packet_artifact"]["endpoint"] == (
        "/api/v1/evidence-bundle/archive/verification-packet"
    )
    assert payload["purchase_path"]["verification_packet_artifact"]["hash_header"] == "X-Verification-Packet-Sha256"
    assert payload["launch"]["route"] == "/launch-room"
    assert payload["concierge"]["route"] == "/buyer-concierge"
    assert payload["evidence"]["route"] == "/evidence-bundle"


def test_management_buyer_brief_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/management/buyer-brief", params={"monthly_ai_subscription_cost": 200_000})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "management-buyer-brief"
    assert payload["pulse"]["source"] == "management-fast-pulse"
    assert payload["commercial"]["three_year_ai_rent"] == "7 200 000 RUB"
    assert payload["primary_motion"]["route"] in {"/launch-room", "/board-pack", "/configurations"}
    assert payload["coverage_ledger"]["summary"]["items"] >= 5
    assert payload["coverage_ledger"]["summary"]["caveats"] >= 1
    assert payload["summary"]["roles"] == 5
    assert payload["summary"]["proof_items"] == 4
    assert payload["summary"]["meeting_steps"] == 4
    assert payload["summary"]["open_first_steps"] == 4
    assert payload["summary"]["purchase_path_steps"] == 5
    assert payload["summary"]["purchase_path_files"] >= 5
    assert payload["summary"]["procurement_handoff_steps"] == 6
    assert payload["summary"]["room_plan_files"] >= 4
    assert payload["summary"]["coverage_caveats"] == payload["coverage_ledger"]["summary"]["caveats"]
    assert payload["buyer_room_plan"]["evidence_contract"] == "buyer_room_plan_v1"
    assert payload["buyer_room_plan"]["role"] == "developer"
    assert payload["buyer_room_plan"]["route"] == "/change"
    assert payload["buyer_room_plan"]["proof_file"] == "rentgen-developer-report.md"
    assert payload["buyer_room_plan"]["close_question"]
    assert "buyer-brief.md" in payload["buyer_room_plan"]["send_files"]
    assert [item["stage"] for item in payload["open_first_path"]] == ["orient", "prove", "close", "verify"]
    assert payload["open_first_path"][0]["source"] == "buyer_room_plan"
    assert payload["open_first_path"][3]["file"] == "archive-verification-packet.zip"
    assert payload["purchase_path"]["primary_route"] == "/killer-demo"
    assert payload["purchase_path"]["buyer_room_packet_artifact"]["file"] == "rentgen-buyer-room-packet.zip"
    assert payload["purchase_path"]["close_artifact"]["file"] == "MEETING_CLOSE_RECEIPT.md"
    assert payload["purchase_path"]["activation_artifact"]["file"] == "POST_DEMO_ACTIVATION_HANDOFF.md"
    assert payload["purchase_path"]["archive_receipt_artifact"]["file"] == "archive-acceptance-receipt.md"
    assert payload["purchase_path"]["verification_packet_artifact"]["file"] == "archive-verification-packet.zip"
    handoff = payload["purchase_path"]["procurement_handoff"]
    assert handoff["acceptance"]
    assert any(item["file"] == "rentgen-buyer-room-packet.zip" for item in handoff["attachments"])
    assert any(item["file"] == "archive-verification-packet.zip" for item in handoff["attachments"])
    assert any(item["hash_header"] == "X-Buyer-Room-Packet-Sha256" for item in handoff["open_order"])
    assert any(item["hash_header"] == "X-Verification-Packet-Sha256" for item in handoff["open_order"])
    assert "archive-acceptance-receipt.json" in payload["purchase_path"]["send_files"]
    assert "rentgen-buyer-room-packet.zip" in payload["purchase_path"]["send_files"]
    assert "archive-verification-packet.zip" in payload["purchase_path"]["send_files"]
    assert "killer-demo-manifest.json" in payload["purchase_path"]["send_files"]
    assert any(item["label"] == "Activate" and item["route"] == "/pilot-launchpad" for item in payload["purchase_path"]["steps"])
    assert {item["role"] for item in payload["role_cards"]} == {
        "developer",
        "architect",
        "director",
        "security",
        "vendor",
    }
    assert any(item["role"] == "security" and item["route"] == "/enterprise-trust-center" for item in payload["role_cards"])
    assert any(item["id"] == "audit-siem" and item["file"] == "rentgen-audit-siem.jsonl" for item in payload["proof_readiness"])
    assert {
        "/buyer-concierge",
        "/killer-demo",
        "/evidence-bundle",
        "/pilot-launchpad",
        "/outcome-ledger",
        "/approvals",
        "/enterprise-trust-center",
    } <= set(payload["routes"])
    assert payload["primary_motion"]["route"] in payload["routes"]
    assert payload["buyer_room_plan"]["route"] in payload["routes"]
    assert len(payload["meeting_flow"]) == 4
    assert [item["route"] for item in payload["meeting_flow"]] == [
        "/buyer-concierge",
        "/killer-demo",
        payload["primary_motion"]["route"],
        "/evidence-bundle",
    ]


def test_management_buyer_room_packet_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get("/api/v1/management/buyer-room-packet", params={"monthly_ai_subscription_cost": 200_000})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["x-buyer-room-packet-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert int(response.headers["x-buyer-room-packet-files"]) >= 14
    assert response.headers["x-buyer-room-packet-open-first"] == "OPEN_FIRST_BUYER_ROOM.md"

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "OPEN_FIRST_BUYER_ROOM.md",
            "buyer-brief.json",
            "buyer-brief.md",
            "buyer-pulse.json",
            "buyer-pulse.md",
            "open-first-path.json",
            "open-first-path.md",
            "buyer-room-plan.json",
            "buyer-room-plan.md",
            "purchase-path.json",
            "purchase-path.md",
            "procurement-handoff.json",
            "procurement-handoff.md",
            "hash-table.json",
        } <= names
        procurement_handoff = archive.read("procurement-handoff.md").decode("utf-8")
        assert "rentgen-buyer-room-packet.zip" in procurement_handoff
        assert "X-Buyer-Room-Packet-Sha256" in procurement_handoff
        assert "archive-verification-packet.zip" in procurement_handoff
        assert "X-Verification-Packet-Sha256" in procurement_handoff
        open_first = archive.read("OPEN_FIRST_BUYER_ROOM.md").decode("utf-8")
        assert "buyer-brief.md" in open_first
        assert "open-first-path.md" in open_first
        assert "hash-table.json" in open_first
        open_first_path = json.loads(archive.read("open-first-path.json").decode("utf-8"))
        assert [item["stage"] for item in open_first_path] == ["orient", "prove", "close", "verify"]
        assert "Verification Packet ZIP" in archive.read("open-first-path.md").decode("utf-8")
        hash_table = json.loads(archive.read("hash-table.json").decode("utf-8"))
        assert hash_table["open_first"] == "OPEN_FIRST_BUYER_ROOM.md"
        assert any(item["file"] == "open-first-path.md" for item in hash_table["files"])
        assert any(item["file"] == "procurement-handoff.md" for item in hash_table["files"])


def test_management_buyer_room_packet_verify_api(monkeypatch):
    monkeypatch.setattr("src.api.management_api.store_or_none", lambda: FakeStore())
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    response = client.get(
        "/api/v1/management/buyer-room-packet/verify",
        params={"monthly_ai_subscription_cost": 200_000},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pass"
    assert payload["archive_type"] == "buyer-room-packet"
    assert payload["checked_files"] == 14
    assert payload["open_first_status"] == "pass"
    assert payload["hash_table_status"] == "pass"
    assert payload["expected_headers"]["X-Buyer-Room-Packet-Sha256"] == payload["archive_sha256"]
    assert payload["expected_headers"]["X-Buyer-Room-Packet-Files"] == "14"
    assert payload["expected_headers"]["X-Buyer-Room-Packet-Open-First"] == "OPEN_FIRST_BUYER_ROOM.md"
    assert "hash-table.json" in payload["required_files"]
    assert payload["summary"]["findings"] == 0
    assert payload["findings"] == []


def test_buyer_health_endpoints_do_not_build_deep_reports(monkeypatch):
    monkeypatch.setattr(
        "src.services.rentgen.executive_dashboard.build_offline_readiness",
        fake_offline_readiness,
    )
    monkeypatch.setattr(launch_room_api, "store_or_none", lambda: FakeStore())
    monkeypatch.setattr(buyer_concierge_api, "store_or_none", lambda: FakeStore())

    def fail_deep_build(_req):
        raise AssertionError("health must not build deep buyer report")

    monkeypatch.setattr(launch_room_api, "_build_report", fail_deep_build)
    monkeypatch.setattr(buyer_concierge_api, "_build_report", fail_deep_build)

    launch_app = FastAPI()
    launch_app.include_router(launch_room_api.router)
    launch_client = TestClient(launch_app)

    launch_response = launch_client.get("/api/v1/launch-room/health")
    assert launch_response.status_code == 200
    launch_payload = launch_response.json()
    assert launch_payload["source"] == "management-fast-pulse"
    assert launch_payload["three_year_ai_rent"] == "4 320 000 RUB"

    concierge_app = FastAPI()
    concierge_app.include_router(buyer_concierge_api.router)
    concierge_client = TestClient(concierge_app)

    concierge_response = concierge_client.get("/api/v1/buyer-concierge/health")
    assert concierge_response.status_code == 200
    concierge_payload = concierge_response.json()
    assert concierge_payload["source"] == "management-fast-pulse"
    assert concierge_payload["purchase_router_status"] in {"ready", "watch", "risk"}
