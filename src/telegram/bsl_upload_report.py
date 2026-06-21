"""Helpers for Telegram BSL upload diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def decode_uploaded_text(raw: bytes) -> str:
    """Decode uploaded 1C/BSL text using common project encodings."""
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _shorten(value: object, limit: int = 180) -> str:
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _first_text(values: object) -> str | None:
    if isinstance(values, str):
        return values.strip() or None
    if not isinstance(values, Iterable):
        return None

    for value in values:
        text = str(value).strip()
        if text:
            return text
    return None


def _details(item: Mapping[str, Any]) -> Mapping[str, Any]:
    details = item.get("details")
    return details if isinstance(details, Mapping) else {}


def format_bsl_upload_report(file_name: str, result: Mapping[str, Any]) -> str:
    """Build a concise Telegram-safe plain-text diagnostics report."""
    diagnostics = result.get("diagnostics") or []
    metrics = result.get("metrics") or {}
    if not isinstance(metrics, Mapping):
        metrics = {}

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for item in diagnostics:
        if not isinstance(item, Mapping):
            continue
        severity = str(item.get("severity") or "").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1

    lines = [
        f"File analyzed: {file_name}",
        (
            f"LOC: {metrics.get('loc', 0)} | "
            f"procedures: {metrics.get('procedures', 0)} | "
            f"functions: {metrics.get('functions', 0)} | "
            f"max nesting: {metrics.get('max_nesting', 0)}"
        ),
        (
            f"Findings: {len(diagnostics)} "
            f"(high {severity_counts['high']}, medium {severity_counts['medium']}, low {severity_counts['low']})"
        ),
    ]

    if diagnostics:
        lines.append("")
        lines.append("Top findings:")
        for raw_item in diagnostics[:8]:
            if not isinstance(raw_item, Mapping):
                continue

            line = raw_item.get("line") or "?"
            severity = str(raw_item.get("severity") or "info").upper()
            code = raw_item.get("code") or "diagnostic"
            message = raw_item.get("message") or "Review this location."
            lines.append(f"- {severity} line {line} [{code}]: {_shorten(message, 220)}")

            details = _details(raw_item)
            safe_option = _first_text(details.get("safe_options"))
            if safe_option:
                lines.append(f"  Safe option: {_shorten(safe_option)}")

            test_expectation = _first_text(details.get("test_expectations"))
            if test_expectation:
                lines.append(f"  Test: {_shorten(test_expectation)}")
    else:
        lines.append("")
        lines.append("No local diagnostics found.")

    caveats = result.get("caveats") or []
    caveat = _first_text(caveats)
    if caveat:
        lines.append("")
        lines.append(f"Note: {_shorten(caveat, 260)}")

    return "\n".join(lines)
