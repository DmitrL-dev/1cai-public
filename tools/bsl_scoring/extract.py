"""Python-based feature extraction for .bsl files.

Replaces Go scanner. Extracts structural, quality, and anti-pattern features
from every BSL module in an unpacked 1C configuration.

Target: 20K files in under 60 seconds using multiprocessing.
"""

import json
import re
import sys
from multiprocessing import Pool, cpu_count
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ENCODINGS = ["utf-8-sig", "utf-8", "cp1251"]

# Module type detection from path segments
_MODULE_TYPE_MAP = {
    "ObjectModule.bsl": "ObjectModule",
    "Ext/ObjectModule.bsl": "ObjectModule",
    "ManagerModule.bsl": "ManagerModule",
    "Ext/ManagerModule.bsl": "ManagerModule",
    "Module.bsl": "CommonModule",
    "Ext/Module.bsl": "CommonModule",
    "CommandModule.bsl": "CommandModule",
    "Ext/CommandModule.bsl": "CommandModule",
    "RecordSetModule.bsl": "RecordSetModule",
    "Ext/RecordSetModule.bsl": "RecordSetModule",
}

# Regex patterns — compiled once at module level for speed
_RE_FUNC_DECL = re.compile(
    r"^\s*(?:Процедура|Функция|Procedure|Function)\s+(\w+)",
    re.IGNORECASE | re.MULTILINE,
)
_RE_EXPORT = re.compile(r"\bЭкспорт\b|\bExport\b", re.IGNORECASE)
_RE_COMMENT_LINE = re.compile(r"^\s*//")
_RE_BRANCH_KEYWORDS = re.compile(
    r"\b(?:Если|ИначеЕсли|Пока|Для|ДляКаждого|Попытка|If|ElsIf|While|For|ForEach|Try)\b",
    re.IGNORECASE,
)
_RE_LOGICAL_OPS = re.compile(r"\b(?:И|Или|And|Or)\b", re.IGNORECASE)
_RE_NESTING_OPEN = re.compile(
    r"^\s*(?:Если|Пока|Для|ДляКаждого|If|While|For|ForEach)\b",
    re.IGNORECASE,
)
_RE_NESTING_CLOSE = re.compile(
    r"^\s*(?:КонецЕсли|КонецЦикла|EndIf|EndDo)\b",
    re.IGNORECASE,
)
_RE_TRY = re.compile(r"^\s*(?:Попытка|Try)\b", re.IGNORECASE)
_RE_EXCEPT = re.compile(r"^\s*(?:Исключение|Except)\b", re.IGNORECASE)
_RE_END_TRY = re.compile(r"^\s*(?:КонецПопытки|EndTry)\b", re.IGNORECASE)
_RE_FUNC_START = re.compile(
    r"^\s*(?:Процедура|Функция|Procedure|Function)\b", re.IGNORECASE
)
_RE_FUNC_END = re.compile(
    r"^\s*(?:КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)\b",
    re.IGNORECASE,
)
_RE_LOOP_START = re.compile(
    r"^\s*(?:Для|ДляКаждого|Пока|For|ForEach|While)\b", re.IGNORECASE
)
_RE_QUERY = re.compile(r"(?:ВЫБРАТЬ|SELECT)\b", re.IGNORECASE)
_RE_SELECT_STAR = re.compile(r"\b(?:ВЫБРАТЬ|SELECT)\s+\*", re.IGNORECASE)
_RE_MAGIC_NUMBER = re.compile(r'(?<!["\w])(\d+)(?!["\w])')
_RE_STRING_LITERAL = re.compile(r'"[^"]*"')
_RE_TODO = re.compile(r"\b(?:TODO|FIXME|HACK)\b", re.IGNORECASE)
_RE_METADATA_REF = re.compile(
    r"\b(Справочник(?:и)?|Документ(?:ы)?|РегистрСведений|РегистрНакопления|"
    r"РегистрБухгалтерии|Перечисление|ПланСчетов|ПланВидовХарактеристик|"
    r"ПланВидовРасчета|БизнесПроцесс|Задача|Обработка|Отчет|"
    r"Catalog(?:s)?|Document(?:s)?|InformationRegister(?:s)?|AccumulationRegister(?:s)?|"
    r"AccountingRegister(?:s)?|Enum(?:s)?|ChartOfAccounts|"
    r"ChartOfCharacteristicTypes|ChartOfCalculationTypes|"
    r"BusinessProcess(?:es)?|Task(?:s)?|DataProcessor(?:s)?|Report(?:s)?)"
    r"\.([А-Яа-яЁёA-Za-z0-9_]+)",
    re.IGNORECASE,
)
_RE_CYRILLIC_IDENT = re.compile(r"\b([А-Яа-яЁё][А-Яа-яЁё0-9_]*)\b")
_RE_ASSIGNMENT = re.compile(r"^\s*([А-Яа-яЁё][А-Яа-яЁё0-9_]*)\s*=")


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------


def _read_bsl(path: Path) -> Optional[str]:
    """Read a BSL file trying multiple encodings."""
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    # Last resort: read with replacement
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Module type detection
# ---------------------------------------------------------------------------


def _detect_module_type(rel_path: str) -> str:
    """Detect module type from relative file path."""
    rel_normed = rel_path.replace("\\", "/")

    # Form modules
    if "/Forms/" in rel_normed and "/Ext/Form/Module.bsl" in rel_normed:
        return "FormModule"

    for suffix, mtype in _MODULE_TYPE_MAP.items():
        if rel_normed.endswith(suffix):
            return mtype

    return "Unknown"


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------


def _extract_features(args: tuple) -> Optional[Dict[str, Any]]:
    """Extract all features from a single .bsl file.

    Args is a tuple (file_path_str, config_root_str) to work with multiprocessing.
    """
    file_path_str, config_root_str = args
    file_path = Path(file_path_str)
    config_root = Path(config_root_str)

    text = _read_bsl(file_path)
    if text is None:
        return None

    try:
        rel_path = str(file_path.relative_to(config_root))
    except ValueError:
        rel_path = str(file_path)

    lines = text.splitlines()
    total_lines = len(lines)
    non_empty_lines = [l for l in lines if l.strip()]
    loc = len(non_empty_lines)

    if loc == 0:
        return None  # skip empty modules

    module_type = _detect_module_type(rel_path)

    # --- Comment analysis ---
    comment_lines = sum(1 for l in lines if _RE_COMMENT_LINE.match(l))
    comment_density = round(comment_lines / total_lines, 4) if total_lines > 0 else 0.0

    # --- Module header ---
    first_non_empty = ""
    for l in lines:
        if l.strip():
            first_non_empty = l.strip()
            break
    has_module_header = first_non_empty.startswith("//")

    # --- Functions ---
    func_matches = list(_RE_FUNC_DECL.finditer(text))
    num_functions = len(func_matches)

    # Export count
    export_count = 0
    for line in lines:
        if _RE_FUNC_START.match(line) and _RE_EXPORT.search(line):
            export_count += 1
    export_ratio = round(export_count / num_functions, 4) if num_functions > 0 else 0.0

    # --- Average function length ---
    func_lengths: List[int] = []
    in_func = False
    func_line_count = 0
    for line in lines:
        if _RE_FUNC_START.match(line):
            in_func = True
            func_line_count = 0
        elif _RE_FUNC_END.match(line):
            if in_func:
                func_lengths.append(func_line_count)
            in_func = False
            func_line_count = 0
        elif in_func:
            if line.strip():
                func_line_count += 1
    avg_func_length = (
        round(sum(func_lengths) / len(func_lengths), 2) if func_lengths else float(loc)
    )

    # --- Cyclomatic complexity ---
    cyclomatic = 1
    for line in lines:
        stripped = line.strip()
        if _RE_COMMENT_LINE.match(line):
            continue
        branch_hits = _RE_BRANCH_KEYWORDS.findall(stripped)
        cyclomatic += len(branch_hits)
        logical_hits = _RE_LOGICAL_OPS.findall(stripped)
        cyclomatic += len(logical_hits)

    # --- Max nesting depth ---
    max_nesting = 0
    current_nesting = 0
    for line in lines:
        stripped = line.strip()
        if _RE_COMMENT_LINE.match(line):
            continue
        if _RE_NESTING_OPEN.match(stripped):
            current_nesting += 1
            max_nesting = max(max_nesting, current_nesting)
        elif _RE_NESTING_CLOSE.match(stripped):
            current_nesting = max(0, current_nesting - 1)
    has_deep_nesting = max_nesting >= 5

    # --- Doc coverage ---
    doc_covered = 0
    for i, line in enumerate(lines):
        if _RE_FUNC_START.match(line):
            # Check if preceded by a comment block
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            if j >= 0 and _RE_COMMENT_LINE.match(lines[j]):
                doc_covered += 1
    doc_coverage = round(doc_covered / num_functions, 4) if num_functions > 0 else 0.0

    # --- Error handling ---
    has_error_handling = bool(_RE_TRY.search(text))

    # --- Empty catch ---
    has_empty_catch = False
    for i, line in enumerate(lines):
        if _RE_EXCEPT.match(line.strip()):
            # Check lines between Исключение and КонецПопытки
            j = i + 1
            found_code = False
            while j < len(lines):
                s = lines[j].strip()
                if _RE_END_TRY.match(s):
                    break
                if s and not _RE_COMMENT_LINE.match(lines[j]):
                    found_code = True
                    break
                j += 1
            if not found_code:
                has_empty_catch = True
                break

    # --- N+1 query detection ---
    has_n_plus_one = False
    in_loop = 0
    for line in lines:
        stripped = line.strip()
        if _RE_COMMENT_LINE.match(line):
            continue
        if _RE_LOOP_START.match(stripped):
            in_loop += 1
        elif _RE_NESTING_CLOSE.match(stripped) and in_loop > 0:
            in_loop -= 1
        if in_loop > 0 and _RE_QUERY.search(stripped):
            has_n_plus_one = True
            break

    # --- SELECT * ---
    # Remove string literals first for accuracy
    text_no_strings = _RE_STRING_LITERAL.sub('""', text)
    has_select_star = bool(_RE_SELECT_STAR.search(text_no_strings))

    # --- Magic numbers ---
    has_magic_numbers = False
    for line in lines:
        if _RE_COMMENT_LINE.match(line):
            continue
        line_no_str = _RE_STRING_LITERAL.sub('""', line)
        for m in _RE_MAGIC_NUMBER.finditer(line_no_str):
            val = int(m.group(1))
            if val > 2:
                has_magic_numbers = True
                break
        if has_magic_numbers:
            break

    # --- TODO/FIXME/HACK ---
    num_todo_fixme = 0
    for line in lines:
        if _RE_COMMENT_LINE.match(line):
            num_todo_fixme += len(_RE_TODO.findall(line))

    # --- Average identifier length ---
    ident_lengths: List[int] = []
    for line in lines:
        if _RE_COMMENT_LINE.match(line):
            continue
        m = _RE_ASSIGNMENT.match(line)
        if m:
            ident_lengths.append(len(m.group(1)))
    avg_identifier_length = (
        round(sum(ident_lengths) / len(ident_lengths), 2) if ident_lengths else 0.0
    )

    # --- Referenced objects ---
    referenced_objects = sorted(
        set(f"{m.group(1)}.{m.group(2)}" for m in _RE_METADATA_REF.finditer(text))
    )

    return {
        "module_path": rel_path.replace("\\", "/"),
        "module_type": module_type,
        "loc": loc,
        "cyclomatic_complexity": cyclomatic,
        "max_nesting": max_nesting,
        "doc_coverage": doc_coverage,
        "comment_density": comment_density,
        "has_module_header": has_module_header,
        "num_functions": num_functions,
        "avg_func_length": avg_func_length,
        "export_ratio": export_ratio,
        "avg_identifier_length": avg_identifier_length,
        "has_error_handling": has_error_handling,
        "has_n_plus_one": has_n_plus_one,
        "has_select_star": has_select_star,
        "has_empty_catch": has_empty_catch,
        "has_magic_numbers": has_magic_numbers,
        "has_deep_nesting": has_deep_nesting,
        "num_todo_fixme": num_todo_fixme,
        "referenced_objects": referenced_objects,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def run_extraction(
    config_path: Path,
    output: Optional[Path] = None,
    workers: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Scan all .bsl files under config_path and extract features.

    Returns list of feature dicts and optionally writes NDJSON to output.
    """
    config_path = config_path.resolve()
    bsl_files = sorted(config_path.rglob("*.bsl"))

    if not bsl_files:
        print(f"No .bsl files found under {config_path}", file=sys.stderr)
        return []

    print(f"Found {len(bsl_files)} .bsl files, extracting features…", file=sys.stderr)

    args_list = [(str(f), str(config_path)) for f in bsl_files]
    n_workers = workers or min(cpu_count(), 8)

    results: List[Dict[str, Any]] = []
    with Pool(processes=n_workers) as pool:
        for feat in pool.imap_unordered(_extract_features, args_list, chunksize=64):
            if feat is not None:
                results.append(feat)

    results.sort(key=lambda r: r["module_path"])

    print(f"Extracted features for {len(results)} modules.", file=sys.stderr)

    # Write output
    out_stream = open(output, "w", encoding="utf-8") if output else sys.stdout
    try:
        for r in results:
            out_stream.write(json.dumps(r, ensure_ascii=False) + "\n")
    finally:
        if output:
            out_stream.close()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BSL feature extraction")
    parser.add_argument("--config-path", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    run_extraction(args.config_path, args.output)
