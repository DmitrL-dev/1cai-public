"""YAxUnit/Vanessa test inventory and lightweight ownership matching."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TEST_ROOTS = ("tests/bsl",)
YAXUNIT_ROOT = ROOT / "tools" / "yaxunit"

_PROC_RE = re.compile(
    r"^\s*(Процедура|Функция)\s+([A-Za-zА-Яа-яЁё0-9_]+)", re.IGNORECASE | re.MULTILINE
)
_EN_PROC_RE = re.compile(
    r"^\s*(Procedure|Function)\s+([A-Za-z][A-Za-z0-9_]*)", re.IGNORECASE | re.MULTILINE
)
_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]{4,}")
_COMMON_TERMS = {
    "commonmodules",
    "documents",
    "catalogs",
    "module",
    "objectmodule",
    "managermodule",
    "forms",
    "form",
    "test",
    "tests",
    "тест",
    "тесты",
    "модуль",
    "форма",
    "документ",
    "справочник",
}


def _tokens(text: str) -> list[str]:
    text = text.replace("_", " ")
    terms = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0).casefold().strip("_")
        if len(token) >= 4 and token not in _COMMON_TERMS:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp1251", errors="ignore")


def _framework(text: str) -> str:
    lowered = text.casefold()
    if "yaxunit" in lowered or "ютест" in lowered:
        return "YAxUnit"
    if "vanessa" in lowered or "сценарий" in lowered:
        return "Vanessa"
    return "BSL"


def _test_roots(root: Path) -> list[Path]:
    return [root / item for item in DEFAULT_TEST_ROOTS if (root / item).exists()]


def _case_id(path: Path, name: str) -> str:
    return f"{path.as_posix()}::{name}"


@lru_cache(maxsize=8)
def build_test_inventory(root_raw: str | None = None) -> dict[str, Any]:
    root = Path(root_raw).resolve() if root_raw else ROOT
    cases: list[dict[str, Any]] = []
    files = []

    for test_root in _test_roots(root):
        for path in sorted(test_root.rglob("*.bsl")):
            text = _read_text(path)
            try:
                rel_path = path.relative_to(root).as_posix()
            except ValueError:
                rel_path = path.as_posix()
            framework = _framework(text)
            files.append(rel_path)
            matches = sorted(
                [*_PROC_RE.finditer(text), *_EN_PROC_RE.finditer(text)],
                key=lambda match: match.start(),
            )
            for match in matches:
                name = match.group(2)
                if "тест" not in name.casefold() and framework == "BSL":
                    continue
                line = text.count("\n", 0, match.start()) + 1
                terms = _tokens(
                    f"{name}\n{text[max(0, match.start() - 400): match.end() + 1200]}"
                )
                cases.append(
                    {
                        "id": _case_id(Path(rel_path), name),
                        "path": rel_path,
                        "name": name,
                        "framework": framework,
                        "line": line,
                        "selector": name,
                        "terms": terms,
                    }
                )

            if not matches and framework != "BSL":
                name = path.stem
                cases.append(
                    {
                        "id": _case_id(Path(rel_path), name),
                        "path": rel_path,
                        "name": name,
                        "framework": framework,
                        "line": 1,
                        "selector": name,
                        "terms": _tokens(text[:2000]),
                    }
                )

    by_framework = Counter(case["framework"] for case in cases)
    return {
        "root": str(root),
        "framework_available": YAXUNIT_ROOT.exists(),
        "test_files": sorted(files),
        "test_cases": cases,
        "summary": {
            "test_files": len(files),
            "test_cases": len(cases),
            "by_framework": dict(by_framework),
            "yaxunit_available": YAXUNIT_ROOT.exists(),
        },
    }


def inventory_summary(root: str | None = None) -> dict[str, Any]:
    inventory = build_test_inventory(root)
    return {
        "root": inventory["root"],
        "framework_available": inventory["framework_available"],
        "summary": inventory["summary"],
    }


def match_tests_for_module(
    module_path: str,
    *,
    object_name: str | None = None,
    limit: int = 5,
    root: str | None = None,
) -> list[dict[str, Any]]:
    inventory = build_test_inventory(root)
    query_terms = set(_tokens(f"{module_path} {object_name or ''}"))
    if not query_terms:
        return []

    matches = []
    for case in inventory["test_cases"]:
        case_terms = set(case["terms"])
        overlap = sorted(query_terms & case_terms)
        if not overlap:
            continue
        score = len(overlap) / max(len(query_terms), 1)
        confidence = min(0.9, 0.45 + score * 0.45)
        matches.append(
            {
                "id": case["id"],
                "path": case["path"],
                "name": case["name"],
                "framework": case["framework"],
                "line": case["line"],
                "selector": case["selector"],
                "confidence": round(confidence, 2),
                "matched_terms": overlap[:10],
                "reason": "Existing BSL test case matched changed module/object terms.",
            }
        )

    matches.sort(
        key=lambda item: (item["confidence"], len(item["matched_terms"])), reverse=True
    )
    return matches[:limit]
