"""Offline readiness self-test for closed enterprise contours."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.services.rentgen.metadata_graph import metadata_summary


REPO_ROOT = Path(__file__).resolve().parents[3]
EXTERNAL_ENV_KEYS = [
    "OPENAI_API_KEY",
    "KIMI_API_KEY",
    "GIGACHAT_CREDENTIALS",
    "YANDEXGPT_API_KEY",
    "ANTHROPIC_API_KEY",
    "MCP_BSL_CONTEXT_BASE_URL",
    "MCP_BSL_TEST_RUNNER_BASE_URL",
    "SUPABASE_URL",
    "AWS_S3_ENDPOINT",
    "MINIO_ENDPOINT",
    "TELEGRAM_BOT_TOKEN",
]


def _check(checks: list[dict[str, Any]], *, id: str, title: str, status: str, evidence: Any, severity: str = "medium") -> None:
    checks.append(
        {
            "id": id,
            "title": title,
            "status": status,
            "severity": severity,
            "evidence": evidence,
        }
    )


def _exists(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists()}


def _docs_count(path: Path) -> int:
    return len(list(path.glob("*.txt"))) if path.exists() else 0


def _decision(checks: list[dict[str, Any]]) -> dict[str, Any]:
    fails = [item for item in checks if item["status"] == "fail"]
    warns = [item for item in checks if item["status"] == "warn"]
    score = max(0, 100 - len(fails) * 25 - len(warns) * 8)
    if fails:
        status = "fail"
    elif warns:
        status = "warn"
    else:
        status = "pass"
    return {
        "status": status,
        "score": score,
        "fails": len(fails),
        "warnings": len(warns),
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 1cAI Offline Readiness",
        "",
        f"Status: **{report['decision']['status'].upper()}**",
        f"Score: **{report['decision']['score']}**",
        "",
        "## Checks",
        "",
    ]
    for item in report["checks"]:
        lines.append(f"- **{item['status']}** `{item['id']}`: {item['title']}")
    lines.extend(["", "## External Surface", ""])
    if report["external_env"]:
        for item in report["external_env"]:
            lines.append(f"- `{item}` is configured")
    else:
        lines.append("- No known external API/base-url env vars are configured.")
    return "\n".join(lines)


def build_offline_readiness(
    *,
    strict: bool = False,
    root: Path | None = None,
    include_metadata: bool = True,
) -> dict[str, Any]:
    """Build a local-only offline readiness report."""

    repo = (root or REPO_ROOT).resolve()
    checks: list[dict[str, Any]] = []

    rentgen_db = repo / "data" / "rentgen.db"
    _check(
        checks,
        id="rentgen-store",
        title="Rentgen SQLite store is available locally",
        status="pass" if rentgen_db.exists() else ("fail" if strict else "warn"),
        evidence=_exists(rentgen_db),
        severity="high",
    )

    config_path = repo / "data" / "configs" / "unpacked"
    _check(
        checks,
        id="metadata-config",
        title="Unpacked EDT metadata is available locally",
        status="pass" if config_path.exists() else ("fail" if strict else "warn"),
        evidence=_exists(config_path),
        severity="high",
    )

    docs_path = repo / "docs" / "its_forms" / "sections"
    docs_count = _docs_count(docs_path)
    _check(
        checks,
        id="offline-its",
        title="Offline ITS documentation chunks are available",
        status="pass" if docs_count else ("fail" if strict else "warn"),
        evidence={"path": str(docs_path), "txt_files": docs_count},
        severity="high",
    )

    model_path = repo / "models" / "qwen-bsl-lora"
    model_exists = model_path.exists()
    _check(
        checks,
        id="local-llm",
        title=(
            "Local BSL model is present"
            if model_exists
            else "Local BSL model is not present; deterministic generator works without it"
        ),
        status="pass" if model_exists else "warn",
        evidence=_exists(model_path),
        severity="low",
    )

    its_mode = (os.getenv("ITS_RAG_MODE") or "offline").lower()
    _check(
        checks,
        id="its-mode",
        title="ITS RAG mode does not require external semantic services",
        status="pass" if its_mode in {"offline", "auto"} else ("fail" if strict else "warn"),
        evidence={"ITS_RAG_MODE": its_mode},
        severity="medium",
    )

    external_env = [key for key in EXTERNAL_ENV_KEYS if os.getenv(key)]
    _check(
        checks,
        id="external-env",
        title=(
            "Known external API/base-url environment variables are not configured"
            if not external_env
            else "Known external API/base-url environment variables are configured"
        ),
        status="pass" if not external_env else ("fail" if strict else "warn"),
        evidence={"configured": external_env},
        severity="high" if strict else "medium",
    )

    if include_metadata:
        try:
            metadata = metadata_summary(str(config_path))
            metadata_signal = metadata.get("summary", {})
        except Exception as exc:  # pragma: no cover - defensive runtime report
            metadata_signal = {"error": str(exc)}
    else:
        metadata_signal = {"skipped": True}

    report = {
        "strict": strict,
        "root": str(repo),
        "decision": _decision(checks),
        "summary": {
            "checks": len(checks),
            "passes": sum(1 for item in checks if item["status"] == "pass"),
            "warnings": sum(1 for item in checks if item["status"] == "warn"),
            "fails": sum(1 for item in checks if item["status"] == "fail"),
            "external_env": len(external_env),
            "metadata_objects": metadata_signal.get("total_objects", 0),
            "its_docs": docs_count,
        },
        "checks": checks,
        "external_env": external_env,
        "runtime": {
            "offline_env": os.getenv("OFFLINE") or "",
            "its_rag_mode": its_mode,
            "dev_skip_auth": os.getenv("DEV_SKIP_AUTH") or "",
            "metadata_scan": "included" if include_metadata else "skipped",
        },
        "caveats": [
            "This self-test does not attempt outbound network calls.",
            "External services can still be used if operators configure them intentionally.",
        ],
    }
    report["markdown"] = _markdown(report)
    return report
