"""Killer Demo Path API for one buyer-ready presentation route."""

from __future__ import annotations

import hashlib
import json
import zipfile
from io import BytesIO
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.evidence_bundle import (
    attach_archive_verification_receipt,
    build_evidence_bundle,
    evidence_bundle_archive,
    verify_evidence_bundle_archive_payload,
)
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.killer_demo_path import (
    KILLER_DEMO_ARCHIVE_HASH_HEADER,
    MEETING_CLOSE_RECEIPT_JSON,
    MEETING_CLOSE_RECEIPT_MD,
    POST_DEMO_ACTIVATION_JSON,
    POST_DEMO_ACTIVATION_MD,
    build_killer_demo_path,
    meeting_close_receipt_markdown,
    post_demo_activation_handoff_markdown,
    role_packet_filename,
)

router = APIRouter(prefix="/api/v1/killer-demo", tags=["Killer Demo"])

KILLER_DEMO_MANIFEST_HEADER = "X-Killer-Demo-Manifest"
KILLER_DEMO_MANIFEST_HASH_HEADER = "X-Killer-Demo-Manifest-Sha256"
KILLER_DEMO_MANIFEST_FILES_HEADER = "X-Killer-Demo-Manifest-Files"
VERIFY_ARCHIVE_MD = "VERIFY_ARCHIVE.md"


class KillerDemoAssumptions(BaseModel):
    monthly_ai_subscription_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    hourly_rate: int | None = Field(default=None, ge=0, le=2_000_000)
    manual_review_hours_month: int | None = Field(default=None, ge=0, le=20_000)
    incident_cost: int | None = Field(default=None, ge=0, le=50_000_000)
    release_delay_hours_per_item: int | None = Field(default=None, ge=0, le=1_000)
    release_windows_per_month: int | None = Field(default=None, ge=0, le=100)
    currency: str | None = Field(default=None, max_length=12)


class KillerDemoRequest(BaseModel):
    client_name: str = Field(default="Demo client", min_length=1, max_length=200)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    release_name: str | None = Field(default=None, max_length=160)
    evidence_profile: Literal["buyer", "enterprise"] = "buyer"
    lock_radar_log_path: str | None = Field(default=None, max_length=2000)
    include_update: bool = False
    include_rights: bool = False
    include_lock_radar: bool = False
    include_extension_safety: bool = False
    governance_limit: int = Field(default=40, ge=1, le=200)
    hotspot_limit: int = Field(default=12, ge=1, le=50)
    assumptions: KillerDemoAssumptions | None = None


def _artifact_reports(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for artifact in bundle.get("artifacts", []):
        raw = artifact.get("json")
        if not raw:
            continue
        try:
            reports[str(artifact["id"])] = json.loads(raw)
        except (TypeError, ValueError):
            continue
    return reports


def _compose(req: KillerDemoRequest) -> tuple[dict[str, Any], dict[str, Any]]:
    store = store_or_none()
    executive = build_executive_dashboard(
        store,
        coverage_items=COVERAGE_ITEMS,
        governance_limit=req.governance_limit,
        hotspot_limit=req.hotspot_limit,
        save_snapshot=False,
    )
    assumptions = (
        req.assumptions.model_dump(exclude_none=True) if req.assumptions else None
    )
    enterprise_profile = req.evidence_profile == "enterprise"
    bundle = build_evidence_bundle(
        executive=executive,
        store=store,
        client_name=req.client_name,
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        release_name=req.release_name,
        changed_modules=req.changed_modules,
        lock_radar_log_path=req.lock_radar_log_path,
        assumptions=assumptions,
        include_update=req.include_update or enterprise_profile,
        include_rights=req.include_rights or enterprise_profile,
        include_lock_radar=req.include_lock_radar or enterprise_profile,
        include_extension_safety=req.include_extension_safety or enterprise_profile,
        include_killer_demo=False,
    )
    reports = _artifact_reports(bundle)
    report = build_killer_demo_path(
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
    )
    return report, bundle


def _build_report(req: KillerDemoRequest) -> dict[str, Any]:
    report, _bundle = _compose(req)
    return report


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode(
        "utf-8"
    )


def _role_packet_markdown(report: dict[str, Any], item: dict[str, Any]) -> str:
    packet = report.get("proof_packet") or {}
    handoff = packet.get("procurement_handoff") or {}
    recipient = str(item.get("recipient") or "stakeholder")
    send_files = [str(file) for file in item.get("send", []) if file]
    available_files = [
        str(file) for file in item.get("available_files", []) if file
    ] or send_files
    missing_files = [str(file) for file in item.get("missing_files", []) if file]
    route = str(item.get("route") or "/killer-demo")
    lines = [
        f"# Killer Demo Role Packet: {recipient}",
        "",
        f"Client: **{(report.get('client') or {}).get('name', 'Demo client')}**",
        f"Demo status: **{(report.get('decision') or {}).get('status', 'unknown')}** / score **{(report.get('decision') or {}).get('score', 0)}**",
        f"Primary route: `{route}`",
        f"Forwardable proof packet: **{bool(packet.get('ready_to_forward'))}**",
        "",
        "## Why This Stakeholder Gets It",
        "",
        str(
            item.get("why")
            or "Use these files to evaluate the proof without opening the whole archive."
        ),
        "",
        "## Available In This Archive",
        "",
    ]
    if available_files:
        lines.extend(f"- `{file}`" for file in available_files)
    else:
        lines.append("- `buyer-brief.md`")
        lines.append("- `rentgen-killer-demo-path.md`")
        lines.append("- `proof-packet.json`")
    if missing_files:
        lines.extend(["", "## Not Included In This Build", ""])
        lines.extend(f"- `{file}`" for file in missing_files)
    lines.extend(
        [
            "",
            "## What To Open First",
            "",
            "1. `buyer-brief.md` for the first-minute room map.",
            "2. This role packet for the stakeholder-specific route and files.",
            f"3. `{route}` in the portal when the buyer wants the live proof screen.",
            "",
            "## Verification",
            "",
            f"- Procurement handoff: **{handoff.get('status', 'unknown')}**",
            f"- Missing files: **{handoff.get('missing_files', 0)}**",
            f"- Blockers: **{handoff.get('blockers', 0)}**",
            f"- Verify this demo overlay with `killer-demo-manifest.json` and the archive with `{handoff.get('hash_header', KILLER_DEMO_ARCHIVE_HASH_HEADER)}`.",
        ]
    )
    return "\n".join(lines)


def _role_packets(report: dict[str, Any]) -> list[dict[str, str]]:
    packet = report.get("proof_packet") or {}
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in packet.get("handoff", []):
        recipient = str(item.get("recipient") or "stakeholder")
        filename = role_packet_filename(recipient)
        if filename in seen:
            continue
        seen.add(filename)
        entries.append(
            {
                "recipient": recipient,
                "route": str(item.get("route") or "/killer-demo"),
                "filename": filename,
                "content": _role_packet_markdown(report, item),
            }
        )
    return entries


def _open_first_killer_demo(
    report: dict[str, Any], bundle: dict[str, Any], role_packets: list[dict[str, str]]
) -> str:
    packet = report.get("proof_packet") or {}
    handoff = packet.get("procurement_handoff") or {}
    order = [
        "`MEETING_CLOSE_RECEIPT.md` for accepted roles, blockers and the next paid step.",
        "`POST_DEMO_ACTIVATION_HANDOFF.md` for paid start, Day 7 proof and Day 30 acceptance.",
        "`rentgen-killer-demo-path.md` for the full meeting script.",
        "`proof-packet.json` for machine-readable files, hashes and routes.",
        f"`killer-demo-manifest.json` for SHA-256 checks of the demo overlay files and `{KILLER_DEMO_MANIFEST_HASH_HEADER}`.",
        f"`{VERIFY_ARCHIVE_MD}` for the exact close-room ZIP verification checklist.",
        "`OPEN_FIRST.md` from the Evidence Bundle for procurement and role packet verification.",
        "`procurement-handoff.md` for buyers, security and procurement.",
    ]
    lines = [
        "# Open First - Killer Demo",
        "",
        f"Bundle: `{bundle.get('bundle_id', 'demo')}`",
        f"Client: **{(report.get('client') or {}).get('name', 'Demo client')}**",
        f"Demo status: **{(report.get('decision') or {}).get('status', 'unknown')}** / score **{(report.get('decision') or {}).get('score', 0)}**",
        f"Proof packet forwardable: **{bool(packet.get('ready_to_forward'))}**",
        "",
        "## Open Order",
        "",
    ]
    lines.extend(f"{index}. {item}" for index, item in enumerate(order, start=1))
    if role_packets:
        lines.extend(["", "## Role Packets", ""])
        for item in role_packets:
            lines.append(
                f"- **{item['recipient']}**: `{item['filename']}` (`{item['route']}`)"
            )
    lines.extend(
        [
            "",
            "## Procurement Readiness",
            "",
            f"- Handoff status: **{handoff.get('status', 'unknown')}**",
            f"- Missing files: **{handoff.get('missing_files', 0)}**",
            f"- Blockers: **{handoff.get('blockers', 0)}**",
            f"- Risk reviews: **{handoff.get('risk_review_items', 0)}**",
            f"- Verify archive hash with `{handoff.get('hash_header', KILLER_DEMO_ARCHIVE_HASH_HEADER)}` and demo overlay hashes with `killer-demo-manifest.json` plus `{KILLER_DEMO_MANIFEST_HASH_HEADER}`.",
        ]
    )
    return "\n".join(lines)


def _archive_readme(
    report: dict[str, Any], bundle: dict[str, Any], role_packets: list[dict[str, str]]
) -> str:
    packet = report.get("proof_packet") or {}
    handoff = packet.get("procurement_handoff") or {}
    role_line = (
        ", ".join(f"`{item['filename']}`" for item in role_packets)
        or "`ROLE_*.md` when role packets are available"
    )
    return "\n".join(
        [
            "# 1C Rentgen Killer Demo Archive",
            "",
            f"Bundle: `{bundle.get('bundle_id', 'demo')}`",
            f"Client: {(report.get('client') or {}).get('name', 'Demo client')}",
            f"Killer Demo status: `{(report.get('decision') or {}).get('status', 'unknown')}`",
            f"Forwardable: `{bool(packet.get('ready_to_forward'))}`",
            "",
            "Open order:",
            "",
            "1. `OPEN_FIRST_KILLER_DEMO.md`",
            "2. `MEETING_CLOSE_RECEIPT.md`",
            "3. `POST_DEMO_ACTIVATION_HANDOFF.md`",
            "4. `rentgen-killer-demo-path.md`",
            "5. `proof-packet.json`",
            "6. `killer-demo-manifest.json`",
            f"7. `{VERIFY_ARCHIVE_MD}`",
            "8. `OPEN_FIRST.md` from the Evidence Bundle",
            "9. `procurement-handoff.md`",
            f"10. Role packets: {role_line}",
            "",
            f"Procurement handoff: `{handoff.get('status', 'unknown')}`, missing `{handoff.get('missing_files', 0)}`, blockers `{handoff.get('blockers', 0)}`.",
            f"The archive is generated from local Rentgen evidence; verify source hashes with `manifest.json`, demo hashes with `killer-demo-manifest.json`, and response headers `{KILLER_DEMO_ARCHIVE_HASH_HEADER}` / `{KILLER_DEMO_MANIFEST_HASH_HEADER}`.",
        ]
    )


def _verify_killer_demo_archive_markdown(
    report: dict[str, Any], bundle: dict[str, Any], role_packets: list[dict[str, str]]
) -> str:
    packet = report.get("proof_packet") or {}
    handoff = packet.get("procurement_handoff") or {}
    role_line = (
        ", ".join(f"`{item['filename']}`" for item in role_packets) or "`ROLE_*.md`"
    )
    lines = [
        "# Verify Killer Demo Archive",
        "",
        f"Bundle: `{bundle.get('bundle_id', 'demo')}`",
        f"Client: **{(report.get('client') or {}).get('name', 'Demo client')}**",
        "",
        "## Record From Download Response",
        "",
        f"- Killer Demo ZIP hash header: `{KILLER_DEMO_ARCHIVE_HASH_HEADER}`",
        f"- Compatibility ZIP hash header: `X-Archive-Sha256`",
        f"- Evidence ZIP hash header: `X-Evidence-Archive-Sha256`",
        f"- Killer Demo manifest header: `{KILLER_DEMO_MANIFEST_HEADER}`",
        f"- Killer Demo manifest hash header: `{KILLER_DEMO_MANIFEST_HASH_HEADER}`",
        f"- Killer Demo manifest count header: `{KILLER_DEMO_MANIFEST_FILES_HEADER}`",
        "",
        "## Verify Files",
        "",
        "1. Open `OPEN_FIRST_KILLER_DEMO.md` for the close-room order.",
        "2. Open `killer-demo-manifest.json` and verify demo overlay files.",
        f"3. Record `{MEETING_CLOSE_RECEIPT_MD}` and `{POST_DEMO_ACTIVATION_MD}` in the procurement ticket.",
        "4. Verify Evidence Bundle source hashes with `manifest.json` and generated entries with `archive-manifest.json`.",
        f"5. Forward role packets only after the role packet hashes are covered by `killer-demo-manifest.json`: {role_line}.",
        "",
        "## Boundary",
        "",
        "- Killer Demo ZIP contains close-room overlays, receipt, activation handoff, proof packet and role packets.",
        "- Evidence Bundle files inside this ZIP remain source/procurement evidence; their generated-file verification is in `archive-manifest.json`.",
        f"- Procurement handoff status: **{handoff.get('status', 'unknown')}**; missing files: **{handoff.get('missing_files', 0)}**; blockers: **{handoff.get('blockers', 0)}**.",
    ]
    return "\n".join(lines)


def _sync_embedded_archive_manifest(
    source_manifest: dict[str, Any] | None, replacements: dict[str, bytes]
) -> bytes | None:
    if not source_manifest:
        return None
    updated = dict(source_manifest)
    files: list[dict[str, Any]] = []
    for entry in source_manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        item = dict(entry)
        filename = str(item.get("filename") or "")
        if filename in replacements:
            payload = replacements[filename]
            item["sha256"] = hashlib.sha256(payload).hexdigest()
            item["size_bytes"] = len(payload)
        files.append(item)
    updated["files"] = files
    updated["file_count"] = len(files)
    return _json_bytes(updated)


def _killer_demo_archive(
    report: dict[str, Any],
    bundle: dict[str, Any],
    *,
    evidence_archive: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_archive = evidence_archive or evidence_bundle_archive(bundle)
    role_packets = _role_packets(report)
    skipped = {
        "README-KILLER-DEMO.md",
        "OPEN_FIRST_KILLER_DEMO.md",
        "rentgen-killer-demo-path.md",
        "killer-demo.json",
        "proof-packet.json",
        "killer-demo-manifest.json",
        "archive-manifest.json",
        VERIFY_ARCHIVE_MD,
        MEETING_CLOSE_RECEIPT_MD,
        MEETING_CLOSE_RECEIPT_JSON,
        POST_DEMO_ACTIVATION_MD,
        POST_DEMO_ACTIVATION_JSON,
    }
    skipped.update(item["filename"] for item in role_packets)
    buffer = BytesIO()
    written: set[str] = set()
    with zipfile.ZipFile(BytesIO(evidence_archive["bytes"]), mode="r") as source:
        source_archive_manifest: dict[str, Any] | None = None
        if "archive-manifest.json" in source.namelist():
            source_archive_manifest = json.loads(
                source.read("archive-manifest.json").decode("utf-8")
            )
            if not isinstance(source_archive_manifest, dict):
                source_archive_manifest = None
        with zipfile.ZipFile(
            buffer, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for item in source.infolist():
                if (
                    item.is_dir()
                    or item.filename in skipped
                    or item.filename in written
                ):
                    continue
                archive.writestr(item.filename, source.read(item.filename))
                written.add(item.filename)
            additions = {
                "README-KILLER-DEMO.md": _archive_readme(
                    report, bundle, role_packets
                ).encode("utf-8"),
                "OPEN_FIRST_KILLER_DEMO.md": _open_first_killer_demo(
                    report, bundle, role_packets
                ).encode("utf-8"),
                VERIFY_ARCHIVE_MD: _verify_killer_demo_archive_markdown(
                    report, bundle, role_packets
                ).encode("utf-8"),
                str(report.get("download_name") or "rentgen-killer-demo-path.md"): str(
                    report.get("markdown") or ""
                ).encode("utf-8"),
                "killer-demo.json": _json_bytes(report),
                "proof-packet.json": _json_bytes(report.get("proof_packet") or {}),
            }
            receipt = report.get("meeting_close_receipt") or {}
            if receipt:
                additions[
                    str(receipt.get("filename") or MEETING_CLOSE_RECEIPT_MD)
                ] = meeting_close_receipt_markdown(receipt).encode("utf-8")
                additions[
                    str(receipt.get("json_filename") or MEETING_CLOSE_RECEIPT_JSON)
                ] = _json_bytes(receipt)
            activation = report.get("post_demo_activation_handoff") or {}
            if activation:
                additions[
                    str(activation.get("filename") or POST_DEMO_ACTIVATION_MD)
                ] = post_demo_activation_handoff_markdown(activation).encode("utf-8")
                additions[
                    str(activation.get("json_filename") or POST_DEMO_ACTIVATION_JSON)
                ] = _json_bytes(activation)
            for item in role_packets:
                additions[item["filename"]] = item["content"].encode("utf-8")
            synced_archive_manifest = _sync_embedded_archive_manifest(
                source_archive_manifest, additions
            )
            if synced_archive_manifest is not None:
                additions["archive-manifest.json"] = synced_archive_manifest
            demo_manifest = {
                "bundle_id": str(bundle.get("bundle_id") or ""),
                "client_name": str((report.get("client") or {}).get("name") or ""),
                "evidence_archive_sha256": str(evidence_archive.get("sha256") or ""),
                "close_receipt": {
                    "filename": str(receipt.get("filename") or "") if receipt else "",
                    "json_filename": str(receipt.get("json_filename") or "")
                    if receipt
                    else "",
                    "status": str(receipt.get("status") or "") if receipt else "",
                    "ready_to_send": bool(receipt.get("ready_to_send"))
                    if receipt
                    else False,
                    "ready_to_ask": bool(receipt.get("ready_to_ask"))
                    if receipt
                    else False,
                },
                "activation_handoff": {
                    "filename": str(activation.get("filename") or "")
                    if activation
                    else "",
                    "json_filename": str(activation.get("json_filename") or "")
                    if activation
                    else "",
                    "status": str(activation.get("status") or "") if activation else "",
                    "ready_to_start": bool(activation.get("ready_to_start"))
                    if activation
                    else False,
                    "route": str(activation.get("route") or "") if activation else "",
                },
                "role_packets": [
                    {
                        "recipient": item["recipient"],
                        "filename": item["filename"],
                        "route": item["route"],
                    }
                    for item in role_packets
                ],
                "files": [
                    {
                        "filename": filename,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content),
                    }
                    for filename, content in additions.items()
                ],
            }
            demo_manifest_bytes = _json_bytes(demo_manifest)
            additions["killer-demo-manifest.json"] = demo_manifest_bytes
            for filename, content in additions.items():
                archive.writestr(filename, content)
                written.add(filename)
    payload = buffer.getvalue()
    bundle_id = str(bundle.get("bundle_id") or "rentgen")
    return {
        "filename": f"{bundle_id}-killer-demo-archive.zip",
        "media_type": "application/zip",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "files": len(written),
        "bytes": payload,
        "evidence_sha256": str(evidence_archive.get("sha256") or ""),
        "killer_demo_manifest_file": "killer-demo-manifest.json",
        "killer_demo_manifest_sha256": hashlib.sha256(demo_manifest_bytes).hexdigest(),
        "killer_demo_manifest_files": len(demo_manifest["files"]),
    }


def _finding_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    high = sum(1 for item in findings if item.get("severity") == "high")
    medium = sum(1 for item in findings if item.get("severity") == "medium")
    low = sum(1 for item in findings if item.get("severity") == "low")
    return {"findings": len(findings), "high": high, "medium": medium, "low": low}


def verify_killer_demo_archive_payload(
    payload: bytes, *, filename: str = ""
) -> dict[str, Any]:
    """Verify a Killer Demo ZIP archive without extracting it."""

    findings: list[dict[str, Any]] = []
    checked = 0
    required = {
        "README-KILLER-DEMO.md",
        "OPEN_FIRST_KILLER_DEMO.md",
        VERIFY_ARCHIVE_MD,
        "killer-demo-manifest.json",
        "killer-demo.json",
        "proof-packet.json",
        MEETING_CLOSE_RECEIPT_MD,
        MEETING_CLOSE_RECEIPT_JSON,
        POST_DEMO_ACTIVATION_MD,
        POST_DEMO_ACTIVATION_JSON,
    }
    archive_sha256 = hashlib.sha256(payload).hexdigest()
    evidence_verify: dict[str, Any] | None = None

    try:
        with zipfile.ZipFile(BytesIO(payload), mode="r") as archive:
            names = {item.filename for item in archive.infolist() if not item.is_dir()}
            for required_file in sorted(required - names):
                findings.append(
                    {
                        "severity": "high",
                        "code": "required-file-missing",
                        "filename": required_file,
                        "message": f"Killer Demo archive is missing required close-room file {required_file}.",
                    }
                )
            if "killer-demo-manifest.json" not in names:
                findings.append(
                    {
                        "severity": "high",
                        "code": "killer-demo-manifest-missing",
                        "message": "killer-demo-manifest.json is required to verify close-room overlay files.",
                    }
                )
                demo_manifest: dict[str, Any] = {}
            else:
                demo_manifest = json.loads(
                    archive.read("killer-demo-manifest.json").decode("utf-8")
                )
                if not isinstance(demo_manifest, dict):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-manifest-invalid",
                            "message": "killer-demo-manifest.json is not an object.",
                        }
                    )
                    demo_manifest = {}

            for entry in demo_manifest.get("files", []):
                if not isinstance(entry, dict):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-manifest-entry-invalid",
                        }
                    )
                    continue
                entry_name = str(entry.get("filename") or "")
                if not entry_name:
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-manifest-entry-without-filename",
                        }
                    )
                    continue
                if entry_name not in names:
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-entry-missing",
                            "filename": entry_name,
                        }
                    )
                    continue
                content = archive.read(entry_name)
                checked += 1
                actual_sha = hashlib.sha256(content).hexdigest()
                if actual_sha != entry.get("sha256"):
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-entry-hash-mismatch",
                            "filename": entry_name,
                            "expected": entry.get("sha256"),
                            "actual": actual_sha,
                        }
                    )
                expected_bytes = entry.get("bytes")
                if isinstance(expected_bytes, int) and len(content) != expected_bytes:
                    findings.append(
                        {
                            "severity": "high",
                            "code": "killer-demo-entry-size-mismatch",
                            "filename": entry_name,
                            "expected": expected_bytes,
                            "actual": len(content),
                        }
                    )

            role_packet_names = {
                str(item.get("filename") or "")
                for item in demo_manifest.get("role_packets", [])
                if isinstance(item, dict)
            }
            for filename_in_manifest in sorted(
                name for name in role_packet_names if name and name not in names
            ):
                findings.append(
                    {
                        "severity": "high",
                        "code": "role-packet-missing",
                        "filename": filename_in_manifest,
                    }
                )

        if "archive-manifest.json" in names:
            evidence_verify = verify_evidence_bundle_archive_payload(
                payload, filename=filename
            )
            if evidence_verify["status"] == "fail":
                findings.append(
                    {
                        "severity": "high",
                        "code": "embedded-evidence-archive-manifest-failed",
                        "message": "Embedded Evidence Bundle archive-manifest.json verification failed.",
                    }
                )
            elif evidence_verify["status"] == "warn":
                findings.append(
                    {
                        "severity": "medium",
                        "code": "embedded-evidence-archive-manifest-warning",
                        "message": "Embedded Evidence Bundle archive-manifest.json verification has warnings.",
                    }
                )
        else:
            findings.append(
                {
                    "severity": "medium",
                    "code": "embedded-evidence-archive-manifest-missing",
                    "message": "archive-manifest.json is absent; source Evidence files cannot be fully verified from this ZIP.",
                }
            )
    except zipfile.BadZipFile:
        findings.append(
            {
                "severity": "high",
                "code": "zip-invalid",
                "message": "Payload is not a readable ZIP archive.",
            }
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        findings.append(
            {"severity": "high", "code": "archive-json-invalid", "message": str(exc)}
        )

    summary = _finding_summary(findings)
    status = "fail" if summary["high"] else ("warn" if findings else "pass")
    result = {
        "status": status,
        "archive_type": "killer-demo",
        "filename": filename,
        "archive_sha256": archive_sha256,
        "checked_files": checked,
        "required_files": sorted(required),
        "embedded_evidence_verify": evidence_verify,
        "summary": summary,
        "findings": findings,
    }
    return attach_archive_verification_receipt(result)


@router.post("/build")
def build(req: KillerDemoRequest) -> dict[str, Any]:
    """Build the buyer-ready killer demo route with proof moments and close scripts."""

    return _build_report(req)


@router.post("/archive")
def archive(req: KillerDemoRequest) -> Response:
    """Return one ZIP with Evidence Bundle files plus the current Killer Demo proof packet."""

    report, bundle = _compose(req)
    archive_payload = _killer_demo_archive(report, bundle)
    return Response(
        content=archive_payload["bytes"],
        media_type=archive_payload["media_type"],
        headers={
            "Content-Disposition": f"attachment; filename={archive_payload['filename']}",
            "X-Archive-Sha256": archive_payload["sha256"],
            KILLER_DEMO_ARCHIVE_HASH_HEADER: archive_payload["sha256"],
            "X-Archive-Files": str(archive_payload["files"]),
            "X-Evidence-Archive-Sha256": archive_payload["evidence_sha256"],
            KILLER_DEMO_MANIFEST_HEADER: archive_payload["killer_demo_manifest_file"],
            KILLER_DEMO_MANIFEST_HASH_HEADER: archive_payload[
                "killer_demo_manifest_sha256"
            ],
            KILLER_DEMO_MANIFEST_FILES_HEADER: str(
                archive_payload["killer_demo_manifest_files"]
            ),
        },
    )


@router.post("/archive/verify")
def verify_archive(req: KillerDemoRequest) -> dict[str, Any]:
    """Build and verify the Killer Demo ZIP without extracting it."""

    report, bundle = _compose(req)
    archive_payload = _killer_demo_archive(report, bundle)
    result = verify_killer_demo_archive_payload(
        archive_payload["bytes"],
        filename=str(archive_payload.get("filename") or ""),
    )
    result["expected_headers"] = {
        "X-Archive-Sha256": archive_payload["sha256"],
        KILLER_DEMO_ARCHIVE_HASH_HEADER: archive_payload["sha256"],
        "X-Archive-Files": str(archive_payload["files"]),
        "X-Evidence-Archive-Sha256": archive_payload["evidence_sha256"],
        KILLER_DEMO_MANIFEST_HEADER: archive_payload["killer_demo_manifest_file"],
        KILLER_DEMO_MANIFEST_HASH_HEADER: archive_payload[
            "killer_demo_manifest_sha256"
        ],
        KILLER_DEMO_MANIFEST_FILES_HEADER: str(
            archive_payload["killer_demo_manifest_files"]
        ),
    }
    attach_archive_verification_receipt(
        result, expected_headers=result["expected_headers"]
    )
    return result


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
        "score": pulse["score"],
        "stages": 6,
        "demo_modes": 4,
        "close_ready": pulse["purchase_status"] == "ready",
        "checkout_gates": pulse["evidence"]["governance_gates"],
        "purchase_status": pulse["purchase_status"],
        "three_year_ai_rent": pulse["commercial"]["three_year_ai_rent"],
        "source": pulse["source"],
    }
