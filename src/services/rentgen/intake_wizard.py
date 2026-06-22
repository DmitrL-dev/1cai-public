"""Configuration intake planning for EDT/Git/XML sources."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.rentgen.metadata_graph import DEFAULT_CONFIG_PATH
from src.services.rentgen.path_safety import collect_files, confine_path

# Per-category scan budget. Each metadata category (BSL, XML, forms, rights,
# tests) is scanned with its OWN budget so one huge category cannot starve
# another. A single combined cap used to truncate mid-alphabet on shipped
# configs (131k+ files): ``Roles/`` sorts after ``Catalogs/`` and never got
# counted, so ``rights_files`` came back a fabricated ``0`` with a false
# "missing Rights.xml" flag. Honest-coverage invariant #9 forbids that — a
# truncated category must be reported as UNKNOWN, never a definite count.
MAX_SCAN_FILES = 20_000

# A count we could not fully determine because the per-category cap was hit.
UNKNOWN = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_count(
    root: Path, suffixes: set[str], *, limit: int = MAX_SCAN_FILES
) -> int:
    files, _truncated = collect_files(root, suffixes=suffixes, max_files=limit)
    return len(files)


def _bounded_inventory(root: Path, *, limit: int = MAX_SCAN_FILES) -> dict[str, Any]:
    """Inventory metadata categories with a SEPARATE bounded pass per category.

    Returns counts that are either an ``int`` (the category was scanned fully)
    or :data:`UNKNOWN`/``None`` (the per-category cap was hit, so the real count
    is undetermined and must NOT be reported as a definite number or treated as
    a clean ``0``). ``*_truncated`` flags mirror that per category.
    """
    counts: dict[str, Any] = {
        "bsl_files": 0,
        "xml_files": 0,
        "form_files": 0,
        "rights_files": 0,
        "test_files": 0,
        "scanned_files": 0,
        "bsl_truncated": 0,
        "xml_truncated": 0,
        "scan_truncated": 0,
    }
    try:
        # BSL pass — also yields the test subset by filename. If this pass is
        # truncated we cannot trust the BSL or test totals, so both go UNKNOWN.
        bsl_files, bsl_truncated = collect_files(
            root, suffixes={".bsl"}, max_files=limit
        )
        if bsl_truncated:
            counts["bsl_files"] = UNKNOWN
            counts["test_files"] = UNKNOWN
            counts["bsl_truncated"] = 1
        else:
            counts["bsl_files"] = len(bsl_files)
            test_count = 0
            for path in bsl_files:
                folded = path.name.casefold()
                if "test" in folded or "тест" in folded:
                    test_count += 1
            counts["test_files"] = test_count

        # XML pass — yields the Form.xml / Rights.xml subsets by filename. If
        # this pass is truncated we cannot trust the XML, form or rights totals
        # (a later-sorting Roles/Rights.xml may be beyond the cap), so all three
        # go UNKNOWN rather than a fabricated 0.
        xml_files, xml_truncated = collect_files(
            root, suffixes={".xml"}, max_files=limit
        )
        if xml_truncated:
            counts["xml_files"] = UNKNOWN
            counts["form_files"] = UNKNOWN
            counts["rights_files"] = UNKNOWN
            counts["xml_truncated"] = 1
        else:
            counts["xml_files"] = len(xml_files)
            form_count = 0
            rights_count = 0
            for path in xml_files:
                if path.name == "Form.xml":
                    form_count += 1
                elif path.name == "Rights.xml":
                    rights_count += 1
            counts["form_files"] = form_count
            counts["rights_files"] = rights_count

        # scanned_files is a lower bound across the (already-bounded) passes.
        counts["scanned_files"] = sum(
            n for n in (len(bsl_files), len(xml_files)) if n is not None
        )
        counts["scan_truncated"] = 1 if (bsl_truncated or xml_truncated) else 0
    except OSError:
        return counts
    return counts


def _detect_source(path: Path, requested: str) -> str:
    if requested and requested != "auto":
        return requested
    if (path / ".git").exists():
        return "git"
    if (path / "Configuration.xml").exists():
        return "edt"
    if _bounded_count(path, {".xml"}, limit=10):
        return "xml"
    return "unknown"


def _status(available: bool, count: int | None = 0) -> str:
    if available and count is None:
        return "unknown"
    if available and count:
        return "ready"
    if available:
        return "partial"
    return "missing"


def _is_ready(count: int | None) -> bool:
    """A category is genuinely present only with a definite positive count."""
    return count is not None and count > 0


def _is_unknown(count: int | None) -> bool:
    """The category scan was truncated, so its real count is undetermined."""
    return count is None


def _is_absent(count: int | None) -> bool:
    """Fully scanned and genuinely zero — the only honest "missing" signal."""
    return count == 0


def _sum_known(*counts: int | None) -> int:
    """Sum only the definite counts; UNKNOWN categories are skipped, never 0."""
    return sum(c for c in counts if c is not None)


def _mix_status(count: int | None) -> str:
    if _is_unknown(count):
        return "unknown"
    return "ready" if _is_ready(count) else "missing"


def _coverage_caveat(count: int | None, *, missing: str, unknown: str) -> str | None:
    """Caveat for one coverage row.

    Ready (definite positive) → no caveat. UNKNOWN (truncated) → the
    "undetermined" caveat, never the "missing" one. Genuinely zero → "missing".
    """
    if _is_ready(count):
        return None
    if _is_unknown(count):
        return unknown
    return missing


def _scale_label(total_files: int) -> tuple[str, str]:
    if total_files >= 5_000:
        return (
            "enterprise",
            "Enterprise-scale source; index incrementally and keep proof artifacts versioned.",
        )
    if total_files >= 1_200:
        return (
            "large",
            "Large 1C source; start from graph, release and security proof before broad refactoring.",
        )
    if total_files >= 250:
        return (
            "medium",
            "Medium source; enough surface for impact, tests and value proof.",
        )
    if total_files > 0:
        return (
            "compact",
            "Compact source; first proof should be fast and easy to repeat.",
        )
    return "empty", "No readable source files were found yet."


def _configuration_genome(
    *,
    detected: str,
    inventory: dict[str, int],
    metadata_ready: bool,
    code_ready: bool,
    forms_ready: bool,
    rights_ready: bool,
    tests_ready: bool,
) -> dict[str, Any]:
    bsl_files = inventory["bsl_files"]
    xml_files = inventory["xml_files"]
    form_files = inventory["form_files"]
    rights_files = inventory["rights_files"]
    test_files = inventory["test_files"]
    total_files = _sum_known(bsl_files, xml_files, form_files, rights_files)
    scale_id, scale_line = _scale_label(total_files)
    first_proof = (
        {
            "label": "Build Rentgen graph",
            "route": "/quality",
            "reason": "BSL modules are present, so the first credible proof is call graph, hotspots and impact.",
        }
        if code_ready
        else {
            "label": "Open metadata map",
            "route": "/metadata" if metadata_ready else "/",
            "reason": "Start from metadata coverage before promising code-level impact.",
        }
    )
    tracks = [
        {
            "id": "developer",
            "label": "Developer proof",
            "route": "/quality",
            "status": "ready"
            if code_ready
            else "unknown"
            if _is_unknown(bsl_files)
            else "missing",
            "line": "Changed modules, call graph and query diagnostics can be shown."
            if code_ready
            else "BSL count is undetermined (scan truncated); run incremental indexing to confirm."
            if _is_unknown(bsl_files)
            else "Add .bsl files before promising code proof.",
        },
        {
            "id": "architect",
            "label": "Architecture map",
            "route": "/metadata",
            "status": "ready"
            if metadata_ready
            else "unknown"
            if _is_unknown(xml_files)
            else "missing",
            "line": "Metadata XML is present, so object and dependency mapping can start."
            if metadata_ready
            else "Metadata XML count is undetermined (scan truncated); run incremental indexing to confirm."
            if _is_unknown(xml_files)
            else "Add EDT/XML export with Configuration.xml and metadata objects.",
        },
        {
            "id": "security",
            "label": "Rights and RLS",
            "route": "/rights-rls",
            "status": "ready"
            if rights_ready
            else "unknown"
            if _is_unknown(rights_files)
            else "missing",
            "line": "Rights.xml is present for role/security review."
            if rights_ready
            else "Rights.xml presence is undetermined (scan truncated); run incremental indexing before security claims."
            if _is_unknown(rights_files)
            else "Attach Rights.xml before security claims become buyer-forwardable.",
        },
        {
            "id": "qa",
            "label": "Test factory",
            "route": "/testing",
            "status": "ready"
            if tests_ready
            else "unknown"
            if _is_unknown(test_files)
            else "partial"
            if code_ready
            else "missing",
            "line": "Existing tests can be matched to impact."
            if tests_ready
            else "Test count is undetermined (scan truncated); run incremental indexing to confirm coverage."
            if _is_unknown(test_files)
            else "Test Factory can plan gaps, but exact coverage needs test files.",
        },
        {
            "id": "release",
            "label": "Release gate",
            "route": "/release-readiness",
            "status": "ready" if code_ready or metadata_ready else "missing",
            "line": "Release readiness can expose caveats from the available source."
            if code_ready or metadata_ready
            else "No release gate until code or metadata is available.",
        },
        {
            "id": "platform",
            "label": "Platform doctor",
            "route": "/platform-doctor",
            "status": "missing",
            "line": "Add platform version, tech journal or OpenMetrics to prove runtime readiness.",
        },
    ]
    # Only emit a "missing X" risk when the category was FULLY scanned and is
    # genuinely zero (``_is_absent``). A truncated/UNKNOWN category must NOT
    # raise a "missing" flag — that was the fabricated safe-or-scary zero of
    # honest-coverage finding #9. Truncation is surfaced as its own caveat.
    risk_flags = [
        item
        for item in [
            {
                "id": "metadata",
                "severity": "high",
                "line": "No metadata XML: architecture map and object impact stay partial.",
            }
            if _is_absent(xml_files)
            else None,
            {
                "id": "code",
                "severity": "high",
                "line": "No BSL files: developer proof and Query Surgeon stay unavailable.",
            }
            if _is_absent(bsl_files)
            else None,
            {
                "id": "forms",
                "severity": "medium",
                "line": "No Form.xml files: UI impact caveats remain visible.",
            }
            if _is_absent(form_files)
            else None,
            {
                "id": "rights",
                "severity": "medium",
                "line": "No Rights.xml files: security/RLS conclusions remain advisory.",
            }
            if _is_absent(rights_files)
            else None,
            {
                "id": "tests",
                "severity": "medium",
                "line": "No tests detected: release confidence starts with planned/gap coverage.",
            }
            if _is_absent(test_files)
            else None,
            {
                "id": "scan-limit",
                "severity": "medium",
                "line": "Scan limit reached; some category counts are undetermined — run incremental indexing for the full source.",
            }
            if inventory["scan_truncated"]
            else None,
        ]
        if item
    ]
    return {
        "headline": f"{detected.upper()} source, {scale_id} scale, {sum(1 for item in tracks if item['status'] == 'ready')} proof tracks ready.",
        "scale": {
            "id": scale_id,
            "files": total_files,
            "line": scale_line,
        },
        "source_mix": [
            {
                "id": "bsl",
                "label": "BSL modules",
                "count": bsl_files,
                "status": _mix_status(bsl_files),
            },
            {
                "id": "xml",
                "label": "Metadata XML",
                "count": xml_files,
                "status": _mix_status(xml_files),
            },
            {
                "id": "forms",
                "label": "Forms",
                "count": form_files,
                "status": _mix_status(form_files),
            },
            {
                "id": "rights",
                "label": "Rights",
                "count": rights_files,
                "status": _mix_status(rights_files),
            },
            {
                "id": "tests",
                "label": "Tests",
                "count": test_files,
                "status": _mix_status(test_files),
            },
        ],
        "readiness_tracks": tracks,
        "risk_flags": risk_flags,
        "first_proof": first_proof,
        "buyer_story": [
            {
                "role": "Developer",
                "spark": "Open the first changed module with graph and test impact.",
                "route": "/quality",
            },
            {
                "role": "Architect",
                "spark": "See whether metadata, forms, rights and code are enough for credible impact analysis.",
                "route": "/metadata",
            },
            {
                "role": "Director",
                "spark": "Turn this source into a buyer-forwardable proof path instead of another AI subscription experiment.",
                "route": "/killer-demo",
            },
        ],
    }


def build_intake_plan(
    source_path: str | None = None, source_type: str = "auto"
) -> dict[str, Any]:
    """Inspect a local source and return an honest first indexing plan.

    This does not mutate stores or start imports. It is a pre-flight: what can be
    read, what coverage is likely, what will remain caveated, and what action the
    user should take next.
    """

    # Confine the caller-supplied path to the allowed data roots. An out-of-root
    # path (e.g. ``C:\Windows``) raises ValueError, which the endpoint layer maps
    # — we must not edit those callers, so we let it propagate. A non-existent
    # path under an allowed root resolves fine and is reported as "blocked" below.
    if source_path:
        resolved = confine_path(Path(source_path).expanduser(), label="config_path")
    else:
        resolved = DEFAULT_CONFIG_PATH.resolve()
    exists = resolved.exists()
    is_dir = resolved.is_dir()
    detected = _detect_source(resolved, source_type) if exists and is_dir else "missing"

    # Read the cap at call time (single source of truth) so an operator-tuned
    # MAX_SCAN_FILES takes effect rather than a value frozen at import.
    inventory = (
        _bounded_inventory(resolved, limit=MAX_SCAN_FILES)
        if exists and is_dir
        else {
            "bsl_files": 0,
            "xml_files": 0,
            "form_files": 0,
            "rights_files": 0,
            "test_files": 0,
            "scanned_files": 0,
            "bsl_truncated": 0,
            "xml_truncated": 0,
            "scan_truncated": 0,
        }
    )
    bsl_files = inventory["bsl_files"]
    xml_files = inventory["xml_files"]
    form_files = inventory["form_files"]
    rights_files = inventory["rights_files"]
    test_files = inventory["test_files"]

    # "ready" requires a definite positive count; an UNKNOWN (truncated) category
    # is neither ready nor missing — it is undetermined and gets a caveat.
    metadata_ready = exists and is_dir and _is_ready(xml_files)
    code_ready = exists and is_dir and _is_ready(bsl_files)
    forms_ready = exists and is_dir and _is_ready(form_files)
    rights_ready = exists and is_dir and _is_ready(rights_files)
    tests_ready = exists and is_dir and _is_ready(test_files)

    coverage = [
        {
            "id": "metadata",
            "title": "Метаданные",
            "status": _status(metadata_ready or _is_unknown(xml_files), xml_files),
            "count": xml_files,
            "caveat": _coverage_caveat(
                xml_files,
                missing="Нужна EDT/XML-выгрузка с Configuration.xml и объектами метаданных.",
                unknown="Скан XML был усечён лимитом — число метаданных не определено, нужна инкрементальная индексация.",
            ),
        },
        {
            "id": "bsl",
            "title": "BSL-код",
            "status": _status(code_ready or _is_unknown(bsl_files), bsl_files),
            "count": bsl_files,
            "caveat": _coverage_caveat(
                bsl_files,
                missing="Без .bsl файлов impact и Query Surgeon будут частичными.",
                unknown="Скан BSL был усечён лимитом — число модулей не определено, нужна инкрементальная индексация.",
            ),
        },
        {
            "id": "forms",
            "title": "Формы",
            "status": _status(forms_ready or _is_unknown(form_files), form_files),
            "count": form_files,
            "caveat": _coverage_caveat(
                form_files,
                missing="Формы не будут участвовать в UI/impact caveats.",
                unknown="Скан XML был усечён лимитом — число форм не определено, нужна инкрементальная индексация.",
            ),
        },
        {
            "id": "rights",
            "title": "Права/RLS",
            "status": _status(rights_ready or _is_unknown(rights_files), rights_files),
            "count": rights_files,
            "caveat": _coverage_caveat(
                rights_files,
                missing="Security/RLS выводы останутся advisory до подключения Rights.xml.",
                unknown="Скан XML был усечён лимитом — наличие Rights.xml не определено, нужна инкрементальная индексация.",
            ),
        },
        {
            "id": "tests",
            "title": "Тесты",
            "status": _status(tests_ready or _is_unknown(test_files), test_files),
            "count": test_files,
            "caveat": _coverage_caveat(
                test_files,
                missing="Test Factory покажет planned/gap вместо точных тестов.",
                unknown="Скан BSL был усечён лимитом — число тестов не определено, нужна инкрементальная индексация.",
            ),
        },
        {
            "id": "platform",
            "title": "Платформа/эксплуатация",
            "status": "missing",
            "count": 0,
            "caveat": "Для Platform Doctor нужны версия платформы, техжурнал/OpenMetrics или ops export.",
        },
    ]

    ready = sum(1 for item in coverage if item["status"] == "ready")
    # An "unknown" (truncated) category is genuinely undetermined: weight it like
    # a partial so it neither inflates to a clean pass nor deflates to a zero.
    partial = sum(1 for item in coverage if item["status"] in ("partial", "unknown"))
    score = round((ready + partial * 0.55) / len(coverage) * 100)
    estimated_minutes = max(
        2, min(30, round(_sum_known(bsl_files, xml_files) / 1200) + 2)
    )
    status = "ready" if exists and score >= 70 else "partial" if exists else "blocked"
    genome = _configuration_genome(
        detected=detected,
        inventory=inventory,
        metadata_ready=metadata_ready,
        code_ready=code_ready,
        forms_ready=forms_ready,
        rights_ready=rights_ready,
        tests_ready=tests_ready,
    )

    return {
        "generated_at": _now(),
        "source": {
            "path": str(resolved),
            "exists": exists,
            "is_dir": is_dir,
            "requested_type": source_type,
            "detected_type": detected,
        },
        "decision": {
            "status": status,
            "score": score if exists else 0,
            "headline": (
                "Источник готов к первому анализу."
                if status == "ready"
                else "Источник можно анализировать частично."
                if status == "partial"
                else "Источник не найден или недоступен."
            ),
        },
        "inventory": {
            # A count is ``null`` when its per-category scan was truncated: the
            # real number is undetermined, NOT zero. ``*_truncated`` flags say
            # which categories that applies to.
            "bsl_files": bsl_files,
            "xml_files": xml_files,
            "form_files": form_files,
            "rights_files": rights_files,
            "test_files": test_files,
            "scanned_files": inventory["scanned_files"],
            "bsl_truncated": bool(inventory.get("bsl_truncated")),
            "xml_truncated": bool(inventory.get("xml_truncated")),
            "scan_truncated": bool(inventory["scan_truncated"]),
            "scan_limit": MAX_SCAN_FILES,
        },
        "configuration_genome": genome,
        "coverage": coverage,
        "estimate": {
            "minutes": estimated_minutes,
            "mode": "local-preflight",
            "notes": [
                "Оценка не запускает импорт и не изменяет локальные stores.",
                "Большие ERP/UH конфигурации должны индексироваться инкрементально.",
                "Pre-flight сканирует каждую категорию отдельным проходом с лимитом scan_limit; усечённая категория помечается как undetermined, а не 0.",
            ],
        },
        "next_actions": [
            {
                "label": "Импортировать метаданные",
                "to": "/metadata",
                "enabled": metadata_ready,
                "reason": "Нужны XML-объекты EDT/выгрузки.",
            },
            {
                "label": "Собрать граф Рентгена",
                "to": "/quality",
                "enabled": code_ready,
                "reason": "Нужны .bsl файлы и callgraph export.",
            },
            {
                "label": "Проверить изменение",
                "to": "/change",
                "enabled": code_ready,
                "reason": "Impact работает по модулям и графу вызовов.",
            },
            {
                "label": "Собрать релизный gate",
                "to": "/release-readiness",
                "enabled": code_ready or metadata_ready,
                "reason": "Gate честно покажет caveats для неполного покрытия.",
            },
        ],
        "caveats": [item["caveat"] for item in coverage if item["caveat"]],
    }
