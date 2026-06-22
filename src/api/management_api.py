"""Management cockpit API for executive 1C delivery control."""

from __future__ import annotations

import hashlib
import json
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.api.copilot_coverage_api import COVERAGE_ITEMS
from src.services.rentgen.buyer_brief import build_buyer_brief
from src.services.rentgen.buyer_pulse import build_buyer_pulse
from src.services.rentgen.demo_story import build_demo_story, build_role_report
from src.services.rentgen.executive_dashboard import build_executive_dashboard
from src.services.rentgen.intake_wizard import build_intake_plan

router = APIRouter(prefix="/api/v1/management", tags=["Management"])

BUYER_ROOM_PACKET_FILENAME = "rentgen-buyer-room-packet.zip"
BUYER_ROOM_PACKET_OPEN_FIRST = "OPEN_FIRST_BUYER_ROOM.md"
BUYER_ROOM_PACKET_SHA_HEADER = "X-Buyer-Room-Packet-Sha256"
BUYER_ROOM_PACKET_FILES_HEADER = "X-Buyer-Room-Packet-Files"
BUYER_ROOM_PACKET_OPEN_FIRST_HEADER = "X-Buyer-Room-Packet-Open-First"

BUYER_ROOM_PACKET_REQUIRED_FILES = {
    BUYER_ROOM_PACKET_OPEN_FIRST,
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
}


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True, default=str
    ).encode("utf-8")


def _markdown_bytes(markdown: str) -> bytes:
    return markdown.rstrip().encode("utf-8") + b"\n"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _buyer_pulse_markdown(pulse: dict[str, Any]) -> str:
    commercial = pulse.get("commercial") or {}
    executive = pulse.get("executive") or {}
    lines = [
        "# Buyer Pulse",
        "",
        f"- Status: {_text(pulse.get('status'), 'unknown')}",
        f"- Purchase status: {_text(pulse.get('purchase_status'), 'unknown')}",
        f"- Score: {_text(pulse.get('score'), 'n/a')}",
        f"- Source: {_text(pulse.get('source'), 'management-fast-pulse')}",
        "",
        "## Commercial Anchor",
        "",
        f"- Monthly AI rent: {_text(commercial.get('monthly_ai_rent'), 'n/a')}",
        f"- Three-year AI rent: {_text(commercial.get('three_year_ai_rent'), 'n/a')}",
        f"- Local license anchor: {_text(commercial.get('local_license_anchor'), 'n/a')}",
        f"- Buyer line: {_text(commercial.get('buyer_line'), 'n/a')}",
        "",
        "## Executive Signals",
        "",
        f"- Red areas: {_text(executive.get('red_areas'), '0')}",
        f"- Review queue: {_text(executive.get('review_queue'), '0')}",
        f"- High hotspots: {_text(executive.get('high_hotspots'), '0')}",
        f"- Headline: {_text(executive.get('headline'), 'n/a')}",
    ]
    return "\n".join(lines)


def _buyer_room_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Buyer Room Plan",
        "",
        f"- Mode: {_text(plan.get('mode'), 'guided-proof')}",
        f"- Role: {_text(plan.get('role'), 'all')}",
        f"- Status: {_text(plan.get('status'), 'watch')}",
        f"- Route: {_text(plan.get('route'), '/')}",
        f"- Proof file: {_text(plan.get('proof_file'), 'buyer-brief.md')}",
        "",
        f"## {_text(plan.get('title'), 'Open buyer route')}",
        "",
        _text(
            plan.get("start_with"),
            "Open one buyer route before deep workbench navigation.",
        ),
        "",
        f"Close question: {_text(plan.get('close_question'), 'What is the next paid step?')}",
        "",
        "## Sequence",
        "",
    ]
    for item in plan.get("sequence") or []:
        lines.append(
            f"{_text(item.get('step'), '1')}. {_text(item.get('label'), 'Step')} "
            f"({_text(item.get('route'), '/')}) - {_text(item.get('line'), '')}"
        )
    lines.extend(["", "## Send Files", ""])
    for filename in plan.get("send_files") or []:
        lines.append(f"- `{filename}`")
    lines.extend(["", "## Why", "", _text(plan.get("why"), "")])
    return "\n".join(lines)


def _procurement_handoff_markdown(handoff: dict[str, Any]) -> str:
    lines = [
        "# Procurement Handoff",
        "",
        f"- Status: {_text(handoff.get('status'), 'watch')}",
        f"- Title: {_text(handoff.get('title'), 'Procurement-ready handoff')}",
        f"- Owner line: {_text(handoff.get('owner_line'), '')}",
        f"- Acceptance: {_text(handoff.get('acceptance'), '')}",
        "",
        "## Open Order",
        "",
    ]
    for item in handoff.get("open_order") or []:
        lines.append(
            f"### {_text(item.get('step'), '?')}. {_text(item.get('label'), 'Artifact')}"
        )
        lines.append("")
        lines.append(f"- Route: {_text(item.get('route'), '/')}")
        if item.get("endpoint"):
            lines.append(f"- Endpoint: {_text(item.get('endpoint'))}")
        lines.append(f"- File: `{_text(item.get('file'), '')}`")
        if item.get("hash_header"):
            lines.append(f"- Hash header: `{_text(item.get('hash_header'))}`")
        lines.append(f"- Check: {_text(item.get('check'), '')}")
        lines.append("")
    lines.extend(["## Attachments", ""])
    for item in handoff.get("attachments") or []:
        lines.append(
            f"- `{_text(item.get('file'), '')}` - {_text(item.get('why'), '')}"
        )
        if item.get("endpoint"):
            lines.append(f"  Endpoint: {_text(item.get('endpoint'))}")
        if item.get("hash_header"):
            lines.append(f"  Hash header: `{_text(item.get('hash_header'))}`")
    return "\n".join(lines)


def _purchase_path_markdown(path: dict[str, Any]) -> str:
    lines = [
        "# Purchase Path",
        "",
        f"- Status: {_text(path.get('status'), 'watch')}",
        f"- Primary route: {_text(path.get('primary_route'), '/killer-demo')}",
        f"- Headline: {_text(path.get('headline'), '')}",
        f"- Buyer line: {_text(path.get('buyer_line'), '')}",
        "",
        "## Steps",
        "",
    ]
    for item in path.get("steps") or []:
        lines.append(
            f"{_text(item.get('step'), '?')}. {_text(item.get('label'), 'Step')} "
            f"({_text(item.get('route'), '/')}) - `{_text(item.get('file'), '')}`"
        )
        if item.get("line"):
            lines.append(f"   {_text(item.get('line'))}")
    lines.extend(["", "## Procurement Artifacts", ""])
    for key in [
        "buyer_room_packet_artifact",
        "close_artifact",
        "activation_artifact",
        "archive_receipt_artifact",
        "verification_packet_artifact",
    ]:
        artifact = path.get(key) or {}
        if artifact:
            lines.append(
                f"- {_text(artifact.get('title'), key)}: `{_text(artifact.get('file'), '')}`"
            )
            if artifact.get("endpoint"):
                lines.append(f"  Endpoint: {_text(artifact.get('endpoint'))}")
            if artifact.get("hash_header"):
                lines.append(f"  Hash header: `{_text(artifact.get('hash_header'))}`")
    lines.extend(["", "## Send Files", ""])
    for filename in path.get("send_files") or []:
        lines.append(f"- `{filename}`")
    return "\n".join(lines)


def _open_first_path_markdown(path: list[dict[str, Any]]) -> str:
    lines = [
        "# Open-First Path",
        "",
        "Four buyer-safe actions before the full workbench: orient, prove, close and verify.",
        "",
    ]
    for item in path:
        lines.append(
            f"## {_text(item.get('step'), '?')}. {_text(item.get('label'), 'Step')}"
        )
        lines.append("")
        lines.append(f"- Stage: {_text(item.get('stage'), '')}")
        lines.append(f"- Title: {_text(item.get('title'), '')}")
        lines.append(f"- Route: {_text(item.get('route'), '/')}")
        lines.append(f"- File: `{_text(item.get('file'), '')}`")
        lines.append(f"- Status: {_text(item.get('status'), 'watch')}")
        lines.append(f"- Source: {_text(item.get('source'), '')}")
        lines.append(f"- Line: {_text(item.get('line'), '')}")
        lines.append("")
    return "\n".join(lines)


def _buyer_brief_markdown(brief: dict[str, Any]) -> str:
    primary = brief.get("primary_motion") or {}
    commercial = brief.get("commercial") or {}
    summary = brief.get("summary") or {}
    lines = [
        "# Buyer Brief",
        "",
        f"- Status: {_text(brief.get('status'), 'watch')}",
        f"- Purchase status: {_text(brief.get('purchase_status'), 'watch')}",
        f"- Score: {_text(brief.get('score'), 'n/a')}",
        f"- Room line: {_text(brief.get('room_line'), '')}",
        "",
        "## Primary Motion",
        "",
        f"- Label: {_text(primary.get('label'), 'Open buyer route')}",
        f"- Route: {_text(primary.get('route'), '/launch-room')}",
        f"- Ask: {_text(primary.get('ask'), '')}",
        f"- Reason: {_text(primary.get('reason'), '')}",
        "",
        "## Commercial",
        "",
        f"- Three-year AI rent: {_text(commercial.get('three_year_ai_rent'), 'n/a')}",
        f"- Local license anchor: {_text(commercial.get('local_license_anchor'), 'n/a')}",
        "",
        "## Summary",
        "",
        f"- Roles: {_text(summary.get('roles'), '0')}",
        f"- Proof items: {_text(summary.get('proof_items'), '0')}",
        f"- Purchase path steps: {_text(summary.get('purchase_path_steps'), '0')}",
        f"- Procurement handoff steps: {_text(summary.get('procurement_handoff_steps'), '0')}",
        "",
        "## Open-First Path",
        "",
    ]
    for item in brief.get("open_first_path") or []:
        lines.append(
            f"{_text(item.get('step'), '?')}. {_text(item.get('label'), 'Step')} "
            f"({_text(item.get('route'), '/')}) - `{_text(item.get('file'), '')}` - {_text(item.get('line'), '')}"
        )
    lines.extend(
        [
            "",
            "## Role Cards",
            "",
        ]
    )
    for item in brief.get("role_cards") or []:
        lines.append(
            f"- {_text(item.get('title'), item.get('role'))}: {_text(item.get('spark'), '')} "
            f"Route: {_text(item.get('route'), '/')}; file: `{_text(item.get('proof_file'), '')}`"
        )
    lines.extend(["", "## Proof Readiness", ""])
    for item in brief.get("proof_readiness") or []:
        lines.append(
            f"- {_text(item.get('title'), item.get('id'))}: {_text(item.get('signal'), '')} "
            f"File: `{_text(item.get('file'), '')}`"
        )
    lines.extend(["", "## Meeting Flow", ""])
    for item in brief.get("meeting_flow") or []:
        lines.append(
            f"{_text(item.get('step'), '?')}. {_text(item.get('label'), 'Step')} "
            f"({_text(item.get('route'), '/')}) - {_text(item.get('line'), '')}"
        )
    return "\n".join(lines)


def _open_first_buyer_room_markdown(brief: dict[str, Any]) -> str:
    plan = brief.get("buyer_room_plan") or {}
    path = brief.get("purchase_path") or {}
    handoff = path.get("procurement_handoff") or {}
    lines = [
        "# Open First: Buyer Room Packet",
        "",
        "This ZIP is the first-screen buyer room packet. Open it before sending the buyer into the full workbench.",
        "",
        "## Open Order",
        "",
        "1. `buyer-brief.md` - room orientation, primary motion and role sparks.",
        "2. `open-first-path.md` - four actions: orient, prove, close and verify.",
        "3. `buyer-room-plan.md` - who starts, which route opens first and the close question.",
        "4. `purchase-path.md` - start, prove, close, activate and realize sequence.",
        "5. `procurement-handoff.md` - exact order for ZIPs, receipts and hash headers.",
        "6. `hash-table.json` - SHA-256 table for this packet.",
        "",
        "## Start Now",
        "",
        f"- First route: {_text(plan.get('route'), path.get('primary_route') or '/launch-room')}",
        f"- First role: {_text(plan.get('role'), 'all')}",
        f"- Close question: {_text(plan.get('close_question'), '')}",
        f"- Acceptance: {_text(handoff.get('acceptance'), '')}",
        "",
        "## Included Files",
        "",
        "- `buyer-brief.json` / `buyer-brief.md`",
        "- `buyer-pulse.json` / `buyer-pulse.md`",
        "- `open-first-path.json` / `open-first-path.md`",
        "- `buyer-room-plan.json` / `buyer-room-plan.md`",
        "- `purchase-path.json` / `purchase-path.md`",
        "- `procurement-handoff.json` / `procurement-handoff.md`",
        "- `hash-table.json`",
    ]
    return "\n".join(lines)


def _buyer_room_packet_archive(brief: dict[str, Any]) -> tuple[bytes, list[str]]:
    pulse = brief.get("pulse") or {}
    open_first_path = list(brief.get("open_first_path") or [])
    plan = brief.get("buyer_room_plan") or {}
    path = brief.get("purchase_path") or {}
    handoff = path.get("procurement_handoff") or {}
    files: list[tuple[str, bytes]] = [
        (
            BUYER_ROOM_PACKET_OPEN_FIRST,
            _markdown_bytes(_open_first_buyer_room_markdown(brief)),
        ),
        ("buyer-brief.json", _json_bytes(brief)),
        ("buyer-brief.md", _markdown_bytes(_buyer_brief_markdown(brief))),
        ("buyer-pulse.json", _json_bytes(pulse)),
        ("buyer-pulse.md", _markdown_bytes(_buyer_pulse_markdown(pulse))),
        ("open-first-path.json", _json_bytes(open_first_path)),
        (
            "open-first-path.md",
            _markdown_bytes(_open_first_path_markdown(open_first_path)),
        ),
        ("buyer-room-plan.json", _json_bytes(plan)),
        ("buyer-room-plan.md", _markdown_bytes(_buyer_room_plan_markdown(plan))),
        ("purchase-path.json", _json_bytes(path)),
        ("purchase-path.md", _markdown_bytes(_purchase_path_markdown(path))),
        ("procurement-handoff.json", _json_bytes(handoff)),
        (
            "procurement-handoff.md",
            _markdown_bytes(_procurement_handoff_markdown(handoff)),
        ),
    ]
    hash_entries = [
        {"file": filename, "sha256": _sha256_bytes(content), "bytes": len(content)}
        for filename, content in files
    ]
    files.append(
        (
            "hash-table.json",
            _json_bytes(
                {
                    "algorithm": "sha256",
                    "archive_files": len(files) + 1,
                    "hashed_files": len(hash_entries),
                    "open_first": BUYER_ROOM_PACKET_OPEN_FIRST,
                    "note": "hash-table.json is excluded from its own table.",
                    "files": hash_entries,
                }
            ),
        )
    )

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for filename, content in files:
            archive.writestr(filename, content)
    return buffer.getvalue(), [filename for filename, _ in files]


def _verify_finding_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "findings": len(findings),
        "high": len([item for item in findings if item.get("severity") == "high"]),
        "medium": len([item for item in findings if item.get("severity") == "medium"]),
        "low": len([item for item in findings if item.get("severity") == "low"]),
    }


def _verify_buyer_room_packet_payload(
    content: bytes, *, filename: str = BUYER_ROOM_PACKET_FILENAME
) -> dict[str, Any]:
    archive_sha256 = _sha256_bytes(content)
    findings: list[dict[str, Any]] = []
    names: set[str] = set()
    checked_files = 0
    hash_table_status = "missing"
    open_first_status = "missing"

    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())
            checked_files = len(names)
            missing = sorted(BUYER_ROOM_PACKET_REQUIRED_FILES - names)
            if missing:
                findings.append(
                    {
                        "severity": "high",
                        "code": "required-files-missing",
                        "message": "Buyer Room Packet ZIP is missing required files.",
                        "files": missing,
                    }
                )
            extra = sorted(names - BUYER_ROOM_PACKET_REQUIRED_FILES)
            if extra:
                findings.append(
                    {
                        "severity": "low",
                        "code": "unexpected-files",
                        "message": "Buyer Room Packet ZIP contains files outside the current contract.",
                        "files": extra,
                    }
                )

            if BUYER_ROOM_PACKET_OPEN_FIRST in names:
                open_first = archive.read(BUYER_ROOM_PACKET_OPEN_FIRST).decode("utf-8")
                if (
                    "Buyer Room Packet" in open_first
                    and "hash-table.json" in open_first
                    and "open-first-path.md" in open_first
                ):
                    open_first_status = "pass"
                else:
                    open_first_status = "warn"
                    findings.append(
                        {
                            "severity": "medium",
                            "code": "open-first-incomplete",
                            "message": "OPEN_FIRST_BUYER_ROOM.md does not describe the packet and hash table.",
                        }
                    )

            if "hash-table.json" in names:
                hash_table = json.loads(archive.read("hash-table.json").decode("utf-8"))
                entries = list(hash_table.get("files") or [])
                expected_files = {name for name in names if name != "hash-table.json"}
                table_files = {str(item.get("file") or "") for item in entries}
                missing_from_table = sorted(expected_files - table_files)
                if missing_from_table:
                    findings.append(
                        {
                            "severity": "high",
                            "code": "hash-table-missing-files",
                            "message": "hash-table.json does not cover all packet files.",
                            "files": missing_from_table,
                        }
                    )
                bad_hashes: list[str] = []
                for item in entries:
                    entry_file = str(item.get("file") or "")
                    if entry_file not in names:
                        continue
                    if _sha256_bytes(archive.read(entry_file)) != str(
                        item.get("sha256") or ""
                    ):
                        bad_hashes.append(entry_file)
                if bad_hashes:
                    findings.append(
                        {
                            "severity": "high",
                            "code": "hash-table-mismatch",
                            "message": "One or more packet file hashes do not match hash-table.json.",
                            "files": bad_hashes,
                        }
                    )
                if not missing_from_table and not bad_hashes:
                    hash_table_status = "pass"
                else:
                    hash_table_status = "fail"
    except BadZipFile:
        findings.append(
            {
                "severity": "high",
                "code": "zip-invalid",
                "message": "Payload is not a readable ZIP archive.",
            }
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        findings.append(
            {"severity": "high", "code": "packet-json-invalid", "message": str(exc)}
        )

    summary = _verify_finding_summary(findings)
    status = "fail" if summary["high"] else "warn" if findings else "pass"
    return {
        "status": status,
        "archive_type": "buyer-room-packet",
        "filename": filename,
        "archive_sha256": archive_sha256,
        "checked_files": checked_files,
        "required_files": sorted(BUYER_ROOM_PACKET_REQUIRED_FILES),
        "present_files": sorted(names),
        "open_first_file": BUYER_ROOM_PACKET_OPEN_FIRST,
        "open_first_status": open_first_status,
        "hash_table_status": hash_table_status,
        "expected_headers": {
            BUYER_ROOM_PACKET_SHA_HEADER: archive_sha256,
            BUYER_ROOM_PACKET_FILES_HEADER: str(checked_files),
            BUYER_ROOM_PACKET_OPEN_FIRST_HEADER: BUYER_ROOM_PACKET_OPEN_FIRST,
        },
        "summary": summary,
        "findings": findings,
    }


class IntakePlanRequest(BaseModel):
    source_path: str | None = Field(default=None, max_length=2000)
    source_type: str = Field(default="auto", pattern="^(auto|edt|git|xml|dt|cf|live)$")


@router.get("/executive")
def executive_dashboard(
    governance_limit: int = Query(40, ge=1, le=200),
    hotspot_limit: int = Query(12, ge=1, le=50),
    save_snapshot: bool = Query(False),
) -> dict[str, Any]:
    """Return the internal executive cockpit for managers and delivery leads."""

    return build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=save_snapshot,
    )


@router.get("/demo")
def demo_story(
    governance_limit: int = Query(40, ge=1, le=200),
    hotspot_limit: int = Query(12, ge=1, le=50),
) -> dict[str, Any]:
    """Return the complete role-oriented demo story with exportable reports."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    return build_demo_story(executive)


@router.get("/buyer-pulse")
def buyer_pulse(
    governance_limit: int = Query(10, ge=1, le=80),
    hotspot_limit: int = Query(5, ge=1, le=30),
    monthly_ai_subscription_cost: int = Query(120_000, ge=0, le=50_000_000),
) -> dict[str, Any]:
    """Return a fast first-screen buyer pulse without building deep deal artifacts."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    return build_buyer_pulse(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai_subscription_cost,
    )


@router.get("/buyer-brief")
def buyer_brief(
    governance_limit: int = Query(10, ge=1, le=80),
    hotspot_limit: int = Query(5, ge=1, le=30),
    monthly_ai_subscription_cost: int = Query(120_000, ge=0, le=50_000_000),
) -> dict[str, Any]:
    """Return a first-minute buyer brief without building deep deal artifacts."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    return build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai_subscription_cost,
    )


@router.get("/buyer-room-packet")
def buyer_room_packet(
    governance_limit: int = Query(10, ge=1, le=80),
    hotspot_limit: int = Query(5, ge=1, le=30),
    monthly_ai_subscription_cost: int = Query(120_000, ge=0, le=50_000_000),
) -> Response:
    """Return the first-screen buyer room ZIP without building deep deal artifacts."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai_subscription_cost,
    )
    content, filenames = _buyer_room_packet_archive(brief)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{BUYER_ROOM_PACKET_FILENAME}"',
            BUYER_ROOM_PACKET_SHA_HEADER: _sha256_bytes(content),
            BUYER_ROOM_PACKET_FILES_HEADER: str(len(filenames)),
            BUYER_ROOM_PACKET_OPEN_FIRST_HEADER: BUYER_ROOM_PACKET_OPEN_FIRST,
        },
    )


@router.get("/buyer-room-packet/verify")
def verify_buyer_room_packet(
    governance_limit: int = Query(10, ge=1, le=80),
    hotspot_limit: int = Query(5, ge=1, le=30),
    monthly_ai_subscription_cost: int = Query(120_000, ge=0, le=50_000_000),
) -> dict[str, Any]:
    """Build and verify the first-screen Buyer Room Packet ZIP contract."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    brief = build_buyer_brief(
        executive=executive,
        monthly_ai_subscription_cost=monthly_ai_subscription_cost,
    )
    content, _filenames = _buyer_room_packet_archive(brief)
    return _verify_buyer_room_packet_payload(
        content, filename=BUYER_ROOM_PACKET_FILENAME
    )


@router.get("/role-report/{role}")
def role_report(
    role: str,
    governance_limit: int = Query(40, ge=1, le=200),
    hotspot_limit: int = Query(12, ge=1, le=50),
) -> dict[str, Any]:
    """Return one role report: developer, architect, director, qa, ops or vendor."""

    executive = build_executive_dashboard(
        store_or_none(),
        coverage_items=COVERAGE_ITEMS,
        governance_limit=governance_limit,
        hotspot_limit=hotspot_limit,
        save_snapshot=False,
    )
    return build_role_report(role, executive)


@router.post("/intake/plan")
def intake_plan(req: IntakePlanRequest) -> dict[str, Any]:
    """Pre-flight an EDT/Git/XML source and return coverage/caveats before import."""

    return build_intake_plan(source_path=req.source_path, source_type=req.source_type)


@router.get("/health")
def health() -> dict[str, Any]:
    store = store_or_none()
    return {
        "status": "ok" if store is not None else "store_not_built",
        "store": store is not None,
    }
