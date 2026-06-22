"""Graph Service — Cypher operations for 1C code graph (Рентген).

Node types: BSL_MODULE, BSL_FUNCTION, BSL_PROCEDURE, BSL_QUERY,
            BSL_DOCUMENT, BSL_CATALOG, BSL_REGISTER, BSL_SUBSCRIPTION,
            BSL_COMMON_MODULE, BSL_SCHEDULED_JOB

Edge types: CALLS, EXECUTES_QUERY, READS_TABLE, WRITES_TABLE,
            HAS_MODULE, HAS_HANDLER, SUBSCRIBES_TO, TRIGGERS
"""

import logging
from typing import Any, Optional

from src.db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class GraphService:
    """Service for building and querying 1C configuration call graphs."""

    def __init__(self, client: Neo4jClient):
        self.client = client

    def ensure_indexes(self):
        """Create indexes for fast lookups."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_MODULE) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_FUNCTION) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_PROCEDURE) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_DOCUMENT) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_COMMON_MODULE) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_SUBSCRIPTION) ON (n.name)",
        ]
        for idx in indexes:
            self.client.run_write(idx)
        logger.info("Graph indexes ensured")

    def clear_graph(self):
        """Delete all nodes and edges in batches to avoid OOM."""
        total = 0
        while True:
            result = self.client.run(
                "MATCH (n) WITH n LIMIT 50000 DETACH DELETE n RETURN count(*) AS deleted"
            )
            deleted = result[0]["deleted"] if result else 0
            if deleted == 0:
                break
            total += deleted
            logger.info("Clear graph progress: %d nodes deleted so far", total)
        logger.warning("Graph cleared: %d nodes total", total)

    # === BATCH INGEST (Go Рентген pipeline) ===

    def bulk_upsert_modules(self, modules: list[dict], batch_size: int = 5000) -> int:
        """Batch upsert module nodes using UNWIND. Returns count."""
        total = 0
        for i in range(0, len(modules), batch_size):
            batch = modules[i : i + batch_size]
            self.client.run_write(
                """
                UNWIND $batch AS m
                MERGE (n:BSL_MODULE {name: m.name})
                SET n.module_type = m.module_type,
                    n.metadata_object = m.metadata_object
                """,
                {"batch": batch},
            )
            total += len(batch)
        logger.info("Bulk upserted %d modules", total)
        return total

    def bulk_upsert_subroutines(
        self, functions: list[dict], batch_size: int = 5000
    ) -> int:
        """Batch upsert function/procedure nodes using UNWIND. Returns count."""
        total = 0
        for i in range(0, len(functions), batch_size):
            batch = functions[i : i + batch_size]

            # Split into functions and procedures
            funcs = [f for f in batch if f.get("is_function", True)]
            procs = [f for f in batch if not f.get("is_function", True)]

            if funcs:
                self.client.run_write(
                    """
                    UNWIND $batch AS f
                    MERGE (n:BSL_FUNCTION {name: f.name, module: f.module})
                    SET n.line = f.line, n.is_export = f.is_export,
                        n.complexity = f.complexity
                    WITH n, f
                    MATCH (m:BSL_MODULE {name: f.module})
                    MERGE (m)-[:HAS_FUNCTION]->(n)
                    """,
                    {"batch": funcs},
                )

            if procs:
                self.client.run_write(
                    """
                    UNWIND $batch AS p
                    MERGE (n:BSL_PROCEDURE {name: p.name, module: p.module})
                    SET n.line = p.line, n.is_export = p.is_export,
                        n.complexity = p.complexity
                    WITH n, p
                    MATCH (m:BSL_MODULE {name: p.module})
                    MERGE (m)-[:HAS_PROCEDURE]->(n)
                    """,
                    {"batch": procs},
                )

            total += len(batch)
            if total % 50000 == 0:
                logger.info(
                    "Bulk upsert progress: %d/%d subroutines", total, len(functions)
                )
        logger.info(
            "Bulk upserted %d subroutines (%d F + %d P)",
            total,
            sum(1 for f in functions if f.get("is_function", True)),
            sum(1 for f in functions if not f.get("is_function", True)),
        )
        return total

    def bulk_add_call_edges(self, edges: list[dict], batch_size: int = 5000) -> int:
        """Batch add CALLS edges using UNWIND with label-specific queries.

        Runs 4 MATCH combinations (F→F, F→P, P→F, P→P) per batch to leverage
        composite indexes on (name, module) for each label.
        """
        total = 0
        created = 0
        combos = [
            ("BSL_FUNCTION", "BSL_FUNCTION"),
            ("BSL_FUNCTION", "BSL_PROCEDURE"),
            ("BSL_PROCEDURE", "BSL_FUNCTION"),
            ("BSL_PROCEDURE", "BSL_PROCEDURE"),
        ]
        for i in range(0, len(edges), batch_size):
            batch = edges[i : i + batch_size]
            for caller_label, callee_label in combos:
                result = self.client.run_write(
                    f"""
                    UNWIND $batch AS e
                    MATCH (a:{caller_label} {{name: e.caller_name, module: e.caller_module}})
                    MATCH (b:{callee_label} {{name: e.callee_name, module: e.callee_module}})
                    MERGE (a)-[r:CALLS]->(b)
                    SET r.line = e.line
                    """,
                    {"batch": batch},
                )
            total += len(batch)
            if total % 100000 == 0:
                logger.info("Bulk call edges progress: %d/%d", total, len(edges))
        logger.info("Bulk added call edges: %d submitted", total)
        return total

    def bulk_add_queries(self, queries: list[dict], batch_size: int = 2000) -> int:
        """Batch add query nodes using UNWIND. Returns count."""
        total = 0
        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]
            self.client.run_write(
                """
                UNWIND $batch AS q
                MERGE (n:BSL_QUERY {qid: q.qid})
                SET n.text = q.text, n.module = q.module, n.line = q.line,
                    n.tables = q.tables
                WITH n, q
                MATCH (f {name: q.function_name, module: q.module})
                WHERE f:BSL_FUNCTION OR f:BSL_PROCEDURE
                MERGE (f)-[:EXECUTES_QUERY]->(n)
                """,
                {"batch": batch},
            )
            total += len(batch)
        logger.info("Bulk added %d queries", total)
        return total

    def ensure_indexes_v2(self):
        """Create composite indexes for fast lookups (v2 — optimized)."""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_MODULE) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_FUNCTION) ON (n.name, n.module)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_PROCEDURE) ON (n.name, n.module)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_DOCUMENT) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_COMMON_MODULE) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_SUBSCRIPTION) ON (n.name)",
            "CREATE INDEX IF NOT EXISTS FOR (n:BSL_QUERY) ON (n.qid)",
        ]
        for idx in indexes:
            try:
                self.client.run_write(idx)
            except Exception as e:
                logger.warning("Index creation skipped: %s", e)
        logger.info("Graph indexes v2 ensured (composite)")

    # === SINGLE INGEST (legacy, kept for backward compatibility) ===

    def upsert_module(
        self,
        name: str,
        module_type: str,
        metadata_object: str,
        file_path: str,
        loc: int = 0,
    ) -> None:
        """Create or update a BSL module node."""
        self.client.run_write(
            """
            MERGE (m:BSL_MODULE {name: $name})
            SET m.module_type = $module_type,
                m.metadata_object = $metadata_object,
                m.file_path = $file_path,
                m.loc = $loc
            """,
            {
                "name": name,
                "module_type": module_type,
                "metadata_object": metadata_object,
                "file_path": file_path,
                "loc": loc,
            },
        )

    def upsert_function(
        self,
        name: str,
        module: str,
        line: int,
        is_export: bool = False,
        complexity: int = 0,
    ) -> None:
        """Create function node and link to module."""
        self.client.run_write(
            """
            MERGE (f:BSL_FUNCTION {name: $name, module: $module})
            SET f.line = $line, f.is_export = $is_export, f.complexity = $complexity
            WITH f
            MATCH (m:BSL_MODULE {name: $module})
            MERGE (m)-[:HAS_FUNCTION]->(f)
            """,
            {
                "name": name,
                "module": module,
                "line": line,
                "is_export": is_export,
                "complexity": complexity,
            },
        )

    def upsert_procedure(
        self,
        name: str,
        module: str,
        line: int,
        is_export: bool = False,
        complexity: int = 0,
    ) -> None:
        """Create procedure node and link to module."""
        self.client.run_write(
            """
            MERGE (p:BSL_PROCEDURE {name: $name, module: $module})
            SET p.line = $line, p.is_export = $is_export, p.complexity = $complexity
            WITH p
            MATCH (m:BSL_MODULE {name: $module})
            MERGE (m)-[:HAS_PROCEDURE]->(p)
            """,
            {
                "name": name,
                "module": module,
                "line": line,
                "is_export": is_export,
                "complexity": complexity,
            },
        )

    def add_call_edge(
        self,
        caller_name: str,
        caller_module: str,
        callee_name: str,
        callee_module: str,
        line: int,
    ) -> None:
        """Add a CALLS edge between two functions/procedures."""
        self.client.run_write(
            """
            MATCH (a {name: $caller_name, module: $caller_module})
            WHERE a:BSL_FUNCTION OR a:BSL_PROCEDURE
            MATCH (b {name: $callee_name, module: $callee_module})
            WHERE b:BSL_FUNCTION OR b:BSL_PROCEDURE
            MERGE (a)-[r:CALLS]->(b)
            SET r.line = $line
            """,
            {
                "caller_name": caller_name,
                "caller_module": caller_module,
                "callee_name": callee_name,
                "callee_module": callee_module,
                "line": line,
            },
        )

    def add_subscription(
        self,
        name: str,
        source_type: str,
        event: str,
        handler_module: str,
        handler_method: str,
    ) -> None:
        """Add an event subscription with its handler link."""
        self.client.run_write(
            """
            MERGE (s:BSL_SUBSCRIPTION {name: $name})
            SET s.source_type = $source_type, s.event = $event,
                s.handler_module = $handler_module, s.handler_method = $handler_method
            WITH s
            MATCH (h {name: $handler_method, module: $handler_module})
            WHERE h:BSL_FUNCTION OR h:BSL_PROCEDURE
            MERGE (s)-[:HAS_HANDLER]->(h)
            """,
            {
                "name": name,
                "source_type": source_type,
                "event": event,
                "handler_module": handler_module,
                "handler_method": handler_method,
            },
        )

    def add_query(
        self,
        query_text: str,
        module: str,
        function_name: str,
        line: int,
        tables: list[str] | None = None,
    ) -> None:
        """Add a query node linked to the function that executes it."""
        import hashlib

        qid = hashlib.md5(f"{module}:{line}:{query_text[:100]}".encode()).hexdigest()[
            :12
        ]
        self.client.run_write(
            """
            MERGE (q:BSL_QUERY {qid: $qid})
            SET q.text = $query_text, q.module = $module, q.line = $line,
                q.tables = $tables
            WITH q
            MATCH (f {name: $function_name, module: $module})
            WHERE f:BSL_FUNCTION OR f:BSL_PROCEDURE
            MERGE (f)-[:EXECUTES_QUERY]->(q)
            """,
            {
                "qid": qid,
                "query_text": query_text,
                "module": module,
                "function_name": function_name,
                "line": line,
                "tables": tables or [],
            },
        )

    # === QUERY (Рентген) ===

    def get_execution_flow(self, entry_point: str, max_depth: int = 10) -> list[dict]:
        """Get full execution flow from an entry point (e.g. document posting handler).

        Returns ordered list of {caller, callee, depth, line, module} dicts
        representing the call chain.
        """
        depth = int(max_depth)  # sanitize
        return self.client.run(
            f"""
            MATCH path = (start {{name: $entry}})-[:CALLS*1..{depth}]->(end)
            WHERE start:BSL_FUNCTION OR start:BSL_PROCEDURE
            UNWIND relationships(path) AS rel
            WITH startNode(rel) AS caller, endNode(rel) AS callee, rel,
                 length(path) AS depth
            RETURN caller.name AS caller, caller.module AS caller_module,
                   callee.name AS callee, callee.module AS callee_module,
                   rel.line AS line, depth
            ORDER BY depth, caller.module, rel.line
            """,
            {"entry": entry_point},
        )

    def get_impact_analysis(self, target: str, max_depth: int = 5) -> list[dict]:
        """Reverse traversal: what calls this function? (RegressionGuard)"""
        depth = int(max_depth)  # sanitize
        return self.client.run(
            f"""
            MATCH path = (caller)-[:CALLS*1..{depth}]->(target {{name: $target}})
            WHERE target:BSL_FUNCTION OR target:BSL_PROCEDURE
            UNWIND relationships(path) AS rel
            WITH startNode(rel) AS c, endNode(rel) AS t, length(path) AS depth
            RETURN c.name AS caller, c.module AS caller_module,
                   t.name AS callee, t.module AS callee_module, depth
            ORDER BY depth
            """,
            {"target": target},
        )

    def get_subscriptions_for(self, metadata_type: str) -> list[dict]:
        """Get all event subscriptions that fire for a metadata type."""
        return self.client.run(
            """
            MATCH (s:BSL_SUBSCRIPTION)
            WHERE s.source_type CONTAINS $meta_type
            OPTIONAL MATCH (s)-[:HAS_HANDLER]->(h)
            RETURN s.name AS subscription, s.event AS event,
                   s.handler_module AS handler_module,
                   s.handler_method AS handler_method,
                   h.line AS handler_line
            ORDER BY s.event
            """,
            {"meta_type": metadata_type},
        )

    def get_queries_in_flow(self, entry_point: str, max_depth: int = 3) -> list[dict]:
        """Get all queries executed in a call chain (Перформер)."""
        depth = min(int(max_depth), 5)  # sanitize + cap
        return self.client.run(
            f"""
            MATCH path = (start {{name: $entry}})-[:CALLS*0..{depth}]->(func)
            WHERE start:BSL_FUNCTION OR start:BSL_PROCEDURE
            MATCH (func)-[:EXECUTES_QUERY]->(q:BSL_QUERY)
            RETURN func.name AS function_name, func.module AS module,
                   q.text AS query_text, q.line AS query_line,
                   q.tables AS tables, length(path) AS call_depth
            ORDER BY call_depth, q.line
            LIMIT 200
            """,
            {"entry": entry_point},
        )

    def compute_fan_metrics(self, batch_size: int = 5000) -> dict:
        """Compute fan-in and fan-out for all BSL_MODULE nodes and write back.

        Fan-in: how many other modules call into this module
        Fan-out: how many other modules this module calls out to

        Returns stats dict.
        """
        # Compute fan-out: for each module, count distinct target modules
        logger.info("Computing fan-out metrics...")
        self.client.run_write(
            """
            MATCH (src_mod:BSL_MODULE)-[:HAS_FUNCTION|HAS_PROCEDURE]->(src_fn)
            MATCH (src_fn)-[:CALLS]->(tgt_fn)
            MATCH (tgt_mod:BSL_MODULE)-[:HAS_FUNCTION|HAS_PROCEDURE]->(tgt_fn)
            WHERE src_mod <> tgt_mod
            WITH src_mod, count(DISTINCT tgt_mod) AS fan_out
            SET src_mod.fan_out = fan_out
        """
        )

        # Compute fan-in: for each module, count distinct source modules
        logger.info("Computing fan-in metrics...")
        self.client.run_write(
            """
            MATCH (tgt_mod:BSL_MODULE)-[:HAS_FUNCTION|HAS_PROCEDURE]->(tgt_fn)
            MATCH (src_fn)-[:CALLS]->(tgt_fn)
            MATCH (src_mod:BSL_MODULE)-[:HAS_FUNCTION|HAS_PROCEDURE]->(src_fn)
            WHERE src_mod <> tgt_mod
            WITH tgt_mod, count(DISTINCT src_mod) AS fan_in
            SET tgt_mod.fan_in = fan_in
        """
        )

        # Get stats
        result = self.client.run(
            """
            MATCH (n:BSL_MODULE)
            WHERE n.fan_in IS NOT NULL OR n.fan_out IS NOT NULL
            RETURN count(n) AS modules_with_fans,
                   round(avg(coalesce(n.fan_in, 0)), 1) AS avg_fan_in,
                   round(avg(coalesce(n.fan_out, 0)), 1) AS avg_fan_out,
                   max(n.fan_in) AS max_fan_in,
                   max(n.fan_out) AS max_fan_out
        """
        )
        stats = result[0] if result else {}
        logger.info("Fan metrics computed: %s", stats)
        return stats

    def get_stats(self) -> dict:
        """Get graph statistics."""
        result = self.client.run(
            """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(n) AS count
            ORDER BY count DESC
            """
        )
        stats = {r["label"]: r["count"] for r in result}
        edges = self.client.run(
            "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count"
        )
        stats["_edges"] = {r["type"]: r["count"] for r in edges}
        return stats
