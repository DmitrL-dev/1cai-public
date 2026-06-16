"""Рентген Go Pipeline — Python consumer for Go bsl-scan callgraph output.

Loads NDJSON from Go bsl-scan (730K+ functions) and ingests into Neo4j
using batch UNWIND queries for 10-50x faster ingestion.

Usage:
    # From NDJSON file (pre-computed):
    pipeline = RentgenGoPipeline()
    stats = pipeline.load_from_ndjson("data/rentgen_callgraph.ndjson")

    # Full pipeline (Go parse + Neo4j ingest):
    stats = pipeline.run("data/configs/unpacked")

    # Parse only (no Neo4j, returns stats):
    stats = pipeline.parse_only("data/configs/unpacked")
"""

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Path to Go bsl-scan binary (relative to project root)
BSL_SCAN_EXE = (
    Path(__file__).resolve().parent.parent.parent.parent / "go" / "bsl-scan.exe"
)


@dataclass
class RentgenFunction:
    """Parsed function/procedure from Go bsl-scan NDJSON output."""

    name: str
    module: str
    line: int
    is_export: bool = False
    is_function: bool = True
    complexity: int = 1
    calls: list[str] = field(default_factory=list)
    queries: list[dict] = field(default_factory=list)


@dataclass
class RentgenStats:
    """Statistics from a Рентген pipeline run."""

    config_path: str = ""
    total_files: int = 0
    total_functions: int = 0
    total_procedures: int = 0
    total_subroutines: int = 0
    total_exports: int = 0
    total_calls: int = 0
    total_queries: int = 0
    unique_modules: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    parse_time_sec: float = 0.0
    ingest_time_sec: float = 0.0
    total_time_sec: float = 0.0
    neo4j_stats: Optional[dict] = None


class RentgenGoPipeline:
    """Full Рентген pipeline: Go bsl-scan → NDJSON → Python → Neo4j.

    Architecture:
        Go bsl-scan (parallel, 16 workers) → NDJSON stdout
        Python consumer (json.loads per line) → BslFunction list
        Neo4j batch ingestion (UNWIND, 5K batches) → graph ready for queries
    """

    def __init__(self, bsl_scan_path: Optional[str] = None):
        self.bsl_scan = Path(bsl_scan_path) if bsl_scan_path else BSL_SCAN_EXE
        self.functions: list[RentgenFunction] = []
        self._stats = RentgenStats()

    def run(
        self,
        config_path: str,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "sentinel2026",
    ) -> RentgenStats:
        """Full pipeline: Go parse → load → Neo4j ingest.

        Args:
            config_path: Path to unpacked 1C configuration directory.
            neo4j_uri: Neo4j bolt URI.
            neo4j_user: Neo4j username.
            neo4j_password: Neo4j password.

        Returns:
            RentgenStats with all metrics.
        """
        t0 = time.perf_counter()

        # Phase 1: Parse with Go
        self.parse(config_path)

        # Phase 2: Ingest into Neo4j
        self.ingest_neo4j(neo4j_uri, neo4j_user, neo4j_password)

        self._stats.total_time_sec = round(time.perf_counter() - t0, 1)
        return self._stats

    def parse(self, config_path: str) -> RentgenStats:
        """Run Go bsl-scan and load results into memory.

        Can be called standalone (without Neo4j) for analysis.
        """
        t0 = time.perf_counter()
        self._stats.config_path = config_path

        if not self.bsl_scan.exists():
            raise FileNotFoundError(
                f"bsl-scan binary not found at {self.bsl_scan}. "
                f"Build it: cd go && go build -o bsl-scan.exe ./cmd/bsl-scan"
            )

        logger.info("Рентген: parsing %s with Go bsl-scan...", config_path)

        proc = subprocess.run(
            [str(self.bsl_scan), "-mode", "callgraph", config_path],
            capture_output=True,
            timeout=600,  # 10 min timeout
        )

        if proc.returncode != 0:
            stderr_text = proc.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"bsl-scan failed (rc={proc.returncode}): {stderr_text}")

        # Log stderr summary (Go outputs summary to stderr)
        stderr_text = proc.stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.info("Go bsl-scan: %s", stderr_text)

        # Parse NDJSON from stdout
        self.functions.clear()
        stdout_bytes = proc.stdout
        for line in stdout_bytes.split(b"\n"):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                self.functions.append(
                    RentgenFunction(
                        name=obj["name"],
                        module=obj["module"],
                        line=obj["line"],
                        is_export=obj.get("is_export", False),
                        is_function=obj.get("is_function", True),
                        complexity=obj.get("complexity", 1),
                        calls=obj.get("calls") or [],
                        queries=obj.get("queries") or [],
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skipping malformed NDJSON line: %s", e)

        self._stats.parse_time_sec = round(time.perf_counter() - t0, 1)
        self._compute_stats()

        logger.info(
            "Рентген parsed: %d subroutines (%d F + %d P), %d calls, "
            "%d queries, %d modules in %.1fs",
            self._stats.total_subroutines,
            self._stats.total_functions,
            self._stats.total_procedures,
            self._stats.total_calls,
            self._stats.total_queries,
            self._stats.unique_modules,
            self._stats.parse_time_sec,
        )
        return self._stats

    def load_from_ndjson(self, ndjson_path: str) -> RentgenStats:
        """Load pre-computed NDJSON file (skip Go parsing step).

        Useful when NDJSON was already generated:
            bsl-scan -mode callgraph <path> > callgraph.ndjson
        """
        t0 = time.perf_counter()
        path = Path(ndjson_path)
        if not path.exists():
            raise FileNotFoundError(f"NDJSON file not found: {path}")

        logger.info("Loading NDJSON from %s...", path)
        self.functions.clear()

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    self.functions.append(
                        RentgenFunction(
                            name=obj["name"],
                            module=obj["module"],
                            line=obj["line"],
                            is_export=obj.get("is_export", False),
                            is_function=obj.get("is_function", True),
                            complexity=obj.get("complexity", 1),
                            calls=obj.get("calls") or [],
                            queries=obj.get("queries") or [],
                        )
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping malformed line: %s", e)

        self._stats.parse_time_sec = round(time.perf_counter() - t0, 1)
        self._compute_stats()

        logger.info(
            "Loaded %d functions from NDJSON in %.1fs",
            len(self.functions),
            self._stats.parse_time_sec,
        )
        return self._stats

    def ingest_neo4j(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "sentinel2026",
    ) -> dict:
        """Ingest parsed functions into Neo4j using batch UNWIND queries.

        Returns dict with ingestion stats.
        """
        from src.db.neo4j_client import Neo4jClient
        from src.modules.graph_api.services.graph_service import GraphService

        if not self.functions:
            raise ValueError(
                "No functions loaded. Call parse() or load_from_ndjson() first."
            )

        t0 = time.perf_counter()
        client = Neo4jClient(uri=uri, user=user, password=password)

        if not client.verify_connectivity():
            raise ConnectionError(f"Cannot connect to Neo4j at {uri}")

        service = GraphService(client)

        # Step 1: Create indexes
        service.ensure_indexes_v2()

        # Step 2: Clear old graph
        logger.info("Clearing old graph...")
        service.clear_graph()

        # Step 3: Bulk upsert modules
        modules_set = {}
        for f in self.functions:
            if f.module not in modules_set:
                parts = f.module.split(".")
                modules_set[f.module] = {
                    "name": f.module,
                    "module_type": parts[1] if len(parts) > 1 else "Module",
                    "metadata_object": parts[0],
                }
        service.bulk_upsert_modules(list(modules_set.values()))

        # Step 4: Bulk upsert functions/procedures
        func_dicts = [
            {
                "name": f.name,
                "module": f.module,
                "line": f.line,
                "is_export": f.is_export,
                "is_function": f.is_function,
                "complexity": f.complexity,
            }
            for f in self.functions
        ]
        service.bulk_upsert_subroutines(func_dicts)

        # Step 5: Build multi-tier call resolution index
        #
        # 1C call resolution is complex because:
        #   - Code calls `МодульА.Функция()` but module is stored as
        #     `МодульА` (1-seg) or `МодульА.ObjectModule` (2-seg)
        #   - Local calls `Функция()` may refer to functions in the same
        #     module, parent module, or a completely different module
        #   - Platform built-ins (Сообщить, Запрос, etc.) have no definition
        #
        # Three-tier resolution:
        #   Tier 1: Exact (name, module) match
        #   Tier 2: Alias (name, short_module) → full module name
        #   Tier 3: Name-only → pick the exported definition (or any unique)

        # Tier 1+2: (name, module) exact and (name, short_module) alias
        func_exact: set[tuple[str, str]] = set()  # (name_lower, module_lower)
        func_alias: dict[tuple[str, str], str] = {}  # (name_lower, short) → module
        # Tier 3: name → best module (prefer exported, then most-connected)
        func_by_name: dict[str, str] = {}  # name_lower → best module
        func_name_exported: dict[str, str] = {}  # name_lower → exported module

        for f in self.functions:
            nl = f.name.lower()
            ml = f.module.lower()
            func_exact.add((nl, ml))

            short = f.module.split(".")[0].lower()
            alias_key = (nl, short)
            # Prefer 1-segment modules (common modules) for alias
            if alias_key not in func_alias or "." not in f.module:
                func_alias[alias_key] = f.module

            # Name-only: prefer exported functions (they're callable cross-module)
            if f.is_export:
                func_name_exported[nl] = f.module
            if nl not in func_by_name:
                func_by_name[nl] = f.module

        logger.info(
            "Resolution index: %d exact, %d alias, %d name-only (%d exported)",
            len(func_exact),
            len(func_alias),
            len(func_by_name),
            len(func_name_exported),
        )

        # Step 6: Bulk add call edges with 3-tier resolution
        call_edges = []
        stats_exact = 0
        stats_alias = 0
        stats_nameonly = 0
        stats_unresolved = 0

        for f in self.functions:
            caller_nl = f.name.lower()
            caller_ml = f.module.lower()

            for call in f.calls:
                if "." in call:
                    parts = call.split(".", 1)
                    callee_name = parts[1]
                    callee_short = parts[0]
                    cnl = callee_name.lower()
                    csl = callee_short.lower()

                    # Tier 1: exact
                    if (cnl, csl) in func_exact:
                        callee_module = callee_short
                        stats_exact += 1
                    # Tier 2: alias (short → full)
                    elif (cnl, csl) in func_alias:
                        callee_module = func_alias[(cnl, csl)]
                        stats_alias += 1
                    # Tier 3: name-only (prefer exported)
                    elif cnl in func_name_exported:
                        callee_module = func_name_exported[cnl]
                        stats_nameonly += 1
                    elif cnl in func_by_name:
                        callee_module = func_by_name[cnl]
                        stats_nameonly += 1
                    else:
                        callee_module = callee_short
                        stats_unresolved += 1

                    call_edges.append(
                        {
                            "caller_name": f.name,
                            "caller_module": f.module,
                            "callee_name": callee_name,
                            "callee_module": callee_module,
                            "line": f.line,
                        }
                    )
                else:
                    # Local call — same module first, then fallback
                    cnl = call.lower()

                    if (cnl, caller_ml) in func_exact:
                        callee_module = f.module
                        stats_exact += 1
                    # Try parent module (strip .ObjectModule etc.)
                    elif "." in f.module:
                        parent = f.module.split(".")[0]
                        if (cnl, parent.lower()) in func_exact:
                            callee_module = parent
                            stats_alias += 1
                        elif cnl in func_name_exported:
                            callee_module = func_name_exported[cnl]
                            stats_nameonly += 1
                        elif cnl in func_by_name:
                            callee_module = func_by_name[cnl]
                            stats_nameonly += 1
                        else:
                            callee_module = f.module
                            stats_unresolved += 1
                    elif cnl in func_name_exported:
                        callee_module = func_name_exported[cnl]
                        stats_nameonly += 1
                    elif cnl in func_by_name:
                        callee_module = func_by_name[cnl]
                        stats_nameonly += 1
                    else:
                        callee_module = f.module
                        stats_unresolved += 1

                    call_edges.append(
                        {
                            "caller_name": f.name,
                            "caller_module": f.module,
                            "callee_name": call,
                            "callee_module": callee_module,
                            "line": f.line,
                        }
                    )

        total_calls = stats_exact + stats_alias + stats_nameonly + stats_unresolved
        resolved_total = stats_exact + stats_alias + stats_nameonly
        logger.info(
            "Call resolution: exact=%d, alias=%d, name-only=%d, unresolved=%d "
            "(%.1f%% resolved of %d)",
            stats_exact,
            stats_alias,
            stats_nameonly,
            stats_unresolved,
            resolved_total * 100 / max(total_calls, 1),
            total_calls,
        )
        if call_edges:
            service.bulk_add_call_edges(call_edges)

        # Step 7: Bulk add queries
        query_dicts = []
        for f in self.functions:
            for q in f.queries:
                q_text = q.get("text", "")
                qid = hashlib.md5(
                    f"{f.module}:{q.get('line', 0)}:{q_text[:100]}".encode()
                ).hexdigest()[:12]
                query_dicts.append(
                    {
                        "qid": qid,
                        "text": q_text,
                        "module": f.module,
                        "function_name": f.name,
                        "line": q.get("line", 0),
                        "tables": q.get("tables", []),
                    }
                )
        if query_dicts:
            service.bulk_add_queries(query_dicts)

        self._stats.ingest_time_sec = round(time.perf_counter() - t0, 1)

        # Get final stats from Neo4j
        try:
            self._stats.neo4j_stats = service.get_stats()
        except Exception:
            pass

        logger.info(
            "Neo4j ingest complete: %d modules, %d subroutines, %d call edges, "
            "%d queries in %.1fs",
            len(modules_set),
            len(self.functions),
            len(call_edges),
            len(query_dicts),
            self._stats.ingest_time_sec,
        )

        client.close()
        return {
            "modules": len(modules_set),
            "subroutines": len(self.functions),
            "call_edges": len(call_edges),
            "queries": len(query_dicts),
            "ingest_time_sec": self._stats.ingest_time_sec,
        }

    def _compute_stats(self):
        """Compute summary statistics from loaded functions."""
        s = self._stats
        s.total_subroutines = len(self.functions)
        s.total_functions = sum(1 for f in self.functions if f.is_function)
        s.total_procedures = sum(1 for f in self.functions if not f.is_function)
        s.total_exports = sum(1 for f in self.functions if f.is_export)
        s.total_calls = sum(len(f.calls) for f in self.functions)
        s.total_queries = sum(len(f.queries) for f in self.functions)
        s.unique_modules = len(set(f.module for f in self.functions))

        complexities = [f.complexity for f in self.functions]
        if complexities:
            s.avg_complexity = round(sum(complexities) / len(complexities), 1)
            s.max_complexity = max(complexities)

    def get_top_complex(self, n: int = 20) -> list[dict]:
        """Get top N most complex functions."""
        sorted_funcs = sorted(self.functions, key=lambda f: f.complexity, reverse=True)
        return [
            {
                "name": f.name,
                "module": f.module,
                "complexity": f.complexity,
                "line": f.line,
            }
            for f in sorted_funcs[:n]
        ]

    def get_top_callers(self, n: int = 20) -> list[dict]:
        """Get top N functions with most outgoing calls."""
        sorted_funcs = sorted(self.functions, key=lambda f: len(f.calls), reverse=True)
        return [
            {"name": f.name, "module": f.module, "calls": len(f.calls), "line": f.line}
            for f in sorted_funcs[:n]
        ]

    def get_dead_code_candidates(self) -> list[dict]:
        """Get exported functions that are never called (dead code candidates)."""
        # Build set of all call targets
        called = set()
        for f in self.functions:
            for call in f.calls:
                called.add(call)

        dead = []
        for f in self.functions:
            if f.is_export:
                # Check if this function is called anywhere
                full_name = f"{f.module}.{f.name}" if "." not in f.module else f.name
                if f.name not in called and full_name not in called:
                    dead.append(
                        {
                            "name": f.name,
                            "module": f.module,
                            "line": f.line,
                            "complexity": f.complexity,
                        }
                    )
        return dead

    def to_summary_json(self) -> str:
        """Export stats as JSON string."""
        import dataclasses

        return json.dumps(dataclasses.asdict(self._stats), ensure_ascii=False, indent=2)
