"""Build the local Рентген SQLite store from precomputed data — no Neo4j.

Inputs (already produced by the Go scanner + bsl_scoring pipeline):
    data/rentgen_callgraph.ndjson   730,416 functions, 18,275 modules (call graph)
    gabriel_runs/scores.json        26,748 module quality scores

Output:
    data/rentgen.db                 single self-contained SQLite graph+quality store

The call-resolution logic (3-tier exact/alias/name-only) is ported verbatim from
src/modules/graph_api/services/rentgen_pipeline.py so the local store produces the
same edges Neo4j would. Only edges between *internal* subroutines are stored
(platform built-ins like Сообщить/Запрос.Выполнить are dropped — they have no
definition, which is exactly what dead-code / flow / impact analysis wants).

Run:
    C:\\Python311\\python.exe tools\\rentgen\\build_store.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NDJSON = ROOT / "data" / "rentgen_callgraph.ndjson"
SCORES = ROOT / "gabriel_runs" / "scores.json"
DB_PATH = ROOT / "data" / "rentgen.db"

# Call resolution precision switch.
#
# 1C/BSL semantics: an *unqualified* call `Функция()` can only bind to (a) the
# same module or (b) a function in a *global* common module. A *qualified* call
# `Модуль.Функция()` binds to that module's export. Resolving a bare/qualified
# call to ANY same-named function elsewhere ("name-only") is therefore unsound —
# it mis-attributes platform built-ins (Вставить, Добавить, Количество, …) to
# random user modules, inflating fan-in with phantom edges. For a risk/impact
# tool a missed edge (false negative) is far safer than an invented one (false
# positive), so name-only resolution is OFF by default. Set to True for higher
# recall at the cost of precision.
ALLOW_NAME_ONLY = False

# Module-type file stems we recognise when parsing score paths.
KNOWN_KINDS = {
    "commandmodule", "managermodule", "objectmodule", "recordsetmodule",
    "valuemanagermodule", "module", "form",
}


def _canon_from_callgraph(module: str) -> tuple[str, str]:
    """callgraph module name -> (object_name_lower, module_kind_lower)."""
    if "." in module:
        obj, kind = module.split(".", 1)
        return obj.lower(), kind.lower()
    # 1-segment = common module; its only file is Ext/Module.bsl
    return module.lower(), "module"


def _canon_from_path(module_path: str) -> tuple[str, str]:
    """score module_path -> (object_name_lower, module_kind_lower).

    AccountingRegisters/МСФО/Commands/X/Ext/CommandModule.bsl -> (мсфо, commandmodule)
    CommonModules/CPMDataExchange/Ext/Module.bsl              -> (cpmdataexchange, module)
    Catalogs/X/Forms/Y/Ext/Form/Module.bsl                    -> (x, form)
    """
    parts = module_path.replace("\\", "/").split("/")
    obj = parts[1] if len(parts) >= 2 else parts[0]
    stem = parts[-1].rsplit(".", 1)[0].lower()  # CommandModule.bsl -> commandmodule
    if "/Forms/" in module_path or "Form/Module" in module_path:
        kind = "form"
    elif stem in KNOWN_KINDS:
        kind = stem
    else:
        kind = "module"
    return obj.lower(), kind


def _connect_fresh(db_path: Path) -> sqlite3.Connection:
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        PRAGMA journal_mode = OFF;
        PRAGMA synchronous = OFF;
        PRAGMA temp_store = MEMORY;
        PRAGMA cache_size = -200000;
        """
    )
    return con


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE subroutine (
            id          INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            module      TEXT NOT NULL,
            line        INTEGER,
            is_export   INTEGER DEFAULT 0,
            is_function INTEGER DEFAULT 1,
            complexity  INTEGER DEFAULT 1
        );
        CREATE TABLE call_edge (
            caller_id INTEGER NOT NULL,
            callee_id INTEGER NOT NULL,
            line      INTEGER,
            tier      TEXT
        );
        CREATE TABLE module (
            name          TEXT PRIMARY KEY,
            object_name   TEXT,
            module_kind   TEXT,
            n_subs        INTEGER DEFAULT 0,
            n_export      INTEGER DEFAULT 0,
            n_functions   INTEGER DEFAULT 0,
            avg_complexity REAL DEFAULT 0,
            max_complexity INTEGER DEFAULT 0,
            sum_complexity INTEGER DEFAULT 0,
            fan_in        INTEGER DEFAULT 0,
            fan_out       INTEGER DEFAULT 0
        );
        CREATE TABLE module_edge (
            src    TEXT NOT NULL,
            dst    TEXT NOT NULL,
            weight INTEGER DEFAULT 1,
            PRIMARY KEY (src, dst)
        );
        CREATE TABLE quality (
            module_path         TEXT PRIMARY KEY,
            module_type         TEXT,
            domain              TEXT,
            loc                 INTEGER DEFAULT 0,
            complexity_score    INTEGER DEFAULT 0,
            documentation_score INTEGER DEFAULT 0,
            maintainability_score INTEGER DEFAULT 0,
            code_quality        INTEGER,
            has_n_plus_one      INTEGER DEFAULT 0,
            has_select_star     INTEGER DEFAULT 0,
            has_empty_catch     INTEGER DEFAULT 0,
            has_deep_nesting    INTEGER DEFAULT 0,
            has_magic_numbers   INTEGER DEFAULT 0,
            num_todo_fixme      INTEGER DEFAULT 0,
            object_name         TEXT,
            module_kind         TEXT,
            fan_in              INTEGER DEFAULT 0,
            fan_out             INTEGER DEFAULT 0
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )


def _iter_ndjson(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def build(db_path: Path = DB_PATH) -> dict:
    if not NDJSON.exists():
        raise FileNotFoundError(f"call graph NDJSON missing: {NDJSON}")
    if not SCORES.exists():
        raise FileNotFoundError(f"scores.json missing: {SCORES}")

    t0 = time.perf_counter()
    con = _connect_fresh(db_path)
    _create_schema(con)
    cur = con.cursor()

    # ---- PASS 1: subroutines + resolution indices ----------------------------
    print("[pass 1] loading subroutines + building resolution index ...", flush=True)
    id_map: dict[tuple[str, str], int] = {}      # (name_l, module_l) -> id  (exact)
    func_alias: dict[tuple[str, str], str] = {}  # (name_l, short_l) -> full module
    func_name_exported: dict[str, str] = {}      # name_l -> exported module
    func_by_name: dict[str, str] = {}            # name_l -> any module
    module_meta: dict[str, dict] = {}            # module -> aggregates

    batch = []
    sid = 0
    for obj in _iter_ndjson(NDJSON):
        name = obj["name"]
        module = obj["module"]
        is_export = 1 if obj.get("is_export") else 0
        is_function = 1 if obj.get("is_function", True) else 0
        complexity = int(obj.get("complexity", 1) or 1)
        line = int(obj.get("line", 0) or 0)
        sid += 1
        batch.append((sid, name, module, line, is_export, is_function, complexity))

        nl = name.lower()
        ml = module.lower()
        id_map[(nl, ml)] = sid
        short = module.split(".")[0].lower()
        ak = (nl, short)
        if ak not in func_alias or "." not in module:
            func_alias[ak] = module
        if is_export:
            func_name_exported[nl] = module
        if nl not in func_by_name:
            func_by_name[nl] = module

        mm = module_meta.get(module)
        if mm is None:
            o, k = _canon_from_callgraph(module)
            mm = module_meta[module] = {
                "object_name": o, "module_kind": k, "n_subs": 0, "n_export": 0,
                "n_functions": 0, "sum_complexity": 0, "max_complexity": 0,
            }
        mm["n_subs"] += 1
        mm["n_export"] += is_export
        mm["n_functions"] += is_function
        mm["sum_complexity"] += complexity
        if complexity > mm["max_complexity"]:
            mm["max_complexity"] = complexity

        if len(batch) >= 20000:
            cur.executemany(
                "INSERT INTO subroutine VALUES (?,?,?,?,?,?,?)", batch
            )
            batch.clear()
    if batch:
        cur.executemany("INSERT INTO subroutine VALUES (?,?,?,?,?,?,?)", batch)
    con.commit()
    n_subs = sid
    print(f"  subroutines: {n_subs:,}  modules: {len(module_meta):,}  "
          f"exact-keys: {len(id_map):,}  names: {len(func_by_name):,} "
          f"({len(func_name_exported):,} exported)", flush=True)

    # write module rows
    mrows = [
        (m, d["object_name"], d["module_kind"], d["n_subs"], d["n_export"],
         d["n_functions"],
         round(d["sum_complexity"] / d["n_subs"], 2) if d["n_subs"] else 0,
         d["max_complexity"], d["sum_complexity"], 0, 0)
        for m, d in module_meta.items()
    ]
    cur.executemany(
        "INSERT INTO module VALUES (?,?,?,?,?,?,?,?,?,?,?)", mrows
    )
    con.commit()

    # ---- PASS 2: resolve calls -> internal edges -----------------------------
    print("[pass 2] resolving call edges ...", flush=True)
    tier_counts = {"exact": 0, "alias": 0, "name": 0, "dropped": 0}
    edge_batch = []
    n_edges = 0
    mod_edge: dict[tuple[str, str], int] = {}

    for obj in _iter_ndjson(NDJSON):
        caller_module = obj["module"]
        caller_ml = caller_module.lower()
        caller_id = id_map.get((obj["name"].lower(), caller_ml))
        if caller_id is None:
            continue
        cline = int(obj.get("line", 0) or 0)
        for call in obj.get("calls") or []:
            if "." in call:
                p0, p1 = call.split(".", 1)
                cnl = p1.lower()
                csl = p0.lower()
                if (cnl, csl) in id_map:
                    callee_module, tier = p0, "exact"
                elif (cnl, csl) in func_alias:
                    callee_module, tier = func_alias[(cnl, csl)], "alias"
                elif ALLOW_NAME_ONLY and cnl in func_name_exported:
                    callee_module, tier = func_name_exported[cnl], "name"
                elif ALLOW_NAME_ONLY and cnl in func_by_name:
                    callee_module, tier = func_by_name[cnl], "name"
                else:
                    tier_counts["dropped"] += 1
                    continue  # method-on-object / built-in -> not a module call
                callee_name_l = cnl
            else:
                cnl = call.lower()
                if (cnl, caller_ml) in id_map:
                    callee_module, tier = caller_module, "exact"
                elif "." in caller_module and (cnl, caller_module.split(".")[0].lower()) in id_map:
                    callee_module, tier = caller_module.split(".")[0], "alias"
                elif ALLOW_NAME_ONLY and cnl in func_name_exported:
                    callee_module, tier = func_name_exported[cnl], "name"
                elif ALLOW_NAME_ONLY and cnl in func_by_name:
                    callee_module, tier = func_by_name[cnl], "name"
                else:
                    tier_counts["dropped"] += 1
                    continue  # bare built-in / non-local call -> drop (sound for 1C)
                callee_name_l = cnl

            callee_id = id_map.get((callee_name_l, callee_module.lower()))
            if callee_id is None:
                tier_counts["dropped"] += 1
                continue  # platform built-in / unresolved -> not an internal edge
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
            edge_batch.append((caller_id, callee_id, cline, tier))
            n_edges += 1
            if caller_module != callee_module:
                mk = (caller_module, callee_module)
                mod_edge[mk] = mod_edge.get(mk, 0) + 1
            if len(edge_batch) >= 50000:
                cur.executemany("INSERT INTO call_edge VALUES (?,?,?,?)", edge_batch)
                edge_batch.clear()
    if edge_batch:
        cur.executemany("INSERT INTO call_edge VALUES (?,?,?,?)", edge_batch)
    con.commit()
    print(f"  internal call edges: {n_edges:,}  "
          f"(exact={tier_counts['exact']:,} alias={tier_counts['alias']:,} "
          f"name={tier_counts['name']:,} dropped={tier_counts['dropped']:,})  "
          f"name_only={'ON' if ALLOW_NAME_ONLY else 'OFF'}",
          flush=True)

    # module-level edges
    cur.executemany(
        "INSERT INTO module_edge VALUES (?,?,?)",
        [(s, d, w) for (s, d), w in mod_edge.items()],
    )
    con.commit()

    # ---- indices --------------------------------------------------------------
    print("[index] building indices ...", flush=True)
    con.executescript(
        """
        CREATE INDEX ix_sub_name ON subroutine(name);
        CREATE INDEX ix_sub_module ON subroutine(module);
        CREATE INDEX ix_sub_export ON subroutine(is_export);
        CREATE INDEX ix_edge_caller ON call_edge(caller_id);
        CREATE INDEX ix_edge_callee ON call_edge(callee_id);
        CREATE INDEX ix_medge_src ON module_edge(src);
        CREATE INDEX ix_medge_dst ON module_edge(dst);
        CREATE INDEX ix_mod_canon ON module(object_name, module_kind);
        CREATE INDEX ix_q_canon ON quality(object_name, module_kind);
        CREATE INDEX ix_q_maint ON quality(maintainability_score);
        CREATE INDEX ix_q_domain ON quality(domain);
        """
    )
    con.commit()

    # ---- fan metrics (module level) ------------------------------------------
    print("[fans] computing module fan-in / fan-out ...", flush=True)
    cur.execute(
        "UPDATE module SET fan_out = (SELECT COUNT(*) FROM module_edge e WHERE e.src = module.name)"
    )
    cur.execute(
        "UPDATE module SET fan_in = (SELECT COUNT(*) FROM module_edge e WHERE e.dst = module.name)"
    )
    con.commit()

    # ---- quality --------------------------------------------------------------
    print("[quality] loading scores.json ...", flush=True)
    scores = json.loads(SCORES.read_text(encoding="utf-8"))
    qrows = []
    for m in scores.get("modules", []):
        path = m["module_path"]
        o, k = _canon_from_path(path)
        qrows.append((
            path, m.get("module_type", "Unknown"), m.get("domain", "Прочее"),
            int(m.get("loc", 0)), int(m.get("complexity_score", 0)),
            int(m.get("documentation_score", 0)), int(m.get("maintainability_score", 0)),
            m.get("code_quality"),
            1 if m.get("has_n_plus_one") else 0, 1 if m.get("has_select_star") else 0,
            1 if m.get("has_empty_catch") else 0, 1 if m.get("has_deep_nesting") else 0,
            1 if m.get("has_magic_numbers") else 0, int(m.get("num_todo_fixme", 0)),
            o, k, 0, 0,
        ))
    cur.executemany(
        "INSERT OR REPLACE INTO quality VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", qrows
    )
    con.commit()
    print(f"  quality rows: {len(qrows):,}", flush=True)

    # ---- JOIN: attach graph fans to quality by (object_name, module_kind) -----
    print("[join] attaching call-graph fans to quality rows ...", flush=True)
    # Aggregate module fans to canonical key (multiple command/form modules may
    # collapse to one callgraph module — take the max fan as the representative).
    cur.execute(
        """
        UPDATE quality
        SET fan_in = COALESCE((
                SELECT MAX(m.fan_in) FROM module m
                WHERE m.object_name = quality.object_name
                  AND m.module_kind = quality.module_kind), 0),
            fan_out = COALESCE((
                SELECT MAX(m.fan_out) FROM module m
                WHERE m.object_name = quality.object_name
                  AND m.module_kind = quality.module_kind), 0)
        """
    )
    con.commit()
    joined = cur.execute(
        "SELECT COUNT(*) FROM quality WHERE fan_in > 0 OR fan_out > 0"
    ).fetchone()[0]
    cov = 100.0 * joined / max(len(qrows), 1)

    # ---- meta -----------------------------------------------------------------
    meta = {
        "built_at_unix": str(int(t0)),
        "n_subroutines": str(n_subs),
        "n_modules": str(len(module_meta)),
        "n_call_edges": str(n_edges),
        "n_module_edges": str(len(mod_edge)),
        "n_quality": str(len(qrows)),
        "join_coverage_pct": f"{cov:.1f}",
        "source_ndjson": str(NDJSON),
        "source_scores": str(SCORES),
    }
    cur.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.execute("PRAGMA journal_mode = WAL;")
    con.execute("VACUUM;")
    con.close()

    dt = time.perf_counter() - t0
    size_mb = db_path.stat().st_size / 1e6
    print("\n=== BUILD COMPLETE ===", flush=True)
    print(f"  db: {db_path}  ({size_mb:.1f} MB)  in {dt:.1f}s")
    print(f"  subroutines={n_subs:,}  modules={len(module_meta):,}  "
          f"call_edges={n_edges:,}  module_edges={len(mod_edge):,}")
    print(f"  quality={len(qrows):,}  join_coverage={cov:.1f}% "
          f"({joined:,} quality modules have call-graph fans)")
    return meta


if __name__ == "__main__":
    out = DB_PATH if len(sys.argv) < 2 else Path(sys.argv[1])
    build(out)
