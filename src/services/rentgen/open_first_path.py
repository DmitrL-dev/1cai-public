"""Shared open-first buyer path helpers."""

from __future__ import annotations

from typing import Any

from src.services.rentgen.buyer_pulse import ARCHIVE_VERIFICATION_PACKET_ZIP

OPEN_FIRST_PATH_FILE = "open-first-path.md"


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _first(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[0] if items else {}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _fallback_path(
    *,
    buyer_room_plan: dict[str, Any],
    proof_readiness: list[dict[str, Any]],
    purchase_path: dict[str, Any],
    primary: dict[str, Any],
    meeting_flow: list[dict[str, Any]],
    source: str,
    orient_title: str,
    orient_route: str,
    orient_line: str,
    orient_file: str,
    orient_status: str,
    prove_title: str,
    prove_route: str,
    prove_line: str,
    prove_file: str,
    prove_status: str,
    close_label: str,
    close_title: str,
    close_route: str,
    close_line: str,
    close_file: str,
    close_status: str,
    verify_title: str,
    verify_route: str,
    verify_line: str,
    verify_file: str,
    verify_status: str,
) -> list[dict[str, Any]]:
    first_meeting = _first(meeting_flow)
    first_proof = _first(proof_readiness)
    close = _as_dict(purchase_path.get("close_artifact"))
    verification = _as_dict(purchase_path.get("verification_packet_artifact"))
    purchase_status = _text(
        purchase_path.get("status"), close_status or orient_status or "watch"
    )
    primary_route = _text(primary.get("route"), "")
    primary_ask = _text(primary.get("ask"), "")
    primary_status = _text(primary.get("status"), orient_status or purchase_status)

    has_buyer_plan = bool(buyer_room_plan)
    return [
        {
            "step": 1,
            "stage": "orient",
            "label": "Orient",
            "title": _text(
                buyer_room_plan.get("title"),
                _text(first_meeting.get("label"), orient_title),
            ),
            "route": _text(
                buyer_room_plan.get("route"),
                _text(first_meeting.get("route"), orient_route),
            ),
            "line": _text(
                buyer_room_plan.get("start_with"),
                _text(first_meeting.get("line"), orient_line),
            ),
            "file": _text(buyer_room_plan.get("proof_file"), orient_file),
            "status": _text(buyer_room_plan.get("status"), primary_status or "watch"),
            "source": "buyer_room_plan" if has_buyer_plan else source,
        },
        {
            "step": 2,
            "stage": "prove",
            "label": "Prove",
            "title": _text(first_proof.get("title"), prove_title),
            "route": _text(first_proof.get("route"), prove_route),
            "line": _text(first_proof.get("signal"), prove_line),
            "file": _text(first_proof.get("file"), prove_file),
            "status": _text(
                first_proof.get("status"), purchase_status or prove_status or "watch"
            ),
            "source": "proof_readiness" if has_buyer_plan else source,
        },
        {
            "step": 3,
            "stage": "close",
            "label": close_label,
            "title": _text(close.get("title"), close_title),
            "route": _text(
                close.get("route"), close_route or primary_route or "/killer-demo"
            ),
            "line": _text(
                close.get("line"),
                close_line
                or primary_ask
                or "Capture accepted roles, blockers and next paid step.",
            ),
            "file": _text(close.get("file"), close_file),
            "status": _text(purchase_path.get("status"), close_status or "watch"),
            "source": "purchase_path.close_artifact" if has_buyer_plan else source,
        },
        {
            "step": 4,
            "stage": "verify",
            "label": "Verify",
            "title": _text(verification.get("title"), verify_title),
            "route": _text(verification.get("route"), verify_route),
            "line": _text(verification.get("line"), verify_line),
            "file": _text(verification.get("file"), verify_file),
            "status": _text(verification.get("status"), verify_status),
            "source": "purchase_path.verification_packet_artifact"
            if has_buyer_plan
            else source,
        },
    ]


def _normalize_item(
    item: dict[str, Any], fallback: dict[str, Any], step: int
) -> dict[str, Any]:
    merged = {
        **fallback,
        **{key: value for key, value in item.items() if value not in (None, "")},
    }
    merged["step"] = _int(merged.get("step"), step)
    merged["stage"] = _text(merged.get("stage"), _text(fallback.get("stage"), ""))
    merged["label"] = _text(merged.get("label"), _text(fallback.get("label"), ""))
    merged["title"] = _text(
        merged.get("title"),
        _text(merged.get("label"), _text(fallback.get("title"), "")),
    )
    merged["route"] = _text(
        merged.get("route"), _text(fallback.get("route"), "/launch-room")
    )
    merged["line"] = _text(
        merged.get("line"),
        _text(
            merged.get("signal"),
            _text(merged.get("check"), _text(fallback.get("line"), "")),
        ),
    )
    merged["file"] = _text(
        merged.get("file"),
        _text(
            merged.get("filename"),
            _text(
                merged.get("proof_file"),
                _text(merged.get("evidence_file"), _text(fallback.get("file"), "")),
            ),
        ),
    )
    merged["status"] = _text(
        merged.get("status"), _text(fallback.get("status"), "watch")
    )
    merged["source"] = _text(
        merged.get("source"), _text(fallback.get("source"), "open-first")
    )
    return merged


def build_open_first_path(
    *,
    existing_path: Any = None,
    buyer_room_plan: dict[str, Any] | None = None,
    proof_readiness: list[dict[str, Any]] | None = None,
    purchase_path: dict[str, Any] | None = None,
    primary: dict[str, Any] | None = None,
    meeting_flow: list[dict[str, Any]] | None = None,
    source: str = "open-first-fallback",
    orient_title: str = "Open buyer route",
    orient_route: str = "/launch-room",
    orient_line: str = "Open one route before deep workbench navigation.",
    orient_file: str = "buyer-brief.md",
    orient_status: str = "watch",
    prove_title: str = "Killer Demo",
    prove_route: str = "/killer-demo",
    prove_line: str = "Show one role-ready proof path before opening deep workbench routes.",
    prove_file: str = "OPEN_FIRST_KILLER_DEMO.md",
    prove_status: str = "watch",
    close_label: str = "Close",
    close_title: str = "Meeting Close Receipt",
    close_route: str = "/killer-demo",
    close_line: str = "Capture accepted roles, blockers and next paid step.",
    close_file: str = "MEETING_CLOSE_RECEIPT.md",
    close_status: str = "watch",
    verify_title: str = "Verification Packet ZIP",
    verify_route: str = "/evidence-bundle",
    verify_line: str = "Attach the pair-level archive verification packet.",
    verify_file: str = ARCHIVE_VERIFICATION_PACKET_ZIP,
    verify_status: str = "ready",
) -> list[dict[str, Any]]:
    """Return a four-step orient/prove/close/verify path with stable fields."""

    buyer_room_plan_dict = _as_dict(buyer_room_plan)
    purchase_path_dict = _as_dict(purchase_path)
    primary_dict = _as_dict(primary)
    proof_items = _as_list(proof_readiness)
    meeting_items = _as_list(meeting_flow)
    fallback = _fallback_path(
        buyer_room_plan=buyer_room_plan_dict,
        proof_readiness=proof_items,
        purchase_path=purchase_path_dict,
        primary=primary_dict,
        meeting_flow=meeting_items,
        source=source,
        orient_title=orient_title,
        orient_route=orient_route,
        orient_line=orient_line,
        orient_file=orient_file,
        orient_status=orient_status,
        prove_title=prove_title,
        prove_route=prove_route,
        prove_line=prove_line,
        prove_file=prove_file,
        prove_status=prove_status,
        close_label=close_label,
        close_title=close_title,
        close_route=close_route,
        close_line=close_line,
        close_file=close_file,
        close_status=close_status,
        verify_title=verify_title,
        verify_route=verify_route,
        verify_line=verify_line,
        verify_file=verify_file,
        verify_status=verify_status,
    )
    existing_items = _as_list(existing_path)
    if not existing_items:
        return fallback
    return [
        _normalize_item(
            existing_items[index] if index < len(existing_items) else {},
            fallback[index],
            index + 1,
        )
        for index in range(4)
    ]


def open_first_path_markdown_lines(
    path: Any,
    *,
    heading: str = "### Open-First Path",
    default_route: str = "/launch-room",
) -> list[str]:
    items = _as_list(path)
    if not items:
        return []
    lines = ["", heading, ""]
    for item in items[:4]:
        lines.append(
            f"- **{_text(item.get('step'), '')}. {_text(item.get('label'), 'Step')}** "
            f"(`{_text(item.get('route'), default_route)}`): "
            f"`{_text(item.get('file'), '')}` - {_text(item.get('line'), '')}"
        )
    return lines
