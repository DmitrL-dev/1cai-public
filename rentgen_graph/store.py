"""Рентген local engine — in-process query layer over data/rentgen.db (SQLite).

Replaces the Neo4j-backed GraphService with a zero-infrastructure store. Every
public method opens a short-lived read-only connection, so it is safe to call
from FastAPI's threadpool without locks.

Capabilities (the product wedge, per market research):
  - get_execution_flow / get_impact_analysis  -> call-graph "blast radius"
  - dead_code                                  -> exported subs never called
  - hotspots                                   -> EXPLAINABLE risk ranking
  - quality reads (module/summary/worst/search)
  - get_stats / db_meta
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Iterator

from .identity import identifier_key, source_key, runtime_source_tail

SymbolId = str | int  # canonical v2 strings, historical v1 integer IDs

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Историческое расположение единственной базы. Остаётся рабочим: установки,
# собранные до мультистора, продолжают открываться без миграции.
DB_PATH = _DATA_DIR / "rentgen.db"

# Дополнительные конфигурации: data/stores/<store_id>.db. Франчайзи держит здесь
# по базе на клиента, продуктовая команда — по базе на ERP/ЗУП/УТ.
STORES_DIR = _DATA_DIR / "stores"

DEFAULT_STORE_ID = "default"

# store_id приходит из HTTP и подставляется в имя файла, поэтому допускаются
# только заведомо безопасные символы: ни разделителей пути, ни точек, ни
# юникода. Всё остальное отвергается до обращения к файловой системе.
_STORE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# ----- explainable risk weights (transparent on purpose) --------------------
_W_MAINT = 0.40  # weight of (100 - maintainability)
_W_CPLX = 0.25  # weight of complexity_score
_W_DOC = 0.10  # weight of (100 - documentation)
_ISSUE_PTS = {  # concrete anti-pattern penalties (sum capped at 25)
    "has_n_plus_one": 8,
    "has_empty_catch": 6,
    "has_deep_nesting": 5,
    "has_select_star": 6,
    "has_magic_numbers": 3,
}
_FANIN_SATURATION = 25.0  # fan-in at which "blast radius" multiplier maxes out
_SQLITE_IN_CHUNK = 500

# Таблицы, без которых база бесполезна: любой публичный метод читает
# как минимум одну из них. Служат признаком «сборка дошла до конца».
_REQUIRED_TABLES = frozenset(
    {"subroutine", "call_edge", "module", "module_edge", "quality", "meta"}
)

_KNOWN_MODULE_KINDS = {
    "commandmodule",
    "managermodule",
    "objectmodule",
    "recordsetmodule",
    "valuemanagermodule",
    "module",
    "form",
}

_METADATA_ROOTS = (
    "CommonModules",
    "Catalogs",
    "Documents",
    "AccountingRegisters",
    "AccumulationRegisters",
    "InformationRegisters",
    "CalculationRegisters",
    "ChartsOfAccounts",
    "ChartsOfCalculationTypes",
    "ChartsOfCharacteristicTypes",
    "BusinessProcesses",
    "Tasks",
    "Reports",
    "DataProcessors",
    "ExchangePlans",
    "Enums",
    "Constants",
)

_RUNTIME_KIND_MAP = {
    "module": "module",
    "модуль": "module",
    "commonmodule": "module",
    "общиймодуль": "module",
    "objectmodule": "objectmodule",
    "модульобъекта": "objectmodule",
    "managermodule": "managermodule",
    "модульменеджера": "managermodule",
    "recordsetmodule": "recordsetmodule",
    "модульнабора записей": "recordsetmodule",
    "модульнабораписей": "recordsetmodule",
    "valuemanagermodule": "valuemanagermodule",
    "модульменеджеразначения": "valuemanagermodule",
    "commandmodule": "commandmodule",
    "модулькоманды": "commandmodule",
    "form": "form",
    "форма": "form",
    "модульформы": "form",
}


def _chunks(values: Iterable, size: int = _SQLITE_IN_CHUNK):
    chunk = []
    for value in values:
        chunk.append(value)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def _strip_to_module_path(module_ref: str) -> str:
    path = module_ref.strip().strip('"').strip("'").replace("\\", "/")
    if path.startswith(("a/", "b/")):
        path = path[2:]
    for root in _METADATA_ROOTS:
        marker = f"{root}/"
        idx = path.find(marker)
        if idx >= 0:
            return path[idx:]
    return path


def _canon_from_path(module_path: str) -> tuple[str, str]:
    path = _strip_to_module_path(module_path)
    parts = path.split("/")
    obj = parts[1] if len(parts) >= 2 else parts[0]
    stem = parts[-1].rsplit(".", 1)[0].lower()
    if "/Forms/" in path or "Form/Module" in path:
        kind = "form"
    elif stem in _KNOWN_MODULE_KINDS:
        kind = stem
    else:
        kind = "module"
    return obj.lower(), kind


def _canon_from_runtime_module(module_ref: str) -> tuple[str, str]:
    compact = module_ref.strip().replace("\\", ".").replace("/", ".")
    parts = [p.strip() for p in compact.split(".") if p.strip()]
    if not parts:
        return "", "module"
    if len(parts) == 1:
        return parts[0].lower(), "module"

    first = parts[0].replace(" ", "").lower()
    last = parts[-1].replace(" ", "").lower()
    if first in {"общиймодуль", "commonmodule", "commonmodules"}:
        return parts[1].lower(), "module"

    kind = _RUNTIME_KIND_MAP.get(last)
    if kind is None and "форм" in last:
        kind = "form"
    elif kind is None and "команд" in last:
        kind = "commandmodule"
    elif kind is None:
        kind = "module"

    return parts[1].lower(), kind


class RentgenStore:
    def __init__(self, db_path: Path | str = DB_PATH, *, immutable: bool = False):
        """Use immutable only while an authorized caller pins a finalized graph.

        Immutable SQLite skips locking and ignores journal files. The caller must
        verify the graph, reject sidecars and hold file/ancestor pins for every
        query. Mutable legacy stores retain normal read-only SQLite locking.
        """
        if not isinstance(immutable, bool):
            raise TypeError("immutable must be a boolean")
        self._immutable = immutable
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"rentgen.db not found at {self.db_path}. "
                f"Build it: python tools/rentgen/build_store.py"
            )

    # -- connection -----------------------------------------------------------
    @contextmanager
    def _con(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(
            self.db_path.resolve().as_uri()
            + "?mode=ro"
            + ("&immutable=1" if self._immutable else ""),
            uri=True,
            check_same_thread=False,
        )
        try:
            con.row_factory = sqlite3.Row
            con.create_function("identifier_key", 1, identifier_key, deterministic=True)
            yield con
        finally:
            # Connection.__exit__ manages a transaction, but does not close the
            # handle. Explicit close is required before replacing files on Windows.
            con.close()

    def available(self) -> bool:
        """Пригодна ли база к чтению.

        Проверяется не только существование файла, но и наличие таблиц. Файл
        может существовать и при этом быть непригодным: сборка упала на середине,
        база скопирована частично, на диске оказался посторонний .db. Раньше в
        таком случае available() возвращал True, эндпоинты считали данные
        доступными и падали с 500 «no such table» — по всему порталу сразу.
        Теперь непригодная база отвечает так же, как отсутствующая: данных нет.

        Проверка — один запрос к sqlite_master, поэтому её дешевле выполнять
        каждый раз, чем кэшировать и потом объяснять, почему пересобранная база
        всё ещё считается битой.
        """

        if not self.db_path.exists():
            return False
        try:
            with self._con() as con:
                present = {
                    row["name"]
                    for row in con.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                if self._has_identity(con) and "call_site" not in present:
                    return False
        except sqlite3.Error:
            return False
        return _REQUIRED_TABLES <= present

    def db_meta(self) -> dict:
        with self._con() as con:
            return {
                r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")
            }

    @staticmethod
    def _has_identity(con: sqlite3.Connection) -> bool:
        return any(
            r[1] == "source_key" for r in con.execute("PRAGMA table_info(module)")
        )

    @staticmethod
    def _source_lookup_key(reference: str) -> str | None:
        try:
            return source_key(reference.strip().strip('"').strip("'"))
        except ValueError:
            return None

    # ====================================================================== #
    #  QUALITY                                                                #
    # ====================================================================== #
    _QCOLS = (
        "module_path, module_type, domain, loc, complexity_score, "
        "documentation_score, maintainability_score, has_n_plus_one, "
        "has_empty_catch, has_deep_nesting, code_quality, fan_in, fan_out"
    )
    _QFULLCOLS = (
        "module_path, module_type, domain, loc, complexity_score, "
        "documentation_score, maintainability_score, code_quality, "
        "has_n_plus_one, has_select_star, has_empty_catch, has_deep_nesting, "
        "has_magic_numbers, num_todo_fixme, object_name, module_kind, fan_in, fan_out"
    )
    _QFULLCOLS_Q = (
        "q.module_path, q.module_type, q.domain, q.loc, q.complexity_score, "
        "q.documentation_score, q.maintainability_score, q.code_quality, "
        "q.has_n_plus_one, q.has_select_star, q.has_empty_catch, q.has_deep_nesting, "
        "q.has_magic_numbers, q.num_todo_fixme, q.object_name, q.module_kind, "
        "q.fan_in, q.fan_out"
    )

    @staticmethod
    def _row_to_score(r: sqlite3.Row) -> dict:
        return {
            "module_path": r["module_path"],
            "module_type": r["module_type"] or "Unknown",
            "domain": r["domain"] or "Прочее",
            "loc": r["loc"] or 0,
            "complexity_score": r["complexity_score"] or 0,
            "documentation_score": r["documentation_score"] or 0,
            "maintainability_score": r["maintainability_score"] or 0,
            "has_n_plus_one": bool(r["has_n_plus_one"]),
            "has_empty_catch": bool(r["has_empty_catch"]),
            "has_deep_nesting": bool(r["has_deep_nesting"]),
            "code_quality": r["code_quality"],
        }

    @classmethod
    def _row_to_full_score(cls, r: sqlite3.Row) -> dict:
        score = cls._row_to_score(r)
        score.update(
            {
                "has_select_star": bool(r["has_select_star"]),
                "has_magic_numbers": bool(r["has_magic_numbers"]),
                "num_todo_fixme": r["num_todo_fixme"] or 0,
                "object_name": r["object_name"] or "",
                "module_kind": r["module_kind"] or "",
                "fan_in": r["fan_in"] or 0,
                "fan_out": r["fan_out"] or 0,
            }
        )
        return score

    def get_module(self, path: str) -> dict | None:
        with self._con() as con:
            modern = self._has_identity(con)
            r = con.execute(
                f"SELECT {self._QCOLS} FROM quality WHERE {'source_key' if modern else 'identifier_key(module_path)'} = ?",
                (
                    self._source_lookup_key(path)
                    if modern
                    else identifier_key(path.replace("\\", "/")),
                ),
            ).fetchone()
        return self._row_to_score(r) if r else None

    def get_module_risk(self, module_ref: str) -> dict | None:
        """Quality + explainable risk for a module path or graph/runtime module ref."""
        with self._con() as con:
            modern = self._has_identity(con)
            r = con.execute(
                f"SELECT {self._QFULLCOLS} FROM quality WHERE {'source_key' if modern else 'identifier_key(module_path)'} = ?",
                (
                    self._source_lookup_key(module_ref)
                    if modern
                    else identifier_key(module_ref.replace("\\", "/")),
                ),
            ).fetchone()
            if r is None:
                rows, _ = self._resolve_graph_modules(con, module_ref)
                if rows and modern:
                    row = rows[0]
                    r = con.execute(
                        f"""
                        SELECT {self._QFULLCOLS} FROM quality
                        WHERE module_id = ?
                        """,
                        (row["name"],),
                    ).fetchone()
        if r is None:
            return None
        return {**self._row_to_full_score(r), **self._risk(r)}

    def summary(self) -> dict:
        with self._con() as con:
            row = con.execute(
                """
                SELECT COUNT(*) total,
                       AVG(complexity_score) avg_cx,
                       AVG(documentation_score) avg_doc,
                       AVG(maintainability_score) avg_mi,
                       SUM(CASE WHEN has_n_plus_one OR has_empty_catch OR has_deep_nesting
                                THEN 1 ELSE 0 END) issues
                FROM quality
                """
            ).fetchone()
            domains = con.execute(
                """
                SELECT domain,
                       COUNT(*) count,
                       ROUND(AVG(maintainability_score), 1) avg_maintainability
                FROM quality
                WHERE domain IS NOT NULL
                GROUP BY domain ORDER BY count DESC LIMIT 20
                """
            ).fetchall()
        return {
            "total_modules": row["total"] or 0,
            "avg_complexity": round(row["avg_cx"] or 0, 1),
            "avg_documentation": round(row["avg_doc"] or 0, 1),
            "avg_maintainability": round(row["avg_mi"] or 0, 1),
            "modules_with_issues": row["issues"] or 0,
            "by_domain": [dict(d) for d in domains],
        }

    def worst(self, limit: int = 20) -> list[dict]:
        with self._con() as con:
            rows = con.execute(
                f"SELECT {self._QCOLS} FROM quality "
                f"ORDER BY maintainability_score ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_score(r) for r in rows]

    def search(self, q: str, limit: int = 20) -> list[dict]:
        with self._con() as con:
            rows = con.execute(
                f"SELECT {self._QCOLS} FROM quality WHERE module_path LIKE ? "
                f"ORDER BY maintainability_score ASC LIMIT ?",
                (f"%{q}%", limit),
            ).fetchall()
        return [self._row_to_score(r) for r in rows]

    # ====================================================================== #
    #  EXPLAINABLE RISK HOTSPOTS  (the product wedge)                         #
    # ====================================================================== #
    @classmethod
    def _risk(cls, r: sqlite3.Row) -> dict:
        """Transparent risk score (0-100) with human-readable reasons.

        risk = quality_risk * blast_multiplier
          quality_risk = w_maint*(100-MI) + w_cplx*CPLX + w_doc*(100-DOC) + issues
          blast        = 0.65 .. 1.0   scaled by fan-in (call-graph centrality)
        Every contributing factor is surfaced in `reasons` so the number is
        never a black box (market-research credibility requirement).
        """
        mi = r["maintainability_score"] or 0
        cplx = r["complexity_score"] or 0
        doc = r["documentation_score"] or 0
        fan_in = r["fan_in"] or 0
        fan_out = r["fan_out"] or 0

        reasons: list[dict] = []
        quality_risk = 0.0

        m_term = _W_MAINT * (100 - mi)
        quality_risk += m_term
        if mi < 50:
            reasons.append(
                {
                    "factor": "maintainability",
                    "detail": f"Низкая поддерживаемость: {mi}/100",
                    "weight": round(m_term, 1),
                }
            )

        c_term = _W_CPLX * cplx
        quality_risk += c_term
        if cplx >= 60:
            reasons.append(
                {
                    "factor": "complexity",
                    "detail": f"Высокая сложность: {cplx}/100",
                    "weight": round(c_term, 1),
                }
            )

        d_term = _W_DOC * (100 - doc)
        quality_risk += d_term
        if doc < 25:
            reasons.append(
                {
                    "factor": "documentation",
                    "detail": f"Почти нет документации: {doc}/100",
                    "weight": round(d_term, 1),
                }
            )

        issue_pts = 0
        issue_labels = {
            "has_n_plus_one": "Запрос в цикле (N+1)",
            "has_empty_catch": "Пустой блок Попытка/Исключение",
            "has_deep_nesting": "Глубокая вложенность",
            "has_select_star": "ВЫБРАТЬ * в запросе",
            "has_magic_numbers": "Магические числа",
        }
        for flag, pts in _ISSUE_PTS.items():
            try:
                present = bool(r[flag])
            except (IndexError, KeyError):
                present = False
            if present:
                issue_pts += pts
                reasons.append(
                    {
                        "factor": "antipattern",
                        "detail": issue_labels[flag],
                        "weight": pts,
                    }
                )
        issue_pts = min(issue_pts, 25)
        quality_risk += issue_pts

        quality_risk = max(0.0, min(100.0, quality_risk))

        centrality = min(1.0, fan_in / _FANIN_SATURATION)
        blast = 0.65 + 0.35 * centrality
        if fan_in >= 5:
            reasons.append(
                {
                    "factor": "blast_radius",
                    "detail": f"От модуля зависят {fan_in} других модулей (радиус поражения)",
                    "weight": round(quality_risk * (blast - 0.65), 1),
                }
            )
        if fan_out >= 15:
            reasons.append(
                {
                    "factor": "coupling",
                    "detail": f"Высокая связанность: зависит от {fan_out} модулей",
                    "weight": 0,
                }
            )

        risk = round(min(100.0, quality_risk * blast))
        reasons.sort(key=lambda x: x["weight"], reverse=True)
        return {
            "risk": risk,
            "quality_risk": round(quality_risk),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "reasons": reasons,
        }

    def hotspots(
        self, limit: int = 30, domain: str | None = None, min_fan_in: int = 0
    ) -> list[dict]:
        where = "WHERE fan_in >= ?"
        params: list = [min_fan_in]
        if domain:
            where += " AND domain = ?"
            params.append(domain)
        # Prefilter to plausibly-risky rows, then rank precisely in Python so the
        # risk math + reasons stay in one place.
        with self._con() as con:
            rows = con.execute(
                f"""
                SELECT module_path, module_type, domain, loc, complexity_score,
                       documentation_score, maintainability_score, code_quality,
                       has_n_plus_one, has_empty_catch, has_deep_nesting,
                       has_select_star, has_magic_numbers, fan_in, fan_out
                FROM quality
                {where}
                  AND (maintainability_score < 60 OR complexity_score > 55
                       OR has_n_plus_one OR has_empty_catch OR fan_in > 8)
                ORDER BY fan_in DESC, complexity_score DESC
                LIMIT 4000
                """,
                params,
            ).fetchall()
        scored = []
        for r in rows:
            risk = self._risk(r)
            scored.append(
                {
                    "module_path": r["module_path"],
                    "module_type": r["module_type"],
                    "domain": r["domain"],
                    "loc": r["loc"],
                    "complexity_score": r["complexity_score"],
                    "documentation_score": r["documentation_score"],
                    "maintainability_score": r["maintainability_score"],
                    "code_quality": r["code_quality"],
                    **risk,
                }
            )
        scored.sort(key=lambda x: x["risk"], reverse=True)
        return scored[:limit]

    # ====================================================================== #
    #  CALL GRAPH — flow / impact / dead code                                 #
    # ====================================================================== #
    def _resolve_entry(
        self, con: sqlite3.Connection, entry: str, cap: int = 25
    ) -> list[SymbolId]:
        """Resolve unique Unicode names, explicit module::name, or symbol IDs."""
        modern = self._has_identity(con)
        exact = con.execute("SELECT id FROM subroutine WHERE id=?", (entry,)).fetchall()
        if exact:
            return [r["id"] for r in exact]
        module_ref = None
        name = entry
        if "::" in entry:
            module_ref, name = entry.rsplit("::", 1)
        elif "." in entry:
            module_ref, name = entry.rsplit(".", 1)
        key_expr = "name_key" if modern else "identifier_key(name)"
        args = [identifier_key(name)]
        condition = f"{key_expr}=?"
        if module_ref is not None:
            modules, _ = self._resolve_graph_modules(con, module_ref)
            if len(modules) != 1:
                return []
            condition += " AND module=?"
            args.append(modules[0]["name"])
        rows = con.execute(
            f"SELECT id FROM subroutine WHERE {condition} ORDER BY id LIMIT 2", args
        ).fetchall()
        return [rows[0]["id"]] if len(rows) == 1 else []

    def _traverse_ids_result(
        self,
        con: sqlite3.Connection,
        entry_ids: list[SymbolId],
        max_depth: int,
        reverse: bool,
        max_edges: int = 600,
    ) -> dict:
        """Traverse unique dependencies and prove whether the frontier is exhausted.

        Completeness is relative to this stored graph, not to dynamic BSL calls.
        A limit is only a truncation when at least one further edge exists.
        """
        if max_depth < 0 or max_edges < 1:
            raise ValueError("max_depth must be nonnegative and max_edges positive")
        modern = self._has_identity(con)
        source_columns = (
            ", cs.source_path AS caller_source_path, ds.source_path AS callee_source_path, "
            "(SELECT display_name FROM module WHERE name=cs.module) AS caller_display_name, "
            "(SELECT display_name FROM module WHERE name=ds.module) AS callee_display_name"
            if modern
            else ""
        )
        join_from = "callee_id" if reverse else "caller_id"
        join_to = "caller_id" if reverse else "callee_id"
        edges: list[dict] = []
        frontier = sorted(set(entry_ids))
        visited: set[SymbolId] = set(frontier)
        depth = 0
        reasons: list[str] = []
        while frontier and depth < max_depth:
            depth += 1
            next_frontier: set[SymbolId] = set()
            for frontier_chunk in _chunks(frontier):
                placeholders = ",".join("?" * len(frontier_chunk))
                q = f"""
                    SELECT e.{join_from} AS from_id, e.{join_to} AS to_id, MIN(e.line) AS line,
                           cs.name AS caller_name, cs.module AS caller_module,
                           ds.name AS callee_name, ds.module AS callee_module {source_columns}
                    FROM call_edge e
                    JOIN subroutine cs ON cs.id = e.caller_id
                    JOIN subroutine ds ON ds.id = e.callee_id
                    WHERE e.{join_from} IN ({placeholders})
                    GROUP BY e.{join_from}, e.{join_to}
                    ORDER BY e.{join_from}, e.{join_to}
                    LIMIT ?
                """
                remaining = max_edges - len(edges)
                rows = con.execute(q, (*frontier_chunk, remaining + 1)).fetchall()
                for r in rows[:remaining]:
                    edges.append(
                        {
                            "caller": r["caller_name"],
                            "caller_module": r["caller_module"],
                            "callee": r["callee_name"],
                            "callee_module": r["callee_module"],
                            "line": r["line"],
                            "depth": depth,
                            **(
                                {
                                    key: r[key]
                                    for key in (
                                        "caller_source_path",
                                        "callee_source_path",
                                        "caller_display_name",
                                        "callee_display_name",
                                    )
                                }
                                if modern
                                else {}
                            ),
                        }
                    )
                    nxt = r["to_id"]
                    if nxt not in visited:
                        visited.add(nxt)
                        next_frontier.add(nxt)
                if len(rows) > remaining:
                    reasons.append("max_edges")
                    break
            if reasons:
                break
            frontier = sorted(next_frontier)
        if frontier and depth >= max_depth and not reasons:
            # Newly discovered nodes were not expanded. Probe without fetching
            # their payloads; a terminal leaf at the limit is still complete.
            for frontier_chunk in _chunks(frontier):
                placeholders = ",".join("?" * len(frontier_chunk))
                if con.execute(
                    f"SELECT 1 FROM call_edge e "
                    "JOIN subroutine cs ON cs.id = e.caller_id "
                    "JOIN subroutine ds ON ds.id = e.callee_id "
                    f"WHERE e.{join_from} IN ({placeholders}) LIMIT 1",
                    frontier_chunk,
                ).fetchone():
                    reasons.append("max_depth")
                    break
        return {
            "edges": edges,
            "complete": not reasons,
            "truncated": bool(reasons),
            "truncation_reasons": reasons,
            "max_depth": max_depth,
            "max_edges": max_edges,
            "completeness_scope": "stored_static_graph",
        }

    def _traverse_ids(
        self,
        con: sqlite3.Connection,
        entry_ids: list[SymbolId],
        max_depth: int,
        reverse: bool,
        max_edges: int = 600,
    ) -> list[dict]:
        # Compatibility for list-based visualization callers. Change gates use
        # module_impact, which retains the completeness result.
        return self._traverse_ids_result(con, entry_ids, max_depth, reverse, max_edges)[
            "edges"
        ]

    def _traverse(
        self, entry: str, max_depth: int, reverse: bool, max_edges: int = 600
    ) -> list[dict]:
        with self._con() as con:
            entry_ids = self._resolve_entry(con, entry)
            return self._traverse_ids(con, entry_ids, max_depth, reverse, max_edges)

    def get_execution_flow(self, entry_point: str, max_depth: int = 10) -> list[dict]:
        return self._traverse(entry_point, max_depth, reverse=False)

    def get_impact_analysis(self, entry_point: str, max_depth: int = 10) -> list[dict]:
        return self._traverse(entry_point, max_depth, reverse=True)

    def dead_code(self, limit: int = 50, scope: str = "common") -> dict:
        """Export candidates without a caller in the stored static graph.

        scope='common' uses recognized common-module source paths. Platform,
        global and dynamic invocation are not proven absent by these results.
        scope='all' also includes other module kinds and platform entry points.
        """
        common_only = "AND s.module NOT LIKE '%.%'" if scope == "common" else ""
        with self._con() as con:
            modern = self._has_identity(con)
            if modern and scope == "common":
                common_only = "AND EXISTS (SELECT 1 FROM module m WHERE m.name=s.module AND m.common_key IS NOT NULL)"
            path_column = "s.source_path" if modern else "NULL"
            evidence = (
                ",s.source_provenance,s.declaration_ambiguous,"
                "(SELECT display_name FROM module WHERE name=s.module) AS display_name"
                if modern
                else ""
            )
            rows = con.execute(
                f"""
                SELECT s.name AS name,
                       CASE WHEN s.is_function THEN 'BSL_FUNCTION' ELSE 'BSL_PROCEDURE' END AS kind,
                       s.module AS module, {path_column} AS module_path, s.line AS line,
                       s.complexity AS complexity {evidence}
                FROM subroutine s
                WHERE s.is_export = 1 {common_only}
                  AND NOT EXISTS (SELECT 1 FROM call_edge e WHERE e.callee_id = s.id)
                ORDER BY s.complexity DESC, s.module, s.name
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            total = con.execute(
                f"""
                SELECT COUNT(*) c FROM subroutine s
                WHERE s.is_export = 1 {common_only}
                  AND NOT EXISTS (SELECT 1 FROM call_edge e WHERE e.callee_id = s.id)
                """
            ).fetchone()["c"]
        return {
            "candidates": [dict(r) for r in rows],
            "total": total,
            "shown": len(rows),
            "scope": scope,
        }

    def get_stats(self) -> dict:
        with self._con() as con:
            modern = self._has_identity(con)
            module_evidence = (
                ",display_name,source_path,source_provenance" if modern else ""
            )
            symbol_evidence = (
                ",source_path,source_provenance,declaration_ambiguous" if modern else ""
            )
            g = con.execute(
                "SELECT COUNT(*) subs, SUM(is_export) exported, "
                "SUM(is_function) funcs, AVG(complexity) avg_c, MAX(complexity) max_c "
                "FROM subroutine"
            ).fetchone()
            n_modules = con.execute("SELECT COUNT(*) c FROM module").fetchone()["c"]
            n_edges = con.execute("SELECT COUNT(*) c FROM call_edge").fetchone()["c"]
            n_medges = con.execute("SELECT COUNT(*) c FROM module_edge").fetchone()["c"]
            n_quality = con.execute("SELECT COUNT(*) c FROM quality").fetchone()["c"]
            top_fanin = con.execute(
                f"SELECT name, object_name, module_kind, fan_in, fan_out, n_subs {module_evidence} "
                "FROM module ORDER BY fan_in DESC,name LIMIT 15"
            ).fetchall()
            top_complex = con.execute(
                f"SELECT id, name, module, complexity, line {symbol_evidence} FROM subroutine "
                "ORDER BY complexity DESC,module,name,id LIMIT 15"
            ).fetchall()
        return {
            "subroutines": g["subs"] or 0,
            "functions": g["funcs"] or 0,
            "procedures": (g["subs"] or 0) - (g["funcs"] or 0),
            "exported": g["exported"] or 0,
            "modules": n_modules,
            "call_edges": n_edges,
            "module_edges": n_medges,
            "quality_modules": n_quality,
            "avg_complexity": round(g["avg_c"] or 0, 1),
            "max_complexity": g["max_c"] or 0,
            "top_fan_in": [dict(r) for r in top_fanin],
            "top_complex": [dict(r) for r in top_complex],
        }

    # ====================================================================== #
    #  MODULE-CENTRIC GRAPH  (for the force-graph viz around one module)      #
    # ====================================================================== #
    def _resolve_graph_modules(
        self, con: sqlite3.Connection, module_ref: str
    ) -> tuple[list[sqlite3.Row], dict]:
        """Resolve exact source identity; aliases only succeed when unique.

        A source-path miss never falls back to a lossy owner/kind join. Legacy
        rows remain inspectable but cannot establish precise source coverage.
        """
        module_ref = module_ref.strip()
        modern = self._has_identity(con)
        canonical = {
            "source": "graph_name",
            "resolution_complete": False,
            "identity_precision": "legacy" if not modern else "source_path",
        }
        if not modern:
            rows = con.execute(
                "SELECT * FROM module WHERE identifier_key(name)=? ORDER BY name LIMIT 2",
                (identifier_key(module_ref),),
            ).fetchall()
            canonical["reason"] = "legacy_source_identity"
            return (rows if len(rows) == 1 else []), canonical
        rows = con.execute(
            "SELECT * FROM module WHERE name=?", (module_ref,)
        ).fetchall()
        if not rows:
            if (
                "/" in module_ref
                or "\\" in module_ref
                or module_ref.lower().endswith(".bsl")
            ):
                canonical["source"] = "module_path"
                rows = con.execute(
                    "SELECT * FROM module WHERE source_key=?",
                    (self._source_lookup_key(module_ref),),
                ).fetchall()
            elif (runtime_tail := runtime_source_tail(module_ref)) is not None:
                canonical["source"] = "runtime_module"
                boundary_tail = "/" + runtime_tail
                rows = con.execute(
                    "SELECT * FROM module WHERE source_provenance='source_path' "
                    "AND (source_key=? OR substr(source_key,-length(?))=?) "
                    "ORDER BY name LIMIT 2",
                    (runtime_tail, boundary_tail, boundary_tail),
                ).fetchall()
            else:
                canonical["source"] = "display_alias"
                rows = con.execute(
                    "SELECT * FROM module WHERE display_key=? ORDER BY name LIMIT 2",
                    (identifier_key(module_ref),),
                ).fetchall()
        if len(rows) > 1:
            canonical["reason"] = "ambiguous_reference"
            return [], canonical
        if not rows:
            canonical["reason"] = "not_found"
            return [], canonical
        row = rows[0]
        precise = row["source_provenance"] == "source_path"
        canonical.update(
            object_name=row["object_name"],
            module_kind=row["module_kind"],
            source_path=row["source_path"],
            module_id=row["name"],
            resolution_complete=precise,
            identity_precision="source_path" if precise else "legacy",
        )
        if not precise:
            canonical["reason"] = "legacy_source_identity"
        return rows, canonical

    def call_sites(
        self, module_ref: str, *, unresolved_only: bool = False
    ) -> list[dict]:
        """Queryable evidence, including unsupported calls and physical spans."""
        with self._con() as con:
            if not self._has_identity(con):
                return []
            modules, _ = self._resolve_graph_modules(con, module_ref)
            if len(modules) != 1:
                return []
            predicate = " AND c.callee_id IS NULL" if unresolved_only else ""
            rows = con.execute(
                "SELECT c.*,s.source_path,s.module,s.name AS caller_name,s.source_provenance "
                "FROM call_site c JOIN subroutine s ON s.id=c.caller_id "
                f"WHERE s.module=?{predicate} ORDER BY c.line,c.column,c.id",
                (modules[0]["name"],),
            ).fetchall()
            return [dict(r) for r in rows]

    def resolve_module(self, module_ref: str) -> dict:
        """Describe how a user-supplied module reference maps to the graph."""
        with self._con() as con:
            rows, canonical = self._resolve_graph_modules(con, module_ref)
        return {
            "module_ref": module_ref,
            "canonical": canonical,
            "graph_modules": [dict(r) for r in rows],
        }

    def module_impact(
        self, module_ref: str, max_depth: int = 5, max_edges: int = 600
    ) -> dict:
        """Reverse impact for every subroutine in a resolved graph module."""
        with self._con() as con:
            module_rows, canonical = self._resolve_graph_modules(con, module_ref)
            module_names = [r["name"] for r in module_rows]
            seed_ids: list[SymbolId] = []
            for name_chunk in _chunks(module_names):
                placeholders = ",".join("?" * len(name_chunk))
                rows = con.execute(
                    f"SELECT id FROM subroutine WHERE module IN ({placeholders})",
                    name_chunk,
                ).fetchall()
                seed_ids.extend(r["id"] for r in rows)

            traversal = self._traverse_ids_result(
                con,
                seed_ids,
                max_depth=max_depth,
                reverse=True,
                max_edges=max_edges,
            )

        edges = traversal["edges"]
        if not canonical["resolution_complete"]:
            traversal["complete"] = False
            traversal["truncated"] = True
            traversal["truncation_reasons"].append(
                canonical.get("reason", "module_resolution")
            )
        module_set = set(module_names)
        impacted: dict[str, int] = {}
        for edge in edges:
            caller_module = edge["caller_module"]
            if caller_module in module_set:
                continue
            impacted[caller_module] = impacted.get(caller_module, 0) + 1

        impacted_modules = [
            {"module": name, "edges": count}
            for name, count in sorted(
                impacted.items(), key=lambda item: item[1], reverse=True
            )
        ]
        return {
            "module_ref": module_ref,
            "canonical": canonical,
            "graph_modules": [dict(r) for r in module_rows],
            "entry_subroutines": len(seed_ids),
            **traversal,
            "complete": bool(module_rows) and traversal["complete"],
            "total": len(edges),
            "impacted_modules": impacted_modules,
        }

    def hotspots_for_graph_modules(
        self, module_names: list[str], limit: int = 20
    ) -> list[dict]:
        """Risk rows whose canonical key matches any graph module name."""
        if not module_names:
            return []

        rows_by_path: dict[str, sqlite3.Row] = {}
        with self._con() as con:
            modern = self._has_identity(con)
            if not modern:
                return []  # Old owner/kind joins cannot establish exact quality.
            for name_chunk in _chunks(dict.fromkeys(module_names)):
                placeholders = ",".join("?" * len(name_chunk))
                rows = con.execute(
                    f"""
                    SELECT DISTINCT {self._QFULLCOLS_Q}
                    FROM quality q
                    JOIN module m
                      ON m.name = q.module_id
                    WHERE m.name IN ({placeholders})
                    """,
                    name_chunk,
                ).fetchall()
                for row in rows:
                    rows_by_path[row["module_path"]] = row

        scored = []
        for row in rows_by_path.values():
            scored.append({**self._row_to_full_score(row), **self._risk(row)})
        scored.sort(key=lambda item: item["risk"], reverse=True)
        return scored[:limit]

    def module_neighbors(self, module: str, limit: int = 60) -> dict:
        """Direct callers + callees of a module (module-level graph slice)."""
        with self._con() as con:
            resolved, canonical = self._resolve_graph_modules(con, module)
            if len(resolved) != 1:
                return {
                    "module": module,
                    "info": None,
                    "calls": [],
                    "called_by": [],
                    "canonical": canonical,
                }
            module = resolved[0]["name"]
            modern = self._has_identity(con)
            out_evidence = ",m.display_name,m.source_path" if modern else ""
            out = con.execute(
                f"SELECT dst AS module, weight {out_evidence} FROM module_edge e JOIN module m ON m.name=e.dst WHERE src = ? "
                "ORDER BY weight DESC,dst LIMIT ?",
                (module, limit),
            ).fetchall()
            inc = con.execute(
                f"SELECT src AS module, weight {out_evidence} FROM module_edge e JOIN module m ON m.name=e.src WHERE dst = ? "
                "ORDER BY weight DESC,src LIMIT ?",
                (module, limit),
            ).fetchall()
            self_row = con.execute(
                "SELECT * FROM module WHERE name = ?",
                (module,),
            ).fetchone()
        return {
            "module": module,
            "info": dict(self_row) if self_row else None,
            "calls": [dict(r) for r in out],
            "called_by": [dict(r) for r in inc],
            "canonical": canonical,
        }

    def module_edges(self, limit: int = 5000, min_weight: int = 1) -> list[dict]:
        """Module-level dependency edges enriched with module and quality metadata."""
        with self._con() as con:
            modern = self._has_identity(con)
            # Legacy graph rows can be inspected, but a quality row cannot be
            # attributed through the old collapsed owner/kind relation.
            quality_joins = (
                "LEFT JOIN quality sq ON sq.module_id=sm.name "
                "LEFT JOIN quality dq ON dq.module_id=dm.name"
                if modern
                else "LEFT JOIN quality sq ON 0 LEFT JOIN quality dq ON 0"
            )
            src_path = "sm.source_path" if modern else "NULL"
            dst_path = "dm.source_path" if modern else "NULL"
            labels = (
                ", sm.display_name AS src_display_name, dm.display_name AS dst_display_name"
                if modern
                else ""
            )
            rows = con.execute(
                f"""
                SELECT e.src,e.dst,e.weight,
                       sm.object_name AS src_object,sm.module_kind AS src_kind,
                       sm.fan_in AS src_fan_in,sm.fan_out AS src_fan_out,
                       {src_path} AS src_path,sq.domain AS src_domain,
                       sq.maintainability_score AS src_maintainability,
                       dm.object_name AS dst_object,dm.module_kind AS dst_kind,
                       dm.fan_in AS dst_fan_in,dm.fan_out AS dst_fan_out,
                       {dst_path} AS dst_path,dq.domain AS dst_domain,
                       dq.maintainability_score AS dst_maintainability {labels}
                FROM module_edge e
                JOIN module sm ON sm.name=e.src
                JOIN module dm ON dm.name=e.dst
                {quality_joins}
                WHERE e.weight >= ? ORDER BY e.weight DESC,e.src,e.dst LIMIT ?
                """,
                (min_weight, limit),
            ).fetchall()

        return [dict(row) for row in rows]


def validate_store_id(store_id: str) -> str:
    """Проверяет идентификатор конфигурации. Бросает ValueError на подозрительном.

    Идентификатор становится частью пути к файлу, поэтому проверка строгая:
    разрешены только буквы, цифры, дефис и подчёркивание. Это отсекает обход
    каталога (``../``), абсолютные пути и NUL-байты до любого обращения к диску.
    """

    if not isinstance(store_id, str) or not _STORE_ID_RE.match(store_id):
        raise ValueError(
            "store_id must match [A-Za-z0-9_-]{1,64}; " f"got {store_id!r}"
        )
    return store_id


def resolve_db_path(store_id: str | None = None) -> Path:
    """Путь к базе конфигурации. None и 'default' — историческая data/rentgen.db."""

    if store_id is None or store_id == DEFAULT_STORE_ID:
        return DB_PATH
    validate_store_id(store_id)
    candidate = (STORES_DIR / f"{store_id}.db").resolve()
    # Пояс поверх подтяжек: даже при валидном id результат обязан лежать внутри
    # STORES_DIR, иначе это симлинк наружу.
    if not str(candidate).startswith(str(STORES_DIR.resolve())):
        raise ValueError(f"store_id escapes the stores directory: {store_id!r}")
    return candidate


def list_stores() -> list[dict]:
    """Доступные конфигурации с их метаданными.

    Всегда содержит запись 'default', даже если база ещё не построена — так
    интерфейс может показать 'не собрано' вместо пустого списка.
    """

    entries: list[dict] = []

    def _describe(store_id: str, db_path: Path) -> dict:
        # Признак доступности берётся у самого движка, а не из проверки на
        # существование файла: битая или недостроенная база не должна попасть
        # в список как рабочая — иначе её выберут в интерфейсе и получат 500.
        entry = {
            "store_id": store_id,
            "path": str(db_path),
            "available": False,
            "meta": {},
        }
        try:
            store = RentgenStore(db_path)
        except FileNotFoundError:
            return entry
        if not store.available():
            return entry
        try:
            entry["meta"] = store.db_meta()
        except sqlite3.Error:
            return entry
        entry["available"] = True
        return entry

    entries.append(_describe(DEFAULT_STORE_ID, DB_PATH))
    if STORES_DIR.exists():
        for db_file in sorted(STORES_DIR.glob("*.db")):
            store_id = db_file.stem
            if store_id == DEFAULT_STORE_ID or not _STORE_ID_RE.match(store_id):
                continue
            entries.append(_describe(store_id, db_file))
    return entries


@lru_cache(maxsize=16)
def _get_store_cached(store_id: str) -> RentgenStore:
    return RentgenStore(resolve_db_path(store_id))


def get_store(store_id: str | None = None) -> RentgenStore:
    """Движок для указанной конфигурации. Без аргумента — историческая база.

    None и "default" нормализуются в один ключ кэша: это одна и та же база, и
    держать под неё два объекта незачем.

    Пустая строка НЕ равна None: `?store=` в запросе — это заданный, но неверный
    идентификатор, и подставлять вместо него дефолтную конфигурацию нельзя —
    клиент получил бы чужие цифры вместо отказа.
    """

    if store_id is None:
        store_id = DEFAULT_STORE_ID
    return _get_store_cached(store_id)
