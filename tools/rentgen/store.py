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

import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Iterable

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rentgen.db"

# ----- explainable risk weights (transparent on purpose) --------------------
_W_MAINT = 0.40      # weight of (100 - maintainability)
_W_CPLX = 0.25       # weight of complexity_score
_W_DOC = 0.10        # weight of (100 - documentation)
_ISSUE_PTS = {       # concrete anti-pattern penalties (sum capped at 25)
    "has_n_plus_one": 8,
    "has_empty_catch": 6,
    "has_deep_nesting": 5,
    "has_select_star": 6,
    "has_magic_numbers": 3,
}
_FANIN_SATURATION = 25.0  # fan-in at which "blast radius" multiplier maxes out
_SQLITE_IN_CHUNK = 500

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
    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"rentgen.db not found at {self.db_path}. "
                f"Build it: python tools/rentgen/build_store.py"
            )

    # -- connection -----------------------------------------------------------
    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(
            f"file:{self.db_path}?mode=ro", uri=True, check_same_thread=False
        )
        con.row_factory = sqlite3.Row
        return con

    def available(self) -> bool:
        return self.db_path.exists()

    def db_meta(self) -> dict:
        with self._con() as con:
            return {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM meta")}

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
        score.update({
            "has_select_star": bool(r["has_select_star"]),
            "has_magic_numbers": bool(r["has_magic_numbers"]),
            "num_todo_fixme": r["num_todo_fixme"] or 0,
            "object_name": r["object_name"] or "",
            "module_kind": r["module_kind"] or "",
            "fan_in": r["fan_in"] or 0,
            "fan_out": r["fan_out"] or 0,
        })
        return score

    def get_module(self, path: str) -> dict | None:
        path = _strip_to_module_path(path)
        with self._con() as con:
            r = con.execute(
                f"SELECT {self._QCOLS} FROM quality WHERE module_path = ?", (path,)
            ).fetchone()
        return self._row_to_score(r) if r else None

    def get_module_risk(self, module_ref: str) -> dict | None:
        """Quality + explainable risk for a module path or graph/runtime module ref."""
        module_path = _strip_to_module_path(module_ref)
        with self._con() as con:
            r = con.execute(
                f"SELECT {self._QFULLCOLS} FROM quality WHERE module_path = ?",
                (module_path,),
            ).fetchone()
            if r is None:
                rows, _ = self._resolve_graph_modules(con, module_ref)
                if rows:
                    row = rows[0]
                    r = con.execute(
                        f"""
                        SELECT {self._QFULLCOLS} FROM quality
                        WHERE object_name = ? AND module_kind = ?
                        ORDER BY fan_in DESC, fan_out DESC, loc DESC
                        LIMIT 1
                        """,
                        (row["object_name"], row["module_kind"]),
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
            reasons.append({"factor": "maintainability", "detail":
                            f"Низкая поддерживаемость: {mi}/100", "weight": round(m_term, 1)})

        c_term = _W_CPLX * cplx
        quality_risk += c_term
        if cplx >= 60:
            reasons.append({"factor": "complexity", "detail":
                            f"Высокая сложность: {cplx}/100", "weight": round(c_term, 1)})

        d_term = _W_DOC * (100 - doc)
        quality_risk += d_term
        if doc < 25:
            reasons.append({"factor": "documentation", "detail":
                            f"Почти нет документации: {doc}/100", "weight": round(d_term, 1)})

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
                reasons.append({"factor": "antipattern", "detail": issue_labels[flag],
                                "weight": pts})
        issue_pts = min(issue_pts, 25)
        quality_risk += issue_pts

        quality_risk = max(0.0, min(100.0, quality_risk))

        centrality = min(1.0, fan_in / _FANIN_SATURATION)
        blast = 0.65 + 0.35 * centrality
        if fan_in >= 5:
            reasons.append({"factor": "blast_radius", "detail":
                            f"От модуля зависят {fan_in} других модулей (радиус поражения)",
                            "weight": round(quality_risk * (blast - 0.65), 1)})
        if fan_out >= 15:
            reasons.append({"factor": "coupling", "detail":
                            f"Высокая связанность: зависит от {fan_out} модулей",
                            "weight": 0})

        risk = round(min(100.0, quality_risk * blast))
        reasons.sort(key=lambda x: x["weight"], reverse=True)
        return {
            "risk": risk,
            "quality_risk": round(quality_risk),
            "fan_in": fan_in,
            "fan_out": fan_out,
            "reasons": reasons,
        }

    def hotspots(self, limit: int = 30, domain: str | None = None,
                 min_fan_in: int = 0) -> list[dict]:
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
            scored.append({
                "module_path": r["module_path"],
                "module_type": r["module_type"],
                "domain": r["domain"],
                "loc": r["loc"],
                "complexity_score": r["complexity_score"],
                "documentation_score": r["documentation_score"],
                "maintainability_score": r["maintainability_score"],
                "code_quality": r["code_quality"],
                **risk,
            })
        scored.sort(key=lambda x: x["risk"], reverse=True)
        return scored[:limit]

    # ====================================================================== #
    #  CALL GRAPH — flow / impact / dead code                                 #
    # ====================================================================== #
    def _resolve_entry(self, con: sqlite3.Connection, entry: str, cap: int = 25) -> list[int]:
        """Resolve an entry point string to subroutine ids."""
        rows = con.execute(
            "SELECT id FROM subroutine WHERE name = ? LIMIT ?", (entry, cap)
        ).fetchall()
        if not rows:
            rows = con.execute(
                "SELECT id FROM subroutine WHERE name = ? COLLATE NOCASE LIMIT ?",
                (entry, cap),
            ).fetchall()
        if not rows and "." in entry:
            mod, name = entry.rsplit(".", 1)
            rows = con.execute(
                "SELECT id FROM subroutine WHERE name = ? COLLATE NOCASE "
                "AND module LIKE ? LIMIT ?",
                (name, f"%{mod}%", cap),
            ).fetchall()
        return [r["id"] for r in rows]

    def _traverse_ids(self, con: sqlite3.Connection, entry_ids: list[int],
                      max_depth: int, reverse: bool,
                      max_edges: int = 600) -> list[dict]:
        join_from = "callee_id" if reverse else "caller_id"
        join_to = "caller_id" if reverse else "callee_id"
        edges: list[dict] = []
        seen_edges: set[tuple[int, int]] = set()
        frontier = list(dict.fromkeys(entry_ids))
        if not frontier:
            return []

        visited: set[int] = set(frontier)
        depth = 0
        while frontier and depth < max_depth and len(edges) < max_edges:
            depth += 1
            next_frontier: set[int] = set()
            for frontier_chunk in _chunks(frontier):
                placeholders = ",".join("?" * len(frontier_chunk))
                q = f"""
                    SELECT e.{join_from} AS from_id, e.{join_to} AS to_id, e.line AS line,
                           cs.name AS caller_name, cs.module AS caller_module,
                           ds.name AS callee_name, ds.module AS callee_module
                    FROM call_edge e
                    JOIN subroutine cs ON cs.id = e.caller_id
                    JOIN subroutine ds ON ds.id = e.callee_id
                    WHERE e.{join_from} IN ({placeholders})
                    LIMIT ?
                """
                rows = con.execute(
                    q, (*frontier_chunk, max_edges - len(edges))
                ).fetchall()
                for r in rows:
                    pair = (r["from_id"], r["to_id"])
                    if pair in seen_edges:
                        continue
                    seen_edges.add(pair)
                    edges.append({
                        "caller": r["caller_name"],
                        "caller_module": r["caller_module"],
                        "callee": r["callee_name"],
                        "callee_module": r["callee_module"],
                        "line": r["line"],
                        "depth": depth,
                    })
                    nxt = r["to_id"]
                    if nxt not in visited:
                        visited.add(nxt)
                        next_frontier.add(nxt)
                    if len(edges) >= max_edges:
                        break
                if len(edges) >= max_edges:
                    break
            frontier = list(next_frontier)
        return edges

    def _traverse(self, entry: str, max_depth: int, reverse: bool,
                  max_edges: int = 600) -> list[dict]:
        with self._con() as con:
            entry_ids = self._resolve_entry(con, entry)
            return self._traverse_ids(con, entry_ids, max_depth, reverse, max_edges)

    def get_execution_flow(self, entry_point: str, max_depth: int = 10) -> list[dict]:
        return self._traverse(entry_point, max_depth, reverse=False)

    def get_impact_analysis(self, entry_point: str, max_depth: int = 10) -> list[dict]:
        return self._traverse(entry_point, max_depth, reverse=True)

    def dead_code(self, limit: int = 50, scope: str = "common") -> dict:
        """Exported subroutines never called by any internal call edge.

        scope='common' (default, high precision): only exports in COMMON modules
        (1-segment module names). In 1C these are reachable *only* via an explicit
        `Модуль.Функция()` call, so zero callers ⇒ genuinely dead (barring dynamic
        Выполнить()). Object/Manager/Form-module exports are excluded because the
        platform invokes them (event handlers, commands, web methods) without a
        BSL call edge — counting them would massively over-report.

        scope='all': every exported subroutine with no caller (noisy).
        """
        common_only = "AND s.module NOT LIKE '%.%'" if scope == "common" else ""
        with self._con() as con:
            rows = con.execute(
                f"""
                SELECT s.name AS name,
                       CASE WHEN s.is_function THEN 'BSL_FUNCTION' ELSE 'BSL_PROCEDURE' END AS kind,
                       s.module AS module, s.module AS module_path, s.line AS line,
                       s.complexity AS complexity
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
        return {"candidates": [dict(r) for r in rows], "total": total,
                "shown": len(rows), "scope": scope}

    def get_stats(self) -> dict:
        with self._con() as con:
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
                "SELECT name, object_name, module_kind, fan_in, fan_out, n_subs "
                "FROM module ORDER BY fan_in DESC LIMIT 15"
            ).fetchall()
            top_complex = con.execute(
                "SELECT name, module, complexity, line FROM subroutine "
                "ORDER BY complexity DESC LIMIT 15"
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
        """Resolve module path/runtime stack name/graph name to graph module rows."""
        module_ref = module_ref.strip()
        exact = con.execute(
            "SELECT name, object_name, module_kind, fan_in, fan_out, n_subs, "
            "n_export, max_complexity FROM module WHERE name = ? LIMIT 20",
            (module_ref,),
        ).fetchall()
        if exact:
            first = exact[0]
            canonical = {
                "object_name": first["object_name"],
                "module_kind": first["module_kind"],
                "source": "graph_name",
            }
            return exact, canonical

        normalized = _strip_to_module_path(module_ref)
        if normalized.lower().endswith(".bsl") or "/" in normalized:
            object_name, module_kind = _canon_from_path(normalized)
            source = "module_path"
        else:
            object_name, module_kind = _canon_from_runtime_module(module_ref)
            source = "runtime_module"

        rows = con.execute(
            """
            SELECT name, object_name, module_kind, fan_in, fan_out, n_subs,
                   n_export, max_complexity
            FROM module
            WHERE object_name = ? AND module_kind = ?
            ORDER BY n_subs DESC, fan_in DESC, fan_out DESC
            LIMIT 20
            """,
            (object_name, module_kind),
        ).fetchall()
        return rows, {
            "object_name": object_name,
            "module_kind": module_kind,
            "source": source,
        }

    def resolve_module(self, module_ref: str) -> dict:
        """Describe how a user-supplied module reference maps to the graph."""
        with self._con() as con:
            rows, canonical = self._resolve_graph_modules(con, module_ref)
        return {
            "module_ref": module_ref,
            "canonical": canonical,
            "graph_modules": [dict(r) for r in rows],
        }

    def module_impact(self, module_ref: str, max_depth: int = 5,
                      max_edges: int = 600) -> dict:
        """Reverse impact for every subroutine in a resolved graph module."""
        with self._con() as con:
            module_rows, canonical = self._resolve_graph_modules(con, module_ref)
            module_names = [r["name"] for r in module_rows]
            seed_ids: list[int] = []
            for name_chunk in _chunks(module_names):
                placeholders = ",".join("?" * len(name_chunk))
                rows = con.execute(
                    f"SELECT id FROM subroutine WHERE module IN ({placeholders})",
                    name_chunk,
                ).fetchall()
                seed_ids.extend(r["id"] for r in rows)

            edges = self._traverse_ids(
                con, seed_ids, max_depth=max_depth, reverse=True,
                max_edges=max_edges,
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
            "edges": edges,
            "total": len(edges),
            "impacted_modules": impacted_modules,
        }

    def hotspots_for_graph_modules(self, module_names: list[str],
                                   limit: int = 20) -> list[dict]:
        """Risk rows whose canonical key matches any graph module name."""
        if not module_names:
            return []

        rows_by_path: dict[str, sqlite3.Row] = {}
        with self._con() as con:
            for name_chunk in _chunks(dict.fromkeys(module_names)):
                placeholders = ",".join("?" * len(name_chunk))
                rows = con.execute(
                    f"""
                    SELECT DISTINCT {self._QFULLCOLS_Q}
                    FROM quality q
                    JOIN module m
                      ON m.object_name = q.object_name
                     AND m.module_kind = q.module_kind
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
            out = con.execute(
                "SELECT dst AS module, weight FROM module_edge WHERE src = ? "
                "ORDER BY weight DESC LIMIT ?", (module, limit),
            ).fetchall()
            inc = con.execute(
                "SELECT src AS module, weight FROM module_edge WHERE dst = ? "
                "ORDER BY weight DESC LIMIT ?", (module, limit),
            ).fetchall()
            self_row = con.execute(
                "SELECT name, object_name, module_kind, fan_in, fan_out, n_subs, "
                "max_complexity FROM module WHERE name = ?", (module,),
            ).fetchone()
        return {
            "module": module,
            "info": dict(self_row) if self_row else None,
            "calls": [dict(r) for r in out],
            "called_by": [dict(r) for r in inc],
        }

    def module_edges(self, limit: int = 5000, min_weight: int = 1) -> list[dict]:
        """Module-level dependency edges enriched with module and quality metadata."""
        with self._con() as con:
            rows = con.execute(
                """
                WITH q AS (
                    SELECT object_name,
                           module_kind,
                           MIN(module_path) AS module_path,
                           MIN(domain) AS domain,
                           MIN(maintainability_score) AS maintainability_score,
                           MAX(has_n_plus_one) AS has_n_plus_one,
                           MAX(has_select_star) AS has_select_star
                    FROM quality
                    GROUP BY object_name, module_kind
                )
                SELECT e.src,
                       e.dst,
                       e.weight,
                       sm.object_name AS src_object,
                       sm.module_kind AS src_kind,
                       sm.fan_in AS src_fan_in,
                       sm.fan_out AS src_fan_out,
                       sq.module_path AS src_path,
                       sq.domain AS src_domain,
                       sq.maintainability_score AS src_maintainability,
                       dm.object_name AS dst_object,
                       dm.module_kind AS dst_kind,
                       dm.fan_in AS dst_fan_in,
                       dm.fan_out AS dst_fan_out,
                       dq.module_path AS dst_path,
                       dq.domain AS dst_domain,
                       dq.maintainability_score AS dst_maintainability
                FROM module_edge e
                JOIN module sm ON sm.name = e.src
                JOIN module dm ON dm.name = e.dst
                LEFT JOIN q sq ON sq.object_name = sm.object_name AND sq.module_kind = sm.module_kind
                LEFT JOIN q dq ON dq.object_name = dm.object_name AND dq.module_kind = dm.module_kind
                WHERE e.weight >= ?
                ORDER BY e.weight DESC
                LIMIT ?
                """,
                (min_weight, limit),
            ).fetchall()
        return [dict(row) for row in rows]


@lru_cache(maxsize=1)
def get_store() -> RentgenStore:
    return RentgenStore()
