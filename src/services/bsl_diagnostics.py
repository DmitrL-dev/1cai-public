"""Local BSL diagnostics used when bsl-language-server is not available.

The checks are intentionally deterministic and explainable. They do not try to
replace the full 1C-Syntax rule set, but they give the product useful offline
review coverage in closed contours where Docker/LSP may be unavailable.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class BSLDiagnostic:
    source: str
    severity: str
    code: str
    message: str
    line: int
    details: dict[str, Any]


_SOURCE = "bsl-diagnostics:fallback"

_PROC_RE = re.compile(r"^\s*(Процедура|Функция)\s+([A-Za-zА-Яа-яЁё0-9_]+)", re.IGNORECASE)
_SELECT_STAR_RE = re.compile(r"\bВЫБРАТЬ\s+\*", re.IGNORECASE)
_DYNAMIC_EXEC_RE = re.compile(r"(?<![.\wА-Яа-яЁё])Выполнить\s*\(", re.IGNORECASE)
_PRIVILEGED_MODE_RE = re.compile(
    r"УстановитьПривилегированныйРежим\s*\(\s*Истина\s*\)", re.IGNORECASE
)
_LOOP_START_RE = re.compile(r"^\s*(Для(\s+Каждого)?|Пока)\b", re.IGNORECASE)
_LOOP_END_RE = re.compile(r"^\s*КонецЦикла\b", re.IGNORECASE)
_BLOCK_START_RE = re.compile(r"^\s*(Если|Для(\s+Каждого)?|Пока|Попытка)\b", re.IGNORECASE)
_BLOCK_END_RE = re.compile(r"^\s*(КонецЕсли|КонецЦикла|КонецПопытки)\b", re.IGNORECASE)
_QUERY_EXEC_RE = re.compile(r"(Новый\s+Запрос|Запрос\s*\.|\.Выполнить\s*\()", re.IGNORECASE)
_OBJECT_REF_RE = re.compile(
    r"\b(Справочник|Справочники|Документ|Документы|РегистрСведений|РегистрыСведений|"
    r"РегистрНакопления|РегистрыНакопления|РегистрБухгалтерии|РегистрыБухгалтерии|"
    r"ПланСчетов|ПланыСчетов|Перечисление|Перечисления)\s*\.",
    re.IGNORECASE,
)
_MAGIC_NUMBER_RE = re.compile(r"(?<![\w.])(\d{2,})(?![\w.])")
_COMMENT_RE = re.compile(r"^\s*//")
_EN_PROC_RE = re.compile(r"^\s*(Procedure|Function)\s+([A-Za-z][A-Za-z0-9_]*)", re.IGNORECASE)
_EN_SELECT_STAR_RE = re.compile(r"\bSELECT\s+\*", re.IGNORECASE)
_EN_DYNAMIC_EXEC_RE = re.compile(r"(?<![.\w])Execute\s*\(", re.IGNORECASE)
_EN_PRIVILEGED_MODE_RE = re.compile(r"SetPrivilegedMode\s*\(\s*True\s*\)", re.IGNORECASE)
_EN_EXCEPTION_RE = re.compile(r"^\s*Except\b", re.IGNORECASE)
_EN_END_TRY_RE = re.compile(r"^\s*EndTry\b", re.IGNORECASE)
_EN_LOOP_START_RE = re.compile(r"^\s*(For(\s+Each)?|While)\b", re.IGNORECASE)
_EN_LOOP_END_RE = re.compile(r"^\s*EndDo\b", re.IGNORECASE)
_EN_BLOCK_START_RE = re.compile(r"^\s*(If|For(\s+Each)?|While|Try)\b", re.IGNORECASE)
_EN_BLOCK_END_RE = re.compile(r"^\s*(EndIf|EndDo|EndTry)\b", re.IGNORECASE)
_EN_QUERY_EXEC_RE = re.compile(r"(New\s+Query|Query\s*\.|\.Execute\s*\()", re.IGNORECASE)
_EN_OBJECT_REF_RE = re.compile(
    r"\b(Catalog|Catalogs|Document|Documents|InformationRegister|InformationRegisters|"
    r"AccumulationRegister|AccumulationRegisters|AccountingRegister|AccountingRegisters|"
    r"ChartOfAccounts|ChartsOfAccounts|Enum|Enums)\s*\.",
    re.IGNORECASE,
)


def _line_number(code: str, pos: int) -> int:
    return code.count("\n", 0, pos) + 1


def _is_code_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("//")


def _add(
    diagnostics: list[BSLDiagnostic],
    *,
    severity: str,
    code: str,
    message: str,
    line: int,
    details: dict[str, Any] | None = None,
) -> None:
    diagnostics.append(
        BSLDiagnostic(
            source=_SOURCE,
            severity=severity,
            code=code,
            message=message,
            line=line,
            details=details or {},
        )
    )


def _empty_catches(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    for idx, line in enumerate(lines):
        if not re.match(r"^\s*Исключение\b", line, re.IGNORECASE):
            continue

        has_code = False
        comments = 0
        cursor = idx + 1
        while cursor < len(lines):
            current = lines[cursor]
            if re.match(r"^\s*КонецПопытки\b", current, re.IGNORECASE):
                if not has_code:
                    severity = "high" if comments == 0 else "medium"
                    _add(
                        diagnostics,
                        severity=severity,
                        code="empty-catch",
                        message="Empty exception handler hides failures and complicates support.",
                        line=idx + 1,
                        details={"comment_lines": comments},
                    )
                break
            if _is_code_line(current):
                has_code = True
            elif _COMMENT_RE.match(current):
                comments += 1
            cursor += 1


def _empty_catches_english(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    for idx, line in enumerate(lines):
        if not _EN_EXCEPTION_RE.match(line):
            continue

        has_code = False
        comments = 0
        cursor = idx + 1
        while cursor < len(lines):
            current = lines[cursor]
            if _EN_END_TRY_RE.match(current):
                if not has_code:
                    severity = "high" if comments == 0 else "medium"
                    _add(
                        diagnostics,
                        severity=severity,
                        code="empty-catch",
                        message="Empty exception handler hides failures and complicates support.",
                        line=idx + 1,
                        details={"comment_lines": comments},
                    )
                break
            if _is_code_line(current):
                has_code = True
            elif _COMMENT_RE.match(current):
                comments += 1
            cursor += 1


def _loop_queries(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    loop_stack: list[int] = []
    for idx, line in enumerate(lines, start=1):
        if _LOOP_START_RE.match(line):
            loop_stack.append(idx)
        if loop_stack and _QUERY_EXEC_RE.search(line):
            _add(
                diagnostics,
                severity="high",
                code="query-in-loop",
                message="Query execution or construction inside a loop may cause N+1 load.",
                line=idx,
                details={"loop_start": loop_stack[-1]},
            )
        if _LOOP_END_RE.match(line) and loop_stack:
            loop_stack.pop()


def _loop_queries_english(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    loop_stack: list[int] = []
    for idx, line in enumerate(lines, start=1):
        if _EN_LOOP_START_RE.match(line):
            loop_stack.append(idx)
        if loop_stack and _EN_QUERY_EXEC_RE.search(line):
            _add(
                diagnostics,
                severity="high",
                code="query-in-loop",
                message="Query execution or construction inside a loop may cause N+1 load.",
                line=idx,
                details={"loop_start": loop_stack[-1]},
            )
        if _EN_LOOP_END_RE.match(line) and loop_stack:
            loop_stack.pop()


def _nesting(lines: list[str], diagnostics: list[BSLDiagnostic], threshold: int) -> int:
    depth = 0
    max_depth = 0
    max_line = 1
    for idx, line in enumerate(lines, start=1):
        if _BLOCK_END_RE.match(line):
            depth = max(0, depth - 1)
        if _BLOCK_START_RE.match(line):
            depth += 1
            if depth > max_depth:
                max_depth = depth
                max_line = idx

    if max_depth >= threshold:
        _add(
            diagnostics,
            severity="medium",
            code="deep-nesting",
            message="Deep nesting makes BSL change impact harder to review and test.",
            line=max_line,
            details={"max_nesting": max_depth, "threshold": threshold},
        )
    return max_depth


def _nesting_english(lines: list[str], diagnostics: list[BSLDiagnostic], threshold: int) -> int:
    depth = 0
    max_depth = 0
    max_line = 1
    for idx, line in enumerate(lines, start=1):
        if _EN_BLOCK_END_RE.match(line):
            depth = max(0, depth - 1)
        if _EN_BLOCK_START_RE.match(line):
            depth += 1
            if depth > max_depth:
                max_depth = depth
                max_line = idx

    if max_depth >= threshold:
        _add(
            diagnostics,
            severity="medium",
            code="deep-nesting",
            message="Deep nesting makes BSL change impact harder to review and test.",
            line=max_line,
            details={"max_nesting": max_depth, "threshold": threshold},
        )
    return max_depth


def _undocumented_exports(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    for idx, line in enumerate(lines):
        if "Экспорт" not in line:
            continue
        match = _PROC_RE.match(line)
        if not match:
            continue

        previous = lines[idx - 1].strip() if idx > 0 else ""
        if not previous.startswith("//"):
            _add(
                diagnostics,
                severity="low",
                code="undocumented-export",
                message="Exported procedure/function has no leading comment.",
                line=idx + 1,
                details={"name": match.group(2), "kind": match.group(1)},
            )


def _undocumented_exports_english(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    for idx, line in enumerate(lines):
        if "Export" not in line:
            continue
        match = _EN_PROC_RE.match(line)
        if not match:
            continue

        previous = lines[idx - 1].strip() if idx > 0 else ""
        if not previous.startswith("//"):
            _add(
                diagnostics,
                severity="low",
                code="undocumented-export",
                message="Exported procedure/function has no leading comment.",
                line=idx + 1,
                details={"name": match.group(2), "kind": match.group(1)},
            )


def _magic_numbers(lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    ignored = {"60", "100", "1000"}
    for idx, line in enumerate(lines, start=1):
        if not _is_code_line(line):
            continue
        numbers = [n for n in _MAGIC_NUMBER_RE.findall(line) if n not in ignored]
        if len(numbers) >= 2:
            _add(
                diagnostics,
                severity="low",
                code="magic-numbers",
                message="Several numeric literals in one line should be named or explained.",
                line=idx,
                details={"numbers": numbers[:8]},
            )


def _is_procedure_decl(line: str) -> bool:
    return bool(
        re.match(r"^\s*Процедура\b", line, re.IGNORECASE)
        or re.match(r"^\s*Procedure\b", line, re.IGNORECASE)
    )


def _is_function_decl(line: str) -> bool:
    return bool(
        re.match(r"^\s*Функция\b", line, re.IGNORECASE)
        or re.match(r"^\s*Function\b", line, re.IGNORECASE)
    )


def _metadata_ref_count(code: str) -> int:
    return len(_OBJECT_REF_RE.findall(code)) + len(_EN_OBJECT_REF_RE.findall(code))


def analyze_bsl(
    code: str,
    *,
    module_path: str | None = None,
    max_nesting_threshold: int = 5,
) -> dict[str, Any]:
    """Analyze BSL code and return deterministic diagnostics plus metrics."""

    lines = code.splitlines()
    diagnostics: list[BSLDiagnostic] = []

    for pattern in (_SELECT_STAR_RE, _EN_SELECT_STAR_RE):
        for match in pattern.finditer(code):
            _add(
                diagnostics,
                severity="medium",
                code="select-star",
                message="SELECT * is fragile for enterprise configurations and metadata evolution.",
                line=_line_number(code, match.start()),
            )

    for pattern in (_DYNAMIC_EXEC_RE, _EN_DYNAMIC_EXEC_RE):
        for match in pattern.finditer(code):
            _add(
                diagnostics,
                severity="high",
                code="dynamic-execute",
                message="Dynamic Execute() complicates security review and static impact analysis.",
                line=_line_number(code, match.start()),
            )

    for pattern in (_PRIVILEGED_MODE_RE, _EN_PRIVILEGED_MODE_RE):
        for match in pattern.finditer(code):
            _add(
                diagnostics,
                severity="high",
                code="privileged-mode",
                message="Privileged mode requires explicit security justification.",
                line=_line_number(code, match.start()),
            )

    _empty_catches(lines, diagnostics)
    _empty_catches_english(lines, diagnostics)
    _loop_queries(lines, diagnostics)
    _loop_queries_english(lines, diagnostics)
    max_nesting = max(
        _nesting(lines, diagnostics, max_nesting_threshold),
        _nesting_english(lines, diagnostics, max_nesting_threshold),
    )
    _undocumented_exports(lines, diagnostics)
    _undocumented_exports_english(lines, diagnostics)
    _magic_numbers(lines, diagnostics)

    diagnostics = sorted(
        diagnostics,
        key=lambda item: (
            item.line,
            {"high": 0, "medium": 1, "low": 2}.get(item.severity, 9),
            item.code,
        ),
    )

    return {
        "engine": "fallback",
        "source": _SOURCE,
        "module_path": module_path,
        "diagnostics": [asdict(item) for item in diagnostics],
        "metrics": {
            "loc": sum(1 for line in lines if _is_code_line(line)),
            "procedures": sum(1 for line in lines if re.match(r"^\s*Процедура\b", line, re.IGNORECASE)),
            "functions": sum(1 for line in lines if re.match(r"^\s*Функция\b", line, re.IGNORECASE)),
            "max_nesting": max_nesting,
            "procedures": sum(1 for line in lines if _is_procedure_decl(line)),
            "functions": sum(1 for line in lines if _is_function_decl(line)),
            "metadata_refs": _metadata_ref_count(code),
        },
        "caveats": [
            "Fallback diagnostics are deterministic heuristics; full 1C-Syntax diagnostics need bsl-language-server.",
        ],
    }
