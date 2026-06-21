"""Evidence Bundle API for approval, commercial and enterprise exports."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.api.killer_demo_api import (
    KILLER_DEMO_MANIFEST_FILES_HEADER,
    KILLER_DEMO_MANIFEST_HASH_HEADER,
    KILLER_DEMO_MANIFEST_HEADER,
    _artifact_reports,
    _killer_demo_archive,
    verify_killer_demo_archive_payload,
)
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.evidence_bundle import (
    attach_archive_verification_receipt,
    build_evidence_bundle,
    evidence_bundle_archive,
    verify_evidence_bundle_archive_payload,
)
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.killer_demo_path import KILLER_DEMO_ARCHIVE_HASH_HEADER, build_killer_demo_path

router = APIRouter(prefix="/api/v1/evidence-bundle", tags=["Evidence Bundle"])


class EvidenceBundleAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class EvidenceBundleRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    release_name: str | None = Field(default=None, max_length=160)
    lock_radar_log_path: str | None = Field(default=None, max_length=2000)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    include_demo: bool = True
    include_vendor: bool = True
    include_update: bool = True
    include_rights: bool = True
    include_lock_radar: bool = False
    include_extension_safety: bool = False
    include_test_factory: bool = True
    include_safe_autopilot: bool = True
    include_value_packs: bool = True
    include_business_case: bool = True
    include_board_pack: bool = True
    include_outcome_ledger: bool = True
    include_launch_room: bool = True
    include_killer_demo: bool = True
    include_buyer_concierge: bool = True
    include_commercial_offer_studio: bool = True
    include_demo_command_center: bool = True
    include_enterprise_trust_center: bool = True
    include_guided_demo: bool = True
    include_scenario_hub: bool = True
    include_pilot_launchpad: bool = True
    include_productization: bool = True
    include_governance_proof: bool = True
    assumptions: EvidenceBundleAssumptions | None = None


def _compose_bundle(req: EvidenceBundleRequest) -> dict[str, Any]:
    store = store_or_none()
    executive = build_executive_dashboard(
        store,
        coverage_items=COVERAGE_ITEMS,
        governance_limit=40,
        hotspot_limit=12,
        save_snapshot=False,
    )
    assumptions = req.assumptions.model_dump(exclude_none=True) if req.assumptions else None
    return build_evidence_bundle(
        executive=executive,
        store=store,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        release_name=req.release_name,
        changed_modules=req.changed_modules,
        lock_radar_log_path=req.lock_radar_log_path,
        assumptions=assumptions,
        include_demo=req.include_demo,
        include_vendor=req.include_vendor,
        include_update=req.include_update,
        include_rights=req.include_rights,
        include_lock_radar=req.include_lock_radar,
        include_extension_safety=req.include_extension_safety,
        include_test_factory=req.include_test_factory,
        include_safe_autopilot=req.include_safe_autopilot,
        include_value_packs=req.include_value_packs,
        include_business_case=req.include_business_case,
        include_board_pack=req.include_board_pack,
        include_outcome_ledger=req.include_outcome_ledger,
        include_launch_room=req.include_launch_room,
        include_killer_demo=req.include_killer_demo,
        include_buyer_concierge=req.include_buyer_concierge,
        include_commercial_offer_studio=req.include_commercial_offer_studio,
        include_demo_command_center=req.include_demo_command_center,
        include_enterprise_trust_center=req.include_enterprise_trust_center,
        include_guided_demo=req.include_guided_demo,
        include_scenario_hub=req.include_scenario_hub,
        include_pilot_launchpad=req.include_pilot_launchpad,
        include_productization=req.include_productization,
        include_governance_proof=req.include_governance_proof,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_archive_headers(archive_payload: dict[str, Any]) -> dict[str, str]:
    return {
        "X-Archive-Sha256": str(archive_payload["sha256"]),
        "X-Archive-Files": str(archive_payload["files"]),
        "X-Archive-Manifest": str(archive_payload["archive_manifest_file"]),
        "X-Archive-Manifest-Sha256": str(archive_payload["archive_manifest_sha256"]),
        "X-Archive-Manifest-Files": str(archive_payload["archive_manifest_files"]),
    }


def _killer_archive_headers(archive_payload: dict[str, Any]) -> dict[str, str]:
    return {
        "X-Archive-Sha256": str(archive_payload["sha256"]),
        KILLER_DEMO_ARCHIVE_HASH_HEADER: str(archive_payload["sha256"]),
        "X-Archive-Files": str(archive_payload["files"]),
        "X-Evidence-Archive-Sha256": str(archive_payload["evidence_sha256"]),
        KILLER_DEMO_MANIFEST_HEADER: str(archive_payload["killer_demo_manifest_file"]),
        KILLER_DEMO_MANIFEST_HASH_HEADER: str(archive_payload["killer_demo_manifest_sha256"]),
        KILLER_DEMO_MANIFEST_FILES_HEADER: str(archive_payload["killer_demo_manifest_files"]),
    }


def _killer_demo_report_from_bundle(req: EvidenceBundleRequest, bundle: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    reports = _artifact_reports(bundle)
    required = [
        "launch-room",
        "demo-command-center",
        "test-factory",
        "buyer-concierge",
        "scenario-hub",
        "enterprise-trust-center",
        "commercial-offer-studio",
        "board-pack",
        "outcome-ledger",
    ]
    missing = [item for item in required if item not in reports]
    if missing:
        return None, missing
    return (
        build_killer_demo_path(
            launch_room=reports["launch-room"],
            demo_command_center=reports["demo-command-center"],
            test_factory=reports["test-factory"],
            buyer_concierge=reports["buyer-concierge"],
            scenario_hub=reports["scenario-hub"],
            enterprise_trust_center=reports["enterprise-trust-center"],
            commercial_offer_studio=reports["commercial-offer-studio"],
            board_pack=reports["board-pack"],
            outcome_ledger=reports["outcome-ledger"],
            client_name=req.client_name,
            config_path=req.config_path,
            target_platform_version=req.target_platform_version,
            evidence_bundle=bundle,
        ),
        [],
    )


def _missing_killer_demo_verify(missing: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "fail",
        "archive_type": "killer-demo",
        "filename": "",
        "archive_sha256": "",
        "checked_files": 0,
        "required_files": [],
        "embedded_evidence_verify": None,
        "summary": {"findings": 1, "high": 1, "medium": 0, "low": 0},
        "findings": [
            {
                "severity": "high",
                "code": "killer-demo-prerequisite-artifacts-missing",
                "message": "Killer Demo archive cannot be built because required Evidence Bundle artifacts are absent.",
                "missing_artifacts": missing,
            }
        ],
    }
    return attach_archive_verification_receipt(result, expected_headers={})


def _dual_status(evidence_result: dict[str, Any], killer_result: dict[str, Any]) -> str:
    statuses = {str(evidence_result.get("status") or ""), str(killer_result.get("status") or "")}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _dual_verification_markdown(packet: dict[str, Any]) -> str:
    pair = packet.get("pair") or {}
    summary = packet.get("summary") or {}
    evidence = packet.get("evidence") or {}
    killer = packet.get("killer_demo") or {}
    lines = [
        "# Dual Archive Verification Packet",
        "",
        f"Status: **{packet.get('status', 'unknown')}**",
        f"Client: **{packet.get('client_name', '')}**",
        f"Generated at: `{packet.get('generated_at', '')}`",
        "",
        "## Pair",
        "",
        f"- Evidence ZIP: `{pair.get('evidence_archive_sha256', '')}`",
        f"- Killer Demo ZIP: `{pair.get('killer_archive_sha256', '')}`",
        f"- Killer embedded Evidence SHA-256: `{pair.get('killer_embedded_evidence_sha256', '')}`",
        f"- Same Evidence source archive: **{bool(pair.get('same_evidence_archive_hash'))}**",
        "",
        "## Summary",
        "",
        f"- Archives: **{summary.get('archives', 0)}**",
        f"- Pass: **{summary.get('pass', 0)}**",
        f"- Warn: **{summary.get('warn', 0)}**",
        f"- Fail: **{summary.get('fail', 0)}**",
        f"- High findings: **{summary.get('high', 0)}**",
        f"- Total findings: **{summary.get('findings', 0)}**",
        "",
        "## Evidence Archive",
        "",
        f"- Status: **{evidence.get('status', 'unknown')}**",
        f"- Filename: `{evidence.get('filename', '')}`",
        f"- Checked files: **{evidence.get('checked_files', 0)}**",
        "",
        "## Killer Demo Archive",
        "",
        f"- Status: **{killer.get('status', 'unknown')}**",
        f"- Filename: `{killer.get('filename', '')}`",
        f"- Checked files: **{killer.get('checked_files', 0)}**",
        "",
        "## Acceptance",
        "",
    ]
    if packet.get("status") == "pass":
        lines.append("- Record both archive hashes and attach this packet plus both archive verification receipts to the procurement ticket.")
    elif packet.get("status") == "warn":
        lines.append("- Record both archive hashes only after warning findings are accepted by security/procurement.")
    else:
        lines.append("- Do not forward the archive pair until high findings are fixed and the dual packet passes.")
    return "\n".join(lines).strip()


def _dual_archive_packet(
    *,
    req: EvidenceBundleRequest,
    evidence_result: dict[str, Any],
    killer_result: dict[str, Any],
) -> dict[str, Any]:
    status = _dual_status(evidence_result, killer_result)
    evidence_summary = evidence_result.get("summary") or {}
    killer_summary = killer_result.get("summary") or {}
    killer_headers = killer_result.get("expected_headers") or {}
    packet: dict[str, Any] = {
        "schema_version": "rentgen.dual_archive_verification_packet.v1",
        "generated_at": _now(),
        "status": status,
        "client_name": req.client_name,
        "summary": {
            "archives": 2,
            "pass": sum(1 for item in (evidence_result, killer_result) if item.get("status") == "pass"),
            "warn": sum(1 for item in (evidence_result, killer_result) if item.get("status") == "warn"),
            "fail": sum(1 for item in (evidence_result, killer_result) if item.get("status") == "fail"),
            "findings": int(evidence_summary.get("findings", 0)) + int(killer_summary.get("findings", 0)),
            "high": int(evidence_summary.get("high", 0)) + int(killer_summary.get("high", 0)),
            "medium": int(evidence_summary.get("medium", 0)) + int(killer_summary.get("medium", 0)),
            "low": int(evidence_summary.get("low", 0)) + int(killer_summary.get("low", 0)),
        },
        "pair": {
            "evidence_archive_sha256": evidence_result.get("archive_sha256"),
            "killer_archive_sha256": killer_result.get("archive_sha256"),
            "killer_embedded_evidence_sha256": killer_headers.get("X-Evidence-Archive-Sha256", ""),
            "same_evidence_archive_hash": bool(
                evidence_result.get("archive_sha256")
                and killer_headers.get("X-Evidence-Archive-Sha256") == evidence_result.get("archive_sha256")
            ),
        },
        "receipt_files": {
            "json": "dual-archive-verification-packet.json",
            "markdown": "dual-archive-verification-packet.md",
        },
        "evidence": evidence_result,
        "killer_demo": killer_result,
    }
    packet["verification_packet_markdown"] = _dual_verification_markdown(packet)
    return packet


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _verification_packet_open_first(packet: dict[str, Any]) -> str:
    pair = packet.get("pair") or {}
    summary = packet.get("summary") or {}
    return "\n".join(
        [
            "# Open First - Archive Verification Packet",
            "",
            f"Status: **{packet.get('status', 'unknown')}**",
            f"Client: **{packet.get('client_name', '')}**",
            "",
            "## Open Order",
            "",
            "1. `dual-archive-verification-packet.md` for the combined Evidence/Killer result.",
            "2. `hash-table.json` for machine-readable archive and receipt hashes.",
            "3. `evidence-archive-verification-receipt.md` for the Evidence ZIP receipt.",
            "4. `killer-demo-archive-verification-receipt.md` for the close-room ZIP receipt.",
            "",
            "## Pair Check",
            "",
            f"- Evidence archive SHA-256: `{pair.get('evidence_archive_sha256', '')}`",
            f"- Killer Demo archive SHA-256: `{pair.get('killer_archive_sha256', '')}`",
            f"- Same Evidence source archive: **{bool(pair.get('same_evidence_archive_hash'))}**",
            f"- High findings: **{summary.get('high', 0)}**",
            "",
            "Attach this small ZIP to the procurement or security ticket next to the two full archives.",
        ]
    )


def _hash_table(packet: dict[str, Any], files: list[tuple[str, bytes]]) -> dict[str, Any]:
    evidence = packet.get("evidence") or {}
    killer = packet.get("killer_demo") or {}
    pair = packet.get("pair") or {}
    return {
        "schema_version": "rentgen.archive_verification_hash_table.v1",
        "generated_at": _now(),
        "status": packet.get("status"),
        "archives": [
            {
                "id": "evidence-archive",
                "status": evidence.get("status"),
                "filename": evidence.get("filename"),
                "sha256": evidence.get("archive_sha256"),
                "hash_header": "X-Archive-Sha256",
                "checked_files": evidence.get("checked_files"),
                "receipt_file": "evidence-archive-verification-receipt.json",
            },
            {
                "id": "killer-demo-archive",
                "status": killer.get("status"),
                "filename": killer.get("filename"),
                "sha256": killer.get("archive_sha256"),
                "hash_header": KILLER_DEMO_ARCHIVE_HASH_HEADER,
                "checked_files": killer.get("checked_files"),
                "receipt_file": "killer-demo-archive-verification-receipt.json",
            },
        ],
        "pair": pair,
        "packet_files": [
            {
                "filename": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for filename, content in files
        ],
    }


def _verification_packet_archive(packet: dict[str, Any]) -> dict[str, Any]:
    evidence = packet.get("evidence") or {}
    killer = packet.get("killer_demo") or {}
    evidence_receipt = evidence.get("verification_receipt") or {}
    killer_receipt = killer.get("verification_receipt") or {}
    files: list[tuple[str, bytes]] = [
        ("OPEN_FIRST_VERIFICATION_PACKET.md", _verification_packet_open_first(packet).encode("utf-8")),
        ("dual-archive-verification-packet.json", _json_bytes(packet)),
        ("dual-archive-verification-packet.md", str(packet.get("verification_packet_markdown") or "").encode("utf-8")),
        ("evidence-archive-verification-receipt.json", _json_bytes(evidence_receipt)),
        (
            "evidence-archive-verification-receipt.md",
            str(evidence.get("verification_receipt_markdown") or "").encode("utf-8"),
        ),
        ("killer-demo-archive-verification-receipt.json", _json_bytes(killer_receipt)),
        (
            "killer-demo-archive-verification-receipt.md",
            str(killer.get("verification_receipt_markdown") or "").encode("utf-8"),
        ),
    ]
    files.append(("hash-table.json", _json_bytes(_hash_table(packet, files))))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files:
            archive.writestr(filename, content)
    payload = buffer.getvalue()
    client_slug = "".join(ch if ch.isalnum() else "-" for ch in str(packet.get("client_name") or "rentgen")).strip("-").lower()
    client_slug = client_slug or "rentgen"
    return {
        "filename": f"{client_slug}-archive-verification-packet.zip",
        "media_type": "application/zip",
        "bytes": payload,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "files": len(files),
        "status": str(packet.get("status") or "unknown"),
    }


@router.post("/build")
def build(req: EvidenceBundleRequest) -> dict[str, Any]:
    """Compose hashed JSON/Markdown evidence artifacts into one portable bundle."""

    return _compose_bundle(req)


@router.post("/archive")
def archive(req: EvidenceBundleRequest) -> Response:
    """Return a ZIP archive with bundle JSON, markdown artifacts and manifest."""

    bundle = _compose_bundle(req)
    archive_payload = evidence_bundle_archive(bundle)
    return Response(
        content=archive_payload["bytes"],
        media_type=archive_payload["media_type"],
        headers={
            "Content-Disposition": f"attachment; filename={archive_payload['filename']}",
            "X-Archive-Sha256": archive_payload["sha256"],
            "X-Archive-Files": str(archive_payload["files"]),
            "X-Archive-Manifest": archive_payload["archive_manifest_file"],
            "X-Archive-Manifest-Sha256": archive_payload["archive_manifest_sha256"],
            "X-Archive-Manifest-Files": str(archive_payload["archive_manifest_files"]),
        },
    )


@router.post("/archive/verify")
def verify_archive(req: EvidenceBundleRequest) -> dict[str, Any]:
    """Build and verify the Evidence Bundle ZIP without extracting it."""

    bundle = _compose_bundle(req)
    archive_payload = evidence_bundle_archive(bundle)
    result = verify_evidence_bundle_archive_payload(
        archive_payload["bytes"],
        filename=str(archive_payload.get("filename") or ""),
    )
    result["expected_headers"] = _evidence_archive_headers(archive_payload)
    attach_archive_verification_receipt(result, expected_headers=result["expected_headers"])
    return result


@router.post("/archive/verify-dual")
def verify_dual_archive(req: EvidenceBundleRequest) -> dict[str, Any]:
    """Build and verify the Evidence ZIP and linked Killer Demo ZIP as one procurement packet."""

    bundle = _compose_bundle(req)
    evidence_archive_payload = evidence_bundle_archive(bundle)
    evidence_result = verify_evidence_bundle_archive_payload(
        evidence_archive_payload["bytes"],
        filename=str(evidence_archive_payload.get("filename") or ""),
    )
    evidence_result["expected_headers"] = _evidence_archive_headers(evidence_archive_payload)
    attach_archive_verification_receipt(evidence_result, expected_headers=evidence_result["expected_headers"])

    killer_report, missing = _killer_demo_report_from_bundle(req, bundle)
    if killer_report is None:
        killer_result = _missing_killer_demo_verify(missing)
    else:
        killer_archive_payload = _killer_demo_archive(
            killer_report,
            bundle,
            evidence_archive=evidence_archive_payload,
        )
        killer_result = verify_killer_demo_archive_payload(
            killer_archive_payload["bytes"],
            filename=str(killer_archive_payload.get("filename") or ""),
        )
        killer_result["expected_headers"] = _killer_archive_headers(killer_archive_payload)
        attach_archive_verification_receipt(killer_result, expected_headers=killer_result["expected_headers"])

    return _dual_archive_packet(req=req, evidence_result=evidence_result, killer_result=killer_result)


@router.post("/archive/verification-packet")
def verification_packet_archive(req: EvidenceBundleRequest) -> Response:
    """Return a small ZIP with dual verification packet and both archive receipts."""

    packet = verify_dual_archive(req)
    archive_payload = _verification_packet_archive(packet)
    return Response(
        content=archive_payload["bytes"],
        media_type=archive_payload["media_type"],
        headers={
            "Content-Disposition": f"attachment; filename={archive_payload['filename']}",
            "X-Archive-Sha256": archive_payload["sha256"],
            "X-Verification-Packet-Sha256": archive_payload["sha256"],
            "X-Verification-Packet-Files": str(archive_payload["files"]),
            "X-Dual-Verification-Status": archive_payload["status"],
        },
    )


@router.get("/health")
def health() -> dict[str, Any]:
    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=10,
        hotspot_limit=5,
        save_snapshot=False,
    )
    pulse = build_buyer_pulse(executive=executive)
    return {
        "status": pulse["status"],
        "artifacts": 1,
        "files": 2,
        "procurement_status": pulse["purchase_status"],
        "procurement_missing_files": 0 if pulse["purchase_status"] == "ready" else 1,
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "source": pulse["source"],
    }
