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
_LEFT_JOIN_ALIAS_RE = re.compile(
    r"\bЛЕВОЕ(?:\s+ВНЕШНЕЕ)?\s+СОЕДИНЕНИЕ\b[\s\S]{0,240}?\bКАК\s+([A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё]*)",
    re.IGNORECASE,
)
_EN_LEFT_JOIN_ALIAS_RE = re.compile(
    r"\bLEFT(?:\s+OUTER)?\s+JOIN\b[\s\S]{0,240}?\bAS\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
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
_QUERY_SEPARATOR_RE = re.compile(r"^\s*\|?\s*;\s*$")
# A new query starts at a ВЫБРАТЬ / SELECT that opens a statement. We allow the
# usual 1C query-text noise before the keyword: leading whitespace, the ``|``
# query-text continuation prefix, and the opening quote of ``Новый Запрос("…``.
# The trailing ``\b`` keeps ВЫБОР (CASE) from being mistaken for ВЫБРАТЬ. The
# optional РАЗРЕШЕННЫЕ / ALLOWED modifier is tolerated so it stays part of the
# same query region. Used to scope LEFT JOIN aliases per query (not per method)
# so an alias from one query cannot bleed into the next one assembled in the
# same string region.
_QUERY_START_RE = re.compile(
    r"^\s*[\"|]?\s*\|?\s*(?:ВЫБРАТЬ|SELECT)\b(?:\s+(?:РАЗРЕШЕННЫЕ|ALLOWED)\b)?",
    re.IGNORECASE,
)
_NULL_GUARD_RE = re.compile(
    r"(ЕстьNULL|ЕСТЬNULL|ISNULL|COALESCE|\bЕСТЬ\s+NULL\b|\bНЕ\s+ЕСТЬ\s+NULL\b|\bIS\s+NULL\b|\bIS\s+NOT\s+NULL\b)",
    re.IGNORECASE,
)
_NULL_FUNC_TOKENS = r"(?:ЕстьNULL|ЕСТЬNULL|ISNULL|COALESCE)"
_NULL_CHECK_TOKENS = r"(?:ЕСТЬ\s+NULL|НЕ\s+ЕСТЬ\s+NULL|IS\s+NULL|IS\s+NOT\s+NULL)"
_FIELD_NAME_RE = r"[A-Za-zА-Яа-яЁё_][\wА-Яа-яЁё]*"
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


def _field_ref_pattern(alias: str, field: str) -> str:
    return rf"(?<![\wА-Яа-яЁё.]){re.escape(alias)}\s*\.\s*{re.escape(field)}(?![\wА-Яа-яЁё])"


def _field_has_null_guard(line: str, alias: str, field: str) -> bool:
    field_ref = _field_ref_pattern(alias, field)
    return bool(
        re.search(rf"{_NULL_FUNC_TOKENS}\s*\(\s*{field_ref}", line, re.IGNORECASE)
        or re.search(rf"{field_ref}\s+{_NULL_CHECK_TOKENS}", line, re.IGNORECASE)
        or re.search(rf"\bНЕ\s+{field_ref}\s+ЕСТЬ\s+NULL\b", line, re.IGNORECASE)
        or re.search(rf"\bNOT\s+{field_ref}\s+IS\s+NULL\b", line, re.IGNORECASE)
    )


def _field_has_case_null_guard(lines: list[str], line_number: int, alias: str, field: str) -> bool:
    window: list[str] = []
    saw_case = False
    for cursor in range(line_number - 1, max(0, line_number - 9), -1):
        previous = lines[cursor - 1]
        if _QUERY_SEPARATOR_RE.match(previous.strip()):
            break
        window.insert(0, previous)
        if re.search(r"\b(ВЫБОР|CASE)\b", previous, re.IGNORECASE):
            saw_case = True
            break
    if not saw_case:
        return False
    for cursor in range(line_number, min(len(lines), line_number + 8) + 1):
        current = lines[cursor - 1]
        window.append(current)
        if re.search(r"\b(КОНЕЦ|END)\b", current, re.IGNORECASE):
            break
    text = "\n".join(window)
    return bool(re.search(r"\b(КОГДА|WHEN)\b", text, re.IGNORECASE)) and _field_has_null_guard(text, alias, field)


def _same_query_block(lines: list[str], left_line: int, right_line: int) -> bool:
    """Whether two lines belong to the same individual query.

    A method may assemble two or more separate queries as text and run them in a
    batch. The LEFT JOIN alias of one query must not be allowed to satisfy or
    trigger the rule in another, so query boundaries are detected per query, not
    per method. A boundary is either the existing ``;`` separator (a ``;`` alone
    on a line) or the start of a new query (a ``ВЫБРАТЬ`` / ``SELECT`` that opens
    a statement). The first line of the scanned range is the region header, so a
    query-start there is skipped — only a separator or a *new* query-start that
    appears strictly after it splits the two lines into different queries.
    """

    start = min(left_line, right_line)
    end = max(left_line, right_line)
    for offset, line in enumerate(lines[start - 1 : end]):
        if _QUERY_SEPARATOR_RE.match(line.strip()):
            return False
        if offset > 0 and _QUERY_START_RE.match(line):
            return False
    return True


def _query_region_is_anchored(lines: list[str], line_number: int) -> bool:
    """Whether ``line_number`` sits inside a confidently bounded query region.

    The rule is deliberately conservative on ambiguity: it only raises when the
    query the field belongs to can be located. Scanning upward from the field we
    must reach a ``ВЫБРАТЬ`` / ``SELECT`` that opens the query before hitting a
    ``;`` separator or the top of the source. If a region cannot be anchored to a
    query head — e.g. a fragment of a dynamically assembled query whose
    ``ВЫБРАТЬ`` is concatenated elsewhere — we prefer NOT to flag rather than risk
    a false HIGH on text that may not even be one query.
    """

    for cursor in range(line_number, 0, -1):
        line = lines[cursor - 1]
        if _QUERY_START_RE.match(line):
            return True
        # A separator above the field with no query head in between means the
        # region opened outside this textual span; treat it as unanchored.
        if cursor < line_number and _QUERY_SEPARATOR_RE.match(line.strip()):
            return False
    return False


def _is_join_condition_continuation(lines: list[str], line_number: int) -> bool:
    ru_and = "\u0418"
    ru_on = "\u041f\u041e"
    ru_left = "\u041b\u0415\u0412\u041e\u0415"
    ru_where = "\u0413\u0414\u0415"
    ru_group = "\u0421\u0413\u0420\u0423\u041f\u041f\u0418\u0420\u041e\u0412\u0410\u0422\u042c"
    ru_select = "\u0412\u042b\u0411\u0420\u0410\u0422\u042c"
    ru_from = "\u0418\u0417"
    line = lines[line_number - 1]
    if not re.search(rf"^\s*\|?\s*({ru_and}|AND|ИЛИ|OR)\b", line, re.IGNORECASE):
        return False
    for previous in reversed(lines[: line_number - 1]):
        if _QUERY_SEPARATOR_RE.match(previous.strip()):
            return False
        if re.search(rf"\b({ru_on}|ON)\b", previous, re.IGNORECASE):
            return True
        if re.search(
            rf"\b({ru_left}|LEFT|{ru_where}|WHERE|{ru_group}|GROUP|{ru_select}|SELECT|{ru_from}|FROM)\b",
            previous,
            re.IGNORECASE,
        ):
            return False
    return False


def _line_at_pos(code: str, pos: int) -> str:
    start = code.rfind("\n", 0, pos) + 1
    end = code.find("\n", pos)
    if end == -1:
        end = len(code)
    return code[start:end]


def _line_is_comment_at_pos(code: str, pos: int) -> bool:
    return _line_at_pos(code, pos).lstrip().startswith("//")


def _alias_field_matches(line: str, alias: str) -> list[re.Match[str]]:
    return list(
        re.finditer(
            rf"(?<![\wА-Яа-яЁё.]){re.escape(alias)}\.({_FIELD_NAME_RE})",
            line,
            re.IGNORECASE,
        )
    )


def _emit_join_field_null_guard(
    diagnostics: list[BSLDiagnostic],
    *,
    line: int,
    alias: str,
    field: str,
    join_line: int,
) -> None:
    _add(
        diagnostics,
        severity="high",
        code="join-field-null-guard",
        message=(
            "Field from LEFT JOIN is used without an explicit NULL guard. "
            "Use ЕстьNULL(), an ЕСТЬ NULL branch, or make the join inner if absence is impossible."
        ),
        line=line,
        details={
            "alias": alias,
            "field": field,
            "field_ref": f"{alias}.{field}",
            "join_line": join_line,
            "risk": (
                "If the joined row is missing, this field becomes NULL and can change totals, "
                "grouping, filters or presentation."
            ),
            "safe_options": [
                f"ЕстьNULL({alias}.{field}, <default>)",
                f"ВЫБОР КОГДА {alias}.{field} ЕСТЬ NULL ТОГДА <when_missing> ИНАЧЕ {alias}.{field} КОНЕЦ",
                "ВНУТРЕННЕЕ СОЕДИНЕНИЕ, если отсутствие связанной строки недопустимо",
            ],
            "test_expectations": [
                "Case with a missing joined row returns the agreed default or branch result.",
                "Case with an existing joined row keeps the previous value.",
                "Before/after comparison confirms row count, grouping and totals did not change unexpectedly.",
            ],
            "caveat": (
                "Heuristic, line- and query-scoped within a single method: LEFT JOIN "
                "aliases are bounded to the individual query they appear in (split on "
                "ВЫБРАТЬ/SELECT and ';'), so this is not a definitive 1C verdict and may "
                "under-report across complex, dynamically assembled queries. Confirm "
                "against the actual query the field belongs to."
            ),
        },
    )


def _mixed_left_join_null_guard_line(
    line: str,
    line_number: int,
    aliases: dict[str, int],
    lines: list[str],
    diagnostics: list[BSLDiagnostic],
) -> None:
    emitted: set[tuple[str, str]] = set()
    for alias, join_line in aliases.items():
        if not _same_query_block(lines, line_number, join_line):
            continue
        if not _query_region_is_anchored(lines, line_number):
            continue
        field_matches = _alias_field_matches(line, alias)
        for field_match in field_matches:
            field = field_match.group(1)
            key = (alias.casefold(), field.casefold())
            if (
                key in emitted
                or _field_has_null_guard(line, alias, field)
                or _field_has_case_null_guard(lines, line_number, alias, field)
            ):
                continue
            emitted.add(key)
            _emit_join_field_null_guard(
                diagnostics,
                line=line_number,
                alias=alias,
                field=field,
                join_line=join_line,
            )


def _left_join_null_guards(code: str, lines: list[str], diagnostics: list[BSLDiagnostic]) -> None:
    aliases: dict[str, int] = {}
    for pattern in (_LEFT_JOIN_ALIAS_RE, _EN_LEFT_JOIN_ALIAS_RE):
        for match in pattern.finditer(code):
            if _line_is_comment_at_pos(code, match.start()):
                continue
            aliases.setdefault(match.group(1), _line_number(code, match.start()))
    if not aliases:
        return

    emitted: set[tuple[str, int]] = set()
    for idx, line in enumerate(lines, start=1):
        if re.search(r"\b(ЛЕВОЕ|LEFT)\b", line, re.IGNORECASE):
            continue
        if re.search(r"\b(ПО|ON)\b", line, re.IGNORECASE):
            continue
        if _is_join_condition_continuation(lines, idx):
            continue
        if _NULL_GUARD_RE.search(line):
            _mixed_left_join_null_guard_line(line, idx, aliases, lines, diagnostics)
            continue
        for alias, join_line in aliases.items():
            if not _same_query_block(lines, idx, join_line):
                continue
            if not _query_region_is_anchored(lines, idx):
                continue
            field_match = next(iter(_alias_field_matches(line, alias)), None)
            if not field_match or (alias.casefold(), idx) in emitted:
                continue
            field = field_match.group(1)
            if _field_has_case_null_guard(lines, idx, alias, field):
                continue
            emitted.add((alias.casefold(), idx))
            _emit_join_field_null_guard(
                diagnostics,
                line=idx,
                alias=alias,
                field=field,
                join_line=join_line,
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
    _left_join_null_guards(code, lines, diagnostics)

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
