"""Build the local Рентген SQLite store from precomputed data — no Neo4j.

Inputs (already produced by the Go scanner + bsl_scoring pipeline):
    data/rentgen_callgraph.ndjson   730,416 functions, 18,275 modules (call graph)
    gabriel_runs/scores.json        26,748 module quality scores

Output:
    data/rentgen.db                 single self-contained SQLite graph+quality store

Canonical graph references preserve the complete root-relative source path.
Only unique local and known exported common-module calls bind; unsupported and
ambiguous calls remain queryable evidence with source and span provenance.

Run:
    C:\\Python311\\python.exe tools\\rentgen\\build_store.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from .identity import (
    IDENTITY_VERSION,
    SCHEMA_VERSION,
    identifier_key,
    module_identity,
    source_key,
    source_metadata,
)

ROOT = Path(__file__).resolve().parents[1]

# Входные данные сборки. Переопределяются переменными окружения, чтобы можно было
# держать выгрузки нескольких конфигураций рядом и собирать каждую из своего
# каталога, не копируя файлы в одно жёстко заданное место.
#
# Каталог `gabriel_runs` называется так по имени эксперимента, из которого вырос
# пайплайн оценки качества. Имя не говорящее, но переименование сломало бы все
# существующие установки и инструкции, поэтому вместо этого путь сделан
# настраиваемым, а здесь написано, что это такое: результат `tools.bsl_scoring`,
# то есть оценки качества по каждому модулю конфигурации.
NDJSON = Path(
    os.getenv("RENTGEN_CALLGRAPH_PATH") or ROOT / "data" / "rentgen_callgraph.ndjson"
)
SCORES = Path(os.getenv("RENTGEN_SCORES_PATH") or ROOT / "gabriel_runs" / "scores.json")
DB_PATH = ROOT / "data" / "rentgen.db"
REPLACE_ATTEMPTS = 3
REPLACE_RETRY_DELAY_SEC = 0.1

REQUIRED_TABLES = {
    "subroutine",
    "call_edge",
    "call_site",
    "module",
    "module_edge",
    "quality",
    "meta",
}


@dataclass(frozen=True)
class BuildInputs:
    callgraph_path: Path
    scores_path: Path | None


class BuildMode(Enum):
    LEGACY = "legacy"
    SNAPSHOT = "snapshot"


def _connect_fresh(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    try:
        con.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            PRAGMA temp_store = FILE;
            PRAGMA cache_size = -200000;
            PRAGMA foreign_keys = ON;
            """
        )
    except BaseException:
        try:
            con.close()
        except BaseException:
            # Preserve the original setup failure, including cancellation.
            pass
        raise
    return con


def _create_schema(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE subroutine (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            module      TEXT NOT NULL,
            line        INTEGER,
            is_export   INTEGER DEFAULT 0,
            is_function INTEGER DEFAULT 1,
            complexity  INTEGER DEFAULT 1,
            name_key TEXT,
            source_path TEXT,
            end_line INTEGER,
            declaration_ambiguous INTEGER DEFAULT 0,
            source_provenance TEXT,
            FOREIGN KEY(module) REFERENCES module(name)
        );
        CREATE TABLE call_edge (
            caller_id TEXT NOT NULL REFERENCES subroutine(id),
            callee_id TEXT NOT NULL REFERENCES subroutine(id),
            line      INTEGER,
            tier      TEXT,
            site_id TEXT REFERENCES call_site(id)
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
            fan_out       INTEGER DEFAULT 0,
            display_name TEXT,
            display_key TEXT,
            source_path TEXT,
            source_key TEXT UNIQUE,
            source_provenance TEXT,
            common_key TEXT
        );
        CREATE TABLE module_edge (
            src    TEXT NOT NULL REFERENCES module(name),
            dst    TEXT NOT NULL REFERENCES module(name),
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
            fan_out             INTEGER DEFAULT 0,
            module_id TEXT REFERENCES module(name),
            source_key TEXT UNIQUE
        );
        CREATE TABLE call_site (
            id TEXT PRIMARY KEY,
            caller_id TEXT NOT NULL REFERENCES subroutine(id),
            callee_id TEXT REFERENCES subroutine(id),
            target TEXT NOT NULL,
            line INTEGER, column INTEGER, end_line INTEGER, end_column INTEGER,
            kind TEXT, span_provenance TEXT, reason TEXT,
            declaration_line INTEGER
        );
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )


def _validate_callgraph_record(record: dict, path: Path, line_number: int) -> None:
    """Validate every field consumed by the graph builder."""

    def invalid(message: str) -> ValueError:
        return ValueError(f"invalid NDJSON in {path} at line {line_number}: {message}")

    for field in ("name", "module"):
        if not isinstance(record.get(field), str):
            raise invalid(f"{field} must be a string")

    for field in ("line", "complexity"):
        if field in record and (
            not isinstance(record[field], int) or isinstance(record[field], bool)
        ):
            raise invalid(f"{field} must be an integer")

    for field in ("is_export", "is_function"):
        if field in record and not isinstance(record[field], bool):
            raise invalid(f"{field} must be a boolean")

    calls = record.get("calls")
    if calls is not None and (
        not isinstance(calls, list) or any(not isinstance(call, str) for call in calls)
    ):
        raise invalid("calls must be a list of strings or null")

    if "source_path" in record and (
        not isinstance(record["source_path"], str) or not record["source_path"]
    ):
        raise invalid("source_path must be a nonempty string")
    if "end_line" in record and (
        not isinstance(record["end_line"], int) or isinstance(record["end_line"], bool)
    ):
        raise invalid("end_line must be an integer")
    if "call_sites" in record:
        sites = record["call_sites"]
        if not isinstance(sites, list):
            raise invalid("call_sites must be a list")
        for site in sites:
            if (
                not isinstance(site, dict)
                or not isinstance(site.get("target"), str)
                or not site["target"]
            ):
                raise invalid("call_sites target must be a nonempty string")
            if site.get("kind") not in {"direct", "qualified", "unresolved"}:
                raise invalid("call_sites kind must be direct, qualified or unresolved")
            for field in ("line", "column", "end_line", "end_column"):
                value = site.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    raise invalid(f"call_sites {field} must be a positive integer")
            if (site["end_line"], site["end_column"]) <= (site["line"], site["column"]):
                raise invalid("call_sites end must follow its start")


def _iter_ndjson(path: Path):
    """Yield every non-blank record, accepting UTF-8 with or without a BOM."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"invalid NDJSON in {path} at line {line_number}: {exc.msg}"
                    ) from exc
                if not isinstance(record, dict):
                    raise ValueError(
                        f"invalid NDJSON in {path} at line {line_number}: "
                        "expected a JSON object"
                    )
                _validate_callgraph_record(record, path, line_number)
                yield record
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"call graph NDJSON must be UTF-8 (UTF-8 BOM is supported): {path}"
        ) from exc


def _load_scores(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"scores.json must be UTF-8 (UTF-8 BOM is supported): {path}"
        ) from exc
    try:
        scores = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid scores.json in {path}: {exc.msg}") from exc
    if not isinstance(scores, dict) or not isinstance(scores.get("modules"), list):
        raise ValueError(f"invalid scores.json in {path}: 'modules' must be a list")
    return scores


def _score_int(module: dict, field: str, index: int) -> int:
    try:
        return int(module.get(field, 0))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"invalid score data in module {index}: {field} must be an integer"
        ) from exc


def _build_temporary(db_path: Path) -> tuple[dict, int]:
    if not NDJSON.exists():
        raise FileNotFoundError(f"call graph NDJSON missing: {NDJSON}")
    if not SCORES.exists():
        raise FileNotFoundError(f"scores.json missing: {SCORES}")

    # Two distinct clocks, deliberately: perf_counter measures how long the build
    # took (monotonic, arbitrary origin); time.time() is the wall-clock instant the
    # store was built. Only the latter is meaningful in meta — "when was this
    # snapshot taken" is the first question an auditor asks of the evidence.
    t0 = time.perf_counter()
    built_at = time.time()
    con = _connect_fresh(db_path)
    try:
        return _populate_store(con, t0, built_at)
    finally:
        con.close()


def _populate_store(
    con: sqlite3.Connection,
    t0: float,
    built_at: float,
    *,
    inputs: BuildInputs | None = None,
    mode: BuildMode = BuildMode.LEGACY,
    binding=None,
    source_paths: tuple[str, ...] = (),
) -> tuple[dict, int]:
    inputs = inputs if inputs is not None else BuildInputs(NDJSON, SCORES)
    _create_schema(con)

    # Stage the corpus once on disk. Both declaration indexing and binding read
    # this same staged input; there is no second raw corpus in Python memory.
    diagnostics = sys.stderr if mode is BuildMode.SNAPSHOT else sys.stdout
    print(
        "[stage] reading source identity and declarations ...",
        file=diagnostics,
        flush=True,
    )
    con.execute(
        "CREATE TABLE input_stage (module_id TEXT, name_key TEXT, line INTEGER, digest TEXT, raw TEXT)"
    )
    n_subs = 0
    for obj in _iter_ndjson(inputs.callgraph_path):
        mid, path, provenance = module_identity(obj)
        semantic_record = {
            k: v for k, v in obj.items() if k not in {"module", "source_path", "name"}
        }
        digest = hashlib.sha256(
            json.dumps(semantic_record, ensure_ascii=False, sort_keys=True).encode(
                "utf-8"
            )
        ).hexdigest()
        con.execute(
            "INSERT INTO input_stage VALUES (?,?,?,?,?)",
            (
                mid,
                identifier_key(obj["name"]),
                obj.get("line", 0),
                digest,
                json.dumps(
                    obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ),
            ),
        )
        n_subs += 1
    if not n_subs and mode is BuildMode.LEGACY:
        raise ValueError(
            f"call graph NDJSON contains no subroutines: {inputs.callgraph_path}"
        )
    con.execute("CREATE INDEX ix_stage ON input_stage(module_id,name_key,line,digest)")

    module_meta = {}
    for mid, raw in con.execute(
        "SELECT module_id,raw FROM input_stage ORDER BY module_id,raw"
    ):
        obj = json.loads(raw)
        _, path, provenance = module_identity(obj)
        if mid in module_meta:
            if module_meta[mid]["source_path"] != path:
                raise ValueError(
                    f"ambiguous source_path normalization: {path!r} and {module_meta[mid]['source_path']!r}"
                )
            continue
        owner, kind, common = source_metadata(path, obj["module"])
        module_meta[mid] = {
            "source_path": path,
            "provenance": provenance,
            "common": common,
        }
        con.execute(
            "INSERT INTO module(name,object_name,module_kind,display_name,display_key,source_path,source_key,source_provenance,common_key) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                mid,
                owner,
                kind,
                obj["module"],
                identifier_key(obj["module"]),
                path,
                source_key(path) if path else None,
                provenance,
                common,
            ),
        )

    # Verified coverage also preserves source modules with zero declarations.
    for path in sorted(source_paths):
        mid = "source:" + source_key(path)
        if mid in module_meta:
            continue
        display = Path(path).stem
        owner, kind, common = source_metadata(path, display)
        module_meta[mid] = {
            "source_path": path,
            "provenance": "source_path",
            "common": common,
        }
        con.execute(
            "INSERT INTO module(name,object_name,module_kind,display_name,display_key,source_path,source_key,source_provenance,common_key) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                mid,
                owner,
                kind,
                display,
                identifier_key(display),
                path,
                source_key(path),
                "source_path",
                common,
            ),
        )

    # A unique declaration ID depends on its source, normalized name and start
    # line. Same-location variants add a semantic content digest and ordinal;
    # display aliases never enter an ID, and no duplicate body is discarded.
    duplicate_locations = set(
        con.execute(
            "SELECT module_id,name_key,line FROM input_stage GROUP BY module_id,name_key,line HAVING COUNT(*)>1"
        )
    )
    symbols = {}
    common_modules = {}
    for mid, info in module_meta.items():
        if info["common"]:
            common_modules.setdefault(info["common"], []).append(mid)
    con.execute(
        "CREATE TABLE staged_calls (caller_id TEXT, module_id TEXT, line INTEGER, sites TEXT, provenance TEXT)"
    )
    previous = None
    duplicate = 0
    for mid, nk, line, digest, raw in con.execute(
        "SELECT * FROM input_stage ORDER BY module_id,name_key,line,digest,raw"
    ):
        obj = json.loads(raw)
        location = (mid, nk, line)
        identity = (*location, digest) if location in duplicate_locations else location
        duplicate = duplicate + 1 if identity == previous else 1
        previous = identity
        sid = (
            "symbol:"
            + hashlib.sha256(
                json.dumps(identity, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            + f":{duplicate}"
        )
        info = module_meta[mid]
        export = int(bool(obj.get("is_export")))
        con.execute(
            "INSERT INTO subroutine(id,name,module,line,is_export,is_function,complexity,name_key,source_path,end_line,source_provenance) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                sid,
                obj["name"],
                mid,
                line,
                export,
                int(obj.get("is_function", True)),
                int(obj.get("complexity", 1) or 1),
                nk,
                info["source_path"],
                obj.get("end_line"),
                info["provenance"],
            ),
        )
        symbols.setdefault((mid, nk), []).append((sid, export))
        if "call_sites" in obj:
            sites = obj["call_sites"]
            span_provenance = "physical"
        else:
            # Old callers only carried the declaration line, not a call span.
            sites = [
                {"target": c, "kind": "qualified" if "." in c else "direct"}
                for c in (obj.get("calls") or [])
            ]
            span_provenance = "legacy_declaration_only"
        con.execute(
            "INSERT INTO staged_calls VALUES (?,?,?,?,?)",
            (sid, mid, line, json.dumps(sites, ensure_ascii=False), span_provenance),
        )
    for candidates in symbols.values():
        if len(candidates) > 1:
            con.executemany(
                "UPDATE subroutine SET declaration_ambiguous=1 WHERE id=?",
                [(sid,) for sid, _ in candidates],
            )
    con.execute("DROP TABLE input_stage")
    con.executescript(
        """
        CREATE INDEX ix_sub_name_key ON subroutine(name_key);
        CREATE INDEX ix_sub_module ON subroutine(module);
        CREATE INDEX ix_sub_export ON subroutine(is_export);
        CREATE INDEX ix_mod_display ON module(display_key);
        UPDATE module SET
            n_subs=(SELECT COUNT(*) FROM subroutine s WHERE s.module=module.name),
            n_export=(SELECT SUM(is_export) FROM subroutine s WHERE s.module=module.name),
            n_functions=(SELECT SUM(is_function) FROM subroutine s WHERE s.module=module.name),
            avg_complexity=(SELECT ROUND(AVG(complexity),2) FROM subroutine s WHERE s.module=module.name),
            max_complexity=(SELECT MAX(complexity) FROM subroutine s WHERE s.module=module.name),
            sum_complexity=(SELECT SUM(complexity) FROM subroutine s WHERE s.module=module.name);
    """
    )

    print(
        "[bind] retaining calls and resolving bounded static targets ...",
        file=diagnostics,
        flush=True,
    )
    n_edges = 0
    n_unresolved = 0
    mod_edge = {}
    for caller, mid, declaration_line, raw_sites, provenance in con.execute(
        "SELECT * FROM staged_calls ORDER BY caller_id"
    ):
        for ordinal, site in enumerate(json.loads(raw_sites)):
            target, kind = site["target"], site["kind"]
            parts = target.split(".")
            callee_module = None
            reason = None
            if kind == "unresolved":
                reason = "computed_receiver"
            elif kind == "direct" and len(parts) == 1 and target.isidentifier():
                callee_module = mid
            elif (
                kind == "qualified"
                and len(parts) == 2
                and all(p.isidentifier() for p in parts)
            ):
                modules = common_modules.get(identifier_key(parts[0]), [])
                if len(modules) == 1:
                    callee_module = modules[0]
                else:
                    reason = "ambiguous_receiver" if modules else "unknown_receiver"
            else:
                reason = "unsupported_receiver"
            callee = None
            if callee_module is not None:
                candidates = symbols.get((callee_module, identifier_key(parts[-1])), [])
                if len(candidates) != 1:
                    reason = "ambiguous_target" if candidates else "unknown_target"
                elif kind == "qualified" and not candidates[0][1]:
                    reason = "not_exported"
                else:
                    callee = candidates[0][0]
            site_id = caller + f"/call:{ordinal}"
            con.execute(
                "INSERT INTO call_site VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    site_id,
                    caller,
                    callee,
                    target,
                    site.get("line"),
                    site.get("column"),
                    site.get("end_line"),
                    site.get("end_column"),
                    kind,
                    provenance,
                    reason,
                    declaration_line,
                ),
            )
            if callee is None:
                n_unresolved += 1
                continue
            con.execute(
                "INSERT INTO call_edge VALUES (?,?,?,?,?)",
                (
                    caller,
                    callee,
                    site.get("line"),
                    "local" if kind == "direct" else "common_export",
                    site_id,
                ),
            )
            n_edges += 1
            if mid != callee_module:
                pair = (mid, callee_module)
                mod_edge[pair] = mod_edge.get(pair, 0) + 1
    con.execute("DROP TABLE staged_calls")
    con.executemany(
        "INSERT INTO module_edge VALUES (?,?,?)",
        [(s, d, w) for (s, d), w in sorted(mod_edge.items())],
    )
    con.executescript(
        """
        CREATE INDEX ix_edge_caller ON call_edge(caller_id);
        CREATE INDEX ix_edge_callee ON call_edge(callee_id);
        CREATE INDEX ix_site_caller ON call_site(caller_id);
        CREATE INDEX ix_site_reason ON call_site(reason);
        CREATE INDEX ix_medge_src ON module_edge(src);
        CREATE INDEX ix_medge_dst ON module_edge(dst);
        CREATE INDEX ix_q_module ON quality(module_id);
        CREATE INDEX ix_q_maint ON quality(maintainability_score);
        CREATE INDEX ix_q_domain ON quality(domain);
        UPDATE module SET fan_out=(SELECT COUNT(*) FROM module_edge e WHERE e.src=module.name);
        UPDATE module SET fan_in=(SELECT COUNT(*) FROM module_edge e WHERE e.dst=module.name);
    """
    )

    scores = (
        _load_scores(inputs.scores_path)
        if inputs.scores_path is not None
        else {"modules": []}
    )
    qrows = []
    for index, m in enumerate(scores["modules"], start=1):
        if not isinstance(m, dict) or not isinstance(m.get("module_path"), str):
            raise ValueError(
                f"invalid score data in module {index}: module_path must be a string"
            )
        path = m["module_path"]
        key = source_key(path)
        module_id = "source:" + key
        if module_id not in module_meta:
            module_id = None
        owner, kind, _ = source_metadata(path, path)
        qrows.append(
            (
                path,
                m.get("module_type", "Unknown"),
                m.get("domain", "Прочее"),
                _score_int(m, "loc", index),
                _score_int(m, "complexity_score", index),
                _score_int(m, "documentation_score", index),
                _score_int(m, "maintainability_score", index),
                m.get("code_quality"),
                int(bool(m.get("has_n_plus_one"))),
                int(bool(m.get("has_select_star"))),
                int(bool(m.get("has_empty_catch"))),
                int(bool(m.get("has_deep_nesting"))),
                int(bool(m.get("has_magic_numbers"))),
                _score_int(m, "num_todo_fixme", index),
                owner,
                kind,
                0,
                0,
                module_id,
                key,
            )
        )
    try:
        con.executemany(
            "INSERT INTO quality VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            sorted(qrows),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError("ambiguous duplicate source_path in quality input") from exc
    con.execute(
        """
        UPDATE quality SET
            fan_in=COALESCE((SELECT fan_in FROM module WHERE name=quality.module_id),0),
            fan_out=COALESCE((SELECT fan_out FROM module WHERE name=quality.module_id),0)
    """
    )
    joined = con.execute(
        "SELECT COUNT(*) FROM quality WHERE module_id IS NOT NULL"
    ).fetchone()[0]
    cov = 100.0 * joined / max(len(qrows), 1)

    # ---- meta -----------------------------------------------------------------
    meta = {
        "build_id": str(uuid.uuid4()) if mode is BuildMode.LEGACY else "",
        "schema_version": SCHEMA_VERSION,
        "identity_version": IDENTITY_VERSION,
        "identity_precision": "legacy"
        if any(m["provenance"] == "legacy_alias" for m in module_meta.values())
        else "source_path",
        "n_unresolved_calls": str(n_unresolved),
        "n_call_sites": str(n_edges + n_unresolved),
        "semantic_scope": "bounded_static_calls; preprocessing and dynamic types unresolved",
        "built_at_unix": str(int(built_at)),
        "build_duration_sec": f"{time.perf_counter() - t0:.1f}",
        "n_subroutines": str(n_subs),
        "n_modules": str(len(module_meta)),
        "n_call_edges": str(n_edges),
        "n_module_edges": str(len(mod_edge)),
        "n_quality": str(len(qrows)),
        "join_coverage_pct": f"{cov:.1f}",
        "source_ndjson": str(inputs.callgraph_path),
        "source_scores": str(inputs.scores_path),
    }
    if mode is BuildMode.SNAPSHOT:
        if binding is None or inputs.scores_path is not None:
            raise ValueError("snapshot mode requires binding and no scores")
        for key in (
            "built_at_unix",
            "build_duration_sec",
            "source_ndjson",
            "source_scores",
            "join_coverage_pct",
        ):
            del meta[key]
        meta.update(asdict(binding))
        meta["build_id"] = hashlib.sha256(
            json.dumps(
                asdict(binding),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        meta["sqlite_version"] = sqlite3.sqlite_version
        meta["quality"] = "unavailable"
    con.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.execute(
        "PRAGMA journal_mode = WAL;"
        if mode is BuildMode.LEGACY
        else "PRAGMA journal_mode = DELETE;"
    )
    con.execute("VACUUM;")
    return meta, joined


def build_snapshot_graph(
    inputs: BuildInputs,
    output_path: Path,
    binding,
    *,
    source_paths: tuple[str, ...] = (),
):
    """Build one fresh caller-owned graph; never replace a global/published DB."""
    output_path = Path(output_path)
    with output_path.open("xb"):
        pass
    try:
        con = _connect_fresh(output_path)
        try:
            meta, _ = _populate_store(
                con,
                0,
                0,
                inputs=inputs,
                mode=BuildMode.SNAPSHOT,
                binding=binding,
                source_paths=source_paths,
            )
        finally:
            con.close()
        _validate_database(output_path, meta)
        if any(
            Path(str(output_path) + suffix).exists()
            for suffix in ("-wal", "-shm", "-journal")
        ):
            raise RuntimeError("snapshot graph has mutable sidecars")
        return binding
    except BaseException:
        try:
            _cleanup_temporary_store(output_path)
        except BaseException:
            # Cleanup must not hide the failure that prevented a valid graph.
            pass
        raise


def _validate_database(db_path: Path, expected_meta: dict) -> None:
    """Reject an incomplete or corrupt temporary database before publication."""
    con = sqlite3.connect(db_path)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise RuntimeError(
                f"temporary Rentgen store failed integrity_check: {integrity!r}"
            )
        foreign_keys = con.execute("PRAGMA foreign_key_check").fetchone()
        if foreign_keys:
            raise RuntimeError(
                f"temporary Rentgen store failed foreign_key_check: {foreign_keys!r}"
            )

        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise RuntimeError(
                "temporary Rentgen store is missing required tables: "
                + ", ".join(sorted(missing))
            )

        count_contract = {
            "subroutine": "n_subroutines",
            "module": "n_modules",
            "call_edge": "n_call_edges",
            "call_site": "n_call_sites",
            "module_edge": "n_module_edges",
            "quality": "n_quality",
        }
        for table, meta_key in count_contract.items():
            actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            expected = int(expected_meta[meta_key])
            if actual != expected:
                raise RuntimeError(
                    f"temporary Rentgen store is incomplete: {table} has "
                    f"{actual} rows, expected {expected}"
                )

        stored_meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        for key, value in expected_meta.items():
            if stored_meta.get(key) != value:
                raise RuntimeError(
                    f"temporary Rentgen store has incomplete meta value: {key}"
                )
    finally:
        con.close()


def _replace_with_retry(source: Path, target: Path) -> None:
    """Atomically publish, tolerating only a short-lived Windows file lock."""
    for attempt in range(1, REPLACE_ATTEMPTS + 1):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS:
                raise
            time.sleep(REPLACE_RETRY_DELAY_SEC)


def _cleanup_temporary_store(db_path: Path, *, include_database: bool = True) -> None:
    suffixes = ("", "-wal", "-shm", "-journal")
    if not include_database:
        suffixes = suffixes[1:]
    for suffix in suffixes:
        Path(f"{db_path}{suffix}").unlink(missing_ok=True)


def _build_summary(
    db_path: Path, size_mb: float, meta: dict, joined: int
) -> tuple[str, ...]:
    """Prepare every fallible summary calculation before publication."""
    return (
        "\n=== BUILD COMPLETE ===",
        f"  db: {db_path}  ({size_mb:.1f} MB)  "
        f"in {float(meta['build_duration_sec']):.1f}s",
        f"  subroutines={int(meta['n_subroutines']):,}  "
        f"modules={int(meta['n_modules']):,}  "
        f"call_edges={int(meta['n_call_edges']):,}  "
        f"module_edges={int(meta['n_module_edges']):,}",
        f"  quality={int(meta['n_quality']):,}  "
        f"join_coverage={meta['join_coverage_pct']}% "
        f"({joined:,} quality modules have call-graph fans)",
    )


class PublicationOutcomeUnknown(RuntimeError):
    """The candidate disappeared but its publication cannot be confirmed."""


def _published_build_matches(db_path: Path, build_id: str) -> bool:
    try:
        con = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key='build_id'").fetchone()
            return row == (build_id,)
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return False


def build(db_path: Path = DB_PATH) -> dict:
    """Build, validate, and atomically publish a complete Rentgen store.

    Empty call graphs are rejected. Inputs may be UTF-8 with or without a UTF-8
    BOM; other encodings are rejected before the accepted database is replaced.

    The atomic replace is the commit point. Before it, every exception (including
    cancellation) leaves the accepted database unchanged. After it, console
    reporting is best effort, so a closed stream or cancellation cannot report a
    committed rebuild as failed.
    Recoverable interruptions at replacement are reconciled using the unique
    build_id in the target. Hard process termination has no acknowledgement;
    the published file's metadata is authoritative on restart.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{db_path.name}.", suffix=".tmp", dir=db_path.parent
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    publication_attempted = False
    try:
        meta, joined = _build_temporary(temporary_path)
        _validate_database(temporary_path, meta)
        size_mb = temporary_path.stat().st_size / 1e6
        summary = _build_summary(db_path, size_mb, meta, joined)
        _cleanup_temporary_store(temporary_path, include_database=False)
        publication_attempted = True
        _replace_with_retry(temporary_path, db_path)
    except BaseException as error:
        if publication_attempted and not temporary_path.exists():
            if not _published_build_matches(db_path, meta["build_id"]):
                raise PublicationOutcomeUnknown(
                    f"Publication outcome unknown for build {meta['build_id']}; "
                    "inspect target metadata before retrying"
                ) from error
            # Replacement committed before acknowledgement was interrupted.
        else:
            try:
                _cleanup_temporary_store(temporary_path)
            except BaseException:
                # Cleanup is best effort and must never replace the build failure.
                pass
            raise

    try:
        for line in summary:
            print(line, flush=True)
    except BaseException:
        # Publication already committed. Diagnostics cannot change its outcome.
        pass
    return meta


def _parse_args(argv: list[str]) -> Path:
    """Куда писать базу.

    Три формы, от самой удобной к самой прямой:
      без аргументов          -> data/rentgen.db (историческая единственная база)
      --store-id erp_uh       -> data/stores/erp_uh.db (конфигурация в мультисторе)
      <путь>                  -> ровно этот файл

    Идентификатор проверяется тем же валидатором, что и на чтении, поэтому
    собрать базу под именем, которое потом нельзя будет открыть, не выйдет.
    """

    parser = argparse.ArgumentParser(
        description="Build the local Рентген SQLite store from the scanned call graph.",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="explicit output path; defaults to data/rentgen.db",
    )
    parser.add_argument(
        "--store-id",
        help="named configuration: writes data/stores/<store-id>.db",
    )
    args = parser.parse_args(argv)

    if args.store_id and args.output:
        parser.error("pass either --store-id or an explicit output path, not both")

    if args.store_id:
        from .store import STORES_DIR, validate_store_id

        validate_store_id(args.store_id)
        STORES_DIR.mkdir(parents=True, exist_ok=True)
        return STORES_DIR / f"{args.store_id}.db"

    return Path(args.output) if args.output else DB_PATH


if __name__ == "__main__":
    build(_parse_args(sys.argv[1:]))
