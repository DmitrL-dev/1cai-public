"""BSL-ориентированные домены для Micro-Model Swarm.

5 специализированных доменов для анализа 1С:Предприятие BSL-кода:
- BSL Pattern Detector — классификация паттернов кода
- BSL Code Quality — оценка качества кода
- 1C Query Optimizer — обнаружение проблем в запросах
- BSL Error Predictor — предсказание ошибок
- Config Similarity — embedding distance для конфигураций
"""

from __future__ import annotations

import re
from typing import Any

from src.micro_swarm.domains import DomainConfig, FeatureSpec, NormMethod

# ──────────────────────────────────────────
# Shared BSL regex patterns
# ──────────────────────────────────────────

_RE_PROCEDURE = re.compile(r"\bПроцедура\s+\w+\s*\(", re.IGNORECASE)
_RE_FUNCTION = re.compile(r"\bФункция\s+\w+\s*\(", re.IGNORECASE)
_RE_END_PROC = re.compile(r"\bКонецПроцедуры\b", re.IGNORECASE)
_RE_END_FUNC = re.compile(r"\bКонецФункции\b", re.IGNORECASE)
_RE_EXPORT = re.compile(
    r"\b(Процедура|Функция)\s+\w+\s*\([^)]*\)\s*Экспорт\b", re.IGNORECASE
)
_RE_IF = re.compile(r"\bЕсли\b", re.IGNORECASE)
_RE_ELSEIF = re.compile(r"\bИначеЕсли\b", re.IGNORECASE)
_RE_FOR = re.compile(r"\bДля\b", re.IGNORECASE)
_RE_WHILE = re.compile(r"\bПока\b", re.IGNORECASE)
_RE_TRY = re.compile(r"\bПопытка\b", re.IGNORECASE)
_RE_EXCEPT = re.compile(r"\bИсключение\b", re.IGNORECASE)
_RE_QUERY = re.compile(r"Запрос\.Текст\s*=", re.IGNORECASE)
_RE_NEW_QUERY = re.compile(r"Новый\s+Запрос", re.IGNORECASE)
_RE_VAR = re.compile(r"\bПерем\s+\w+", re.IGNORECASE)

# Form handler patterns
_FORM_HANDLERS = [
    r"\bПриСозданииНаСервере\b",
    r"\bПриОткрытии\b",
    r"\bПередЗаписью\b",
    r"\bПриЗаписиНаСервере\b",
    r"\bПослеЗаписиНаСервере\b",
    r"\bОбработкаЗаполнения\b",
    r"\bПриИзменении\b",
    r"\bПриНажатии\b",
]
_RE_FORM_HANDLERS = [re.compile(p, re.IGNORECASE) for p in _FORM_HANDLERS]

# Print form patterns
_RE_PRINT_FORM = re.compile(
    r"\b(ТабличныйДокумент|ПолучитьМакет|Вывести|ПечатнаяФорма)\b",
    re.IGNORECASE,
)

# HTTP/Web patterns
_RE_HTTP = re.compile(
    r"\b(HTTPСоединение|HTTPЗапрос|ОтправитьHTTP|WSСоединение|ВебСервис)\b",
    re.IGNORECASE,
)

# Scheduled job patterns
_RE_SCHEDULE = re.compile(
    r"\b(РегламентноеЗадание|ФоновоеЗадание|ОбработчикОповещения)\b",
    re.IGNORECASE,
)

# Documentation comment patterns
_RE_DOC = re.compile(r"//\s*(Функция|Процедура|Параметры:|Возвращаемое значение:)")

# Code smell patterns
_RE_MAGIC_NUMBER = re.compile(r"(?<!=)\s+\b\d{2,}\b(?!\s*[),;\n])")
_RE_STRING_CONCAT = re.compile(r'\+\s*"')
_RE_DIVISION = re.compile(r"\s/\s")
_RE_TYPE_CHECK = re.compile(r"\bТипЗнч\b", re.IGNORECASE)

# Query problem patterns
_RE_SELECT_STAR = re.compile(r"\bВЫБРАТЬ\s+\*", re.IGNORECASE)
_RE_SUBQUERY = re.compile(r"\(\s*ВЫБРАТЬ\b", re.IGNORECASE)
_RE_TEMP_TABLE = re.compile(r"\bПОМЕСТИТЬ\b", re.IGNORECASE)
_RE_JOIN = re.compile(
    r"\b(ЛЕВОЕ|ПРАВОЕ|ПОЛНОЕ|ВНУТРЕННЕЕ)?\s*СОЕДИНЕНИЕ\b", re.IGNORECASE
)
_RE_INDEX = re.compile(r"\bИНДЕКСИРОВАТЬ\b", re.IGNORECASE)
_RE_WHERE = re.compile(r"\bГДЕ\b", re.IGNORECASE)
_RE_ORDER = re.compile(r"\bУПОРЯДОЧИТЬ\b", re.IGNORECASE)
_RE_GROUP = re.compile(r"\bСГРУППИРОВАТЬ\b", re.IGNORECASE)


def _count_re(pattern: re.Pattern[str], text: str) -> int:
    """Count regex pattern matches in text."""
    return len(pattern.findall(text))


def _count_nesting_depth(code: str) -> int:
    """Calculate max nesting depth of control structures."""
    depth = 0
    max_depth = 0
    openers = re.compile(r"\b(Если|Для|Пока|Попытка)\b", re.IGNORECASE)
    closers = re.compile(r"\b(КонецЕсли|КонецЦикла|КонецПопытки)\b", re.IGNORECASE)
    for line in code.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        depth += len(openers.findall(stripped))
        depth -= len(closers.findall(stripped))
        if depth < 0:
            depth = 0
        if depth > max_depth:
            max_depth = depth
    return max_depth


def _extract_query_texts(code: str) -> list[str]:
    """Extract query text strings from BSL code."""
    queries: list[str] = []
    pattern = re.compile(
        r'(?:Запрос\.Текст|ТекстЗапроса)\s*=\s*"(.*?)"',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(code):
        queries.append(m.group(1))
    # Also handle multi-line query strings with |
    pattern_ml = re.compile(
        r'(?:Запрос\.Текст|ТекстЗапроса)\s*=\s*\n\s*"\s*\|(.+?)(?:";|\|")',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern_ml.finditer(code):
        queries.append(m.group(1))
    return queries


# ──────────────────────────────────────────
# Domain 1: BSL Pattern Detector
# ──────────────────────────────────────────


def extract_bsl_pattern_features(code: str) -> dict[str, float]:
    """Extract features for BSL pattern classification.

    Classifies code into patterns: form handler, DB query,
    print form, HTTP/web service, scheduled job.
    """
    proc_count = _count_re(_RE_PROCEDURE, code)
    func_count = _count_re(_RE_FUNCTION, code)
    export_count = _count_re(_RE_EXPORT, code)
    total_routines = proc_count + func_count

    return {
        "has_form_handler": float(any(p.search(code) for p in _RE_FORM_HANDLERS)),
        "has_db_query": float(
            bool(_RE_QUERY.search(code)) or bool(_RE_NEW_QUERY.search(code))
        ),
        "has_print_form": float(bool(_RE_PRINT_FORM.search(code))),
        "has_http_call": float(bool(_RE_HTTP.search(code))),
        "has_schedule_job": float(bool(_RE_SCHEDULE.search(code))),
        "procedure_count": float(proc_count),
        "function_count": float(func_count),
        "export_ratio": (float(export_count) / max(total_routines, 1)),
    }


BSL_PATTERN_DOMAIN = DomainConfig(
    name="bsl_pattern",
    description="Классификация BSL-паттернов (форма, запрос, печать, HTTP, регламент)",
    features=(
        FeatureSpec("has_form_handler", NormMethod.NONE),
        FeatureSpec("has_db_query", NormMethod.NONE),
        FeatureSpec("has_print_form", NormMethod.NONE),
        FeatureSpec("has_http_call", NormMethod.NONE),
        FeatureSpec("has_schedule_job", NormMethod.NONE),
        FeatureSpec("procedure_count", NormMethod.MIN_MAX, 0.0, 30.0),
        FeatureSpec("function_count", NormMethod.MIN_MAX, 0.0, 30.0),
        FeatureSpec("export_ratio", NormMethod.NONE),
    ),
)


# ──────────────────────────────────────────
# Domain 2: BSL Code Quality
# ──────────────────────────────────────────


def extract_bsl_quality_features(code: str) -> dict[str, float]:
    """Extract code quality features from BSL code.

    Evaluates: complexity, documentation coverage, nesting,
    coupling (external calls), code smell indicators.
    """
    lines = [
        l for l in code.split("\n") if l.strip() and not l.strip().startswith("//")
    ]
    loc = max(len(lines), 1)

    proc_count = _count_re(_RE_PROCEDURE, code)
    func_count = _count_re(_RE_FUNCTION, code)
    total_routines = proc_count + func_count

    # Complexity per routine
    if_count = _count_re(_RE_IF, code)
    elseif_count = _count_re(_RE_ELSEIF, code)
    for_count = _count_re(_RE_FOR, code)
    while_count = _count_re(_RE_WHILE, code)
    try_count = _count_re(_RE_TRY, code)
    total_complexity = (
        total_routines + if_count + elseif_count + for_count + while_count + try_count
    )

    avg_complexity = float(total_complexity) / max(total_routines, 1)
    # Approximation without per-routine parsing
    max_complexity = avg_complexity * 1.5

    # Documentation coverage
    doc_comments = _count_re(_RE_DOC, code)
    doc_coverage = float(doc_comments) / max(total_routines, 1)

    # Nesting depth
    nesting = _count_nesting_depth(code)

    # Coupling — external module calls (ОбщийМодуль.Метод pattern)
    coupling = len(re.findall(r"\w+\.\w+\(", code))

    # Dead code — unreachable after Возврат
    dead_lines = len(re.findall(r"Возврат\s*;[^К]*\S", code, re.IGNORECASE))

    return {
        "avg_complexity": avg_complexity,
        "max_complexity": max_complexity,
        "loc": float(loc),
        "functions_per_loc": float(total_routines) / loc,
        "doc_coverage": min(doc_coverage, 1.0),
        "nesting_depth": float(nesting),
        "coupling_score": float(coupling),
        "dead_code_ratio": float(dead_lines) / loc,
    }


BSL_QUALITY_DOMAIN = DomainConfig(
    name="bsl_quality",
    description="Оценка качества BSL-кода (сложность, документирование, связность)",
    features=(
        FeatureSpec("avg_complexity", NormMethod.MIN_MAX, 0.0, 20.0),
        FeatureSpec("max_complexity", NormMethod.MIN_MAX, 0.0, 30.0),
        FeatureSpec("loc", NormMethod.MIN_MAX, 0.0, 5000.0),
        FeatureSpec("functions_per_loc", NormMethod.MIN_MAX, 0.0, 0.1),
        FeatureSpec("doc_coverage", NormMethod.NONE),
        FeatureSpec("nesting_depth", NormMethod.MIN_MAX, 0.0, 10.0),
        FeatureSpec("coupling_score", NormMethod.MIN_MAX, 0.0, 50.0),
        FeatureSpec("dead_code_ratio", NormMethod.NONE),
    ),
)


# ──────────────────────────────────────────
# Domain 3: 1C Query Optimizer
# ──────────────────────────────────────────


def extract_query_optimizer_features(code: str) -> dict[str, float]:
    """Extract features for 1C query optimization analysis.

    Detects: N+1 queries (query in loop), unnecessary JOINs,
    missing indexes, SELECT *, subqueries, temp tables.
    """
    queries = _extract_query_texts(code)
    query_count = len(queries) + _count_re(_RE_NEW_QUERY, code)
    if query_count == 0:
        query_count = max(_count_re(_RE_QUERY, code), 0)

    # N+1 detection: query inside loop
    loop_pattern = re.compile(
        r"\b(Для|Пока)\b.*?(Запрос\.Текст|Новый\s+Запрос)",
        re.IGNORECASE | re.DOTALL,
    )
    has_n_plus_one = float(bool(loop_pattern.search(code)))

    # Analyze query texts
    all_query_text = " ".join(queries)
    join_count = _count_re(_RE_JOIN, all_query_text)
    has_unnecessary_join = float(join_count > 3)  # Heuristic: >3 JOINs suspect

    has_no_index = float(
        bool(queries)
        and not bool(_RE_INDEX.search(all_query_text))
        and bool(_RE_WHERE.search(all_query_text))
    )

    has_star_select = float(bool(_RE_SELECT_STAR.search(all_query_text)))
    has_subquery = float(bool(_RE_SUBQUERY.search(all_query_text)))
    has_temp_table = float(bool(_RE_TEMP_TABLE.search(all_query_text)))

    query_lengths = [len(q) for q in queries] if queries else [0]
    query_length_avg = sum(query_lengths) / max(len(query_lengths), 1)

    return {
        "query_count": float(max(query_count, len(queries))),
        "has_n_plus_one": has_n_plus_one,
        "has_unnecessary_join": has_unnecessary_join,
        "has_no_index": has_no_index,
        "query_length_avg": query_length_avg,
        "has_star_select": has_star_select,
        "has_subquery": has_subquery,
        "has_temp_table": has_temp_table,
    }


QUERY_OPTIMIZER_DOMAIN = DomainConfig(
    name="query_optimizer",
    description="Обнаружение проблем в запросах 1С (N+1, SELECT *, отсутствие индексов)",
    features=(
        FeatureSpec("query_count", NormMethod.MIN_MAX, 0.0, 20.0),
        FeatureSpec("has_n_plus_one", NormMethod.NONE),
        FeatureSpec("has_unnecessary_join", NormMethod.NONE),
        FeatureSpec("has_no_index", NormMethod.NONE),
        FeatureSpec("query_length_avg", NormMethod.MIN_MAX, 0.0, 2000.0),
        FeatureSpec("has_star_select", NormMethod.NONE),
        FeatureSpec("has_subquery", NormMethod.NONE),
        FeatureSpec("has_temp_table", NormMethod.NONE),
    ),
)


# ──────────────────────────────────────────
# Domain 4: BSL Error Predictor
# ──────────────────────────────────────────


def extract_error_features(code: str) -> dict[str, float]:
    """Extract features for BSL error prediction.

    Detects patterns correlated with runtime errors:
    empty catch blocks, unguarded division, magic numbers,
    excessive string concatenation, deep nesting.
    """
    try_count = _count_re(_RE_TRY, code)

    # Empty catch: Исключение followed by КонецПопытки with nothing in between
    empty_catch = len(
        re.findall(
            r"Исключение\s*;\s*КонецПопытки",
            code,
            re.IGNORECASE,
        )
    )

    # Unguarded division (division without prior zero check)
    divisions = _count_re(_RE_DIVISION, code)
    type_checks = _count_re(_RE_TYPE_CHECK, code)

    # Magic numbers (>= 2 digits, not in common positions)
    magic_numbers = _count_re(_RE_MAGIC_NUMBER, code)

    # String concatenation anti-pattern
    string_concats = _count_re(_RE_STRING_CONCAT, code)

    # Variable reuse (Перем + assignment to same name)
    var_count = _count_re(_RE_VAR, code)

    # Nesting depth
    nesting = _count_nesting_depth(code)

    lines = code.split("\n")
    loc = max(len(lines), 1)

    return {
        "try_catch_ratio": float(try_count) / max(loc, 1) * 100,
        "has_empty_catch": float(empty_catch > 0),
        "has_unguarded_division": float(divisions > type_checks),
        "variable_reuse_count": float(var_count),
        "magic_number_count": float(magic_numbers),
        "has_type_check": float(type_checks > 0),
        "string_concat_count": float(string_concats),
        "nested_if_depth": float(nesting),
    }


ERROR_PREDICTOR_DOMAIN = DomainConfig(
    name="error_predictor",
    description="Предсказание ошибок в BSL-коде (пустые catch, деление без проверки)",
    features=(
        FeatureSpec("try_catch_ratio", NormMethod.MIN_MAX, 0.0, 10.0),
        FeatureSpec("has_empty_catch", NormMethod.NONE),
        FeatureSpec("has_unguarded_division", NormMethod.NONE),
        FeatureSpec("variable_reuse_count", NormMethod.MIN_MAX, 0.0, 20.0),
        FeatureSpec("magic_number_count", NormMethod.MIN_MAX, 0.0, 30.0),
        FeatureSpec("has_type_check", NormMethod.NONE),
        FeatureSpec("string_concat_count", NormMethod.MIN_MAX, 0.0, 20.0),
        FeatureSpec("nested_if_depth", NormMethod.MIN_MAX, 0.0, 10.0),
    ),
)


# ──────────────────────────────────────────
# Domain 5: Config Similarity
# ──────────────────────────────────────────


def extract_config_features(config_data: dict[str, Any]) -> dict[str, float]:
    """Extract features from 1C configuration metadata for similarity comparison.

    Uses MicroModel embedding for cosine distance between configs.

    Args:
        config_data: dict with keys like module_count, role_count, etc.
    """
    return {
        "module_count": float(config_data.get("module_count", 0)),
        "role_count": float(config_data.get("role_count", 0)),
        "subsystem_depth": float(config_data.get("subsystem_depth", 0)),
        "form_count": float(config_data.get("form_count", 0)),
        "command_count": float(config_data.get("command_count", 0)),
        "template_count": float(config_data.get("template_count", 0)),
        "scheduled_job_count": float(config_data.get("scheduled_job_count", 0)),
        "attr_count": float(config_data.get("attr_count", 0)),
    }


CONFIG_SIMILARITY_DOMAIN = DomainConfig(
    name="config_similarity",
    description="Embedding distance для сравнения конфигураций 1С",
    features=(
        FeatureSpec("module_count", NormMethod.MIN_MAX, 0.0, 500.0),
        FeatureSpec("role_count", NormMethod.MIN_MAX, 0.0, 100.0),
        FeatureSpec("subsystem_depth", NormMethod.MIN_MAX, 0.0, 10.0),
        FeatureSpec("form_count", NormMethod.MIN_MAX, 0.0, 1000.0),
        FeatureSpec("command_count", NormMethod.MIN_MAX, 0.0, 500.0),
        FeatureSpec("template_count", NormMethod.MIN_MAX, 0.0, 200.0),
        FeatureSpec("scheduled_job_count", NormMethod.MIN_MAX, 0.0, 50.0),
        FeatureSpec("attr_count", NormMethod.MIN_MAX, 0.0, 5000.0),
    ),
)
