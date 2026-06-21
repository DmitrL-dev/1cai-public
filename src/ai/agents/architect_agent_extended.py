"""
Architect Agent Extended
------------------------

Advanced architectural analysis agent leveraging the persistent Code Graph (Neo4j).
Performs deep structural analysis, detects cycles, and evaluates architectural quality.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from src.ai.code_analysis.graph import EdgeKind, NodeKind
from src.ai.code_analysis.neo4j_backend import Neo4jCodeGraphBackend

try:
    from src.db.neo4j_client import get_neo4j_client
except ImportError:
    get_neo4j_client = None  # type: ignore

logger = logging.getLogger(__name__)

ARCHITECT_GRAPH_CONTRACT = "architect_graph_evidence_contract"


class ArchitectAgentExtended:
    """
    Расширенный архитектурный агент, использующий Neo4j для глубокого анализа.
    """

    def __init__(self) -> None:
        self.backend = Neo4jCodeGraphBackend()
        try:
            self.client = get_neo4j_client() if callable(get_neo4j_client) else None
        except Exception as exc:
            logger.warning("Neo4j client unavailable for architect agent: %s", exc)
            self.client = None

    async def analyze_system(self, description: str) -> Dict[str, Any]:
        """
        Выполняет полный архитектурный анализ системы.

        Args:
            description: Текстовое описание (используется для контекста,
                         но основной анализ идет по графу).
        """
        logger.info("Starting extended architectural analysis")

        # 1. Structural Metrics
        coupling = await self._analyze_coupling()
        cohesion = await self._analyze_cohesion()
        cycles = await self._detect_cycles()

        # 2. Pattern Recognition
        patterns = await self._identify_patterns()

        # 3. Risk Assessment
        risks = []
        if cycles:
            risks.append(f"Found {len(cycles)} circular dependencies")
        if coupling is not None and coupling > 0.7:
            risks.append("High system coupling detected")
        if cohesion is not None and cohesion < 0.3:
            risks.append("Low system cohesion detected")

        # 4. Generate Recommendations
        recommendations = self._generate_recommendations(
            coupling, cohesion, cycles, patterns
        )

        return {
            "analysis": {
                "summary": "Deep architectural analysis based on Code Graph",
                "mode": ARCHITECT_GRAPH_CONTRACT,
                "coverage": self._coverage(coupling, cohesion, cycles),
                "modules_count": await self._count_nodes(NodeKind.MODULE),
                "services_count": await self._count_nodes(NodeKind.SERVICE),
                "scalability_risk": self._scalability_risk(coupling),
                "detected_patterns": patterns,
                "required_evidence": self._required_evidence(coupling, cohesion),
                "caveats": [
                    "Metrics are calculated only from the connected code graph.",
                    "No default cohesion/coupling values are substituted when graph evidence is absent.",
                ],
            },
            "architecture": {
                "overall_score": self._calculate_score(coupling, cohesion, len(cycles)),
                "metrics": {
                    "coupling": round(coupling, 2) if coupling is not None else None,
                    "cohesion": round(cohesion, 2) if cohesion is not None else None,
                    "cycles_detected": len(cycles),
                    "measured": {
                        "coupling": coupling is not None,
                        "cohesion": cohesion is not None,
                        "cycles": bool(self.client),
                    },
                },
                "risks": risks,
                "recommendations": recommendations,
            },
            "details": {
                "cycles": cycles[:10]  # Return top 10 cycles
            },
        }

    async def _count_nodes(self, kind: NodeKind) -> int:
        """Count nodes of a specific kind."""
        if not self.client:
            return 0
        cypher = "MATCH (n:Node) WHERE n.kind = $kind RETURN count(n) as count"
        result = self._execute_query(cypher, {"kind": kind.value})
        return result[0]["count"] if result else 0

    async def _analyze_coupling(self, config_name: Optional[str] = None) -> Optional[float]:
        """
        Calculate system-wide coupling (0.0 to 1.0).
        Simplified metric: Ratio of actual dependencies to maximum possible dependencies.
        """
        cypher = """
        MATCH (n:Node)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN count(n) as nodes, count(r) as edges
        """
        if not self.client:
            return None

        result = self._execute_query(cypher)
        if not result:
            return None

        nodes = result[0]["nodes"]
        edges = result[0]["edges"]

        if nodes == 0:
            return None
        if nodes <= 1:
            return 0.0

        # Max edges in directed graph = n * (n-1)
        max_edges = nodes * (nodes - 1)
        return min(1.0, edges / max_edges) if max_edges > 0 else 0.0

    async def _analyze_cohesion(self, config_name: Optional[str] = None) -> Optional[float]:
        """
        Calculate system-wide cohesion (0.0 to 1.0).
        Proxy metric: share of edges that stay inside the same declared module,
        namespace, package or kind. Returns None when graph evidence is absent.
        """
        if not self.client:
            return None

        cypher = """
        MATCH (n:Node)-[r]->(m:Node)
        WITH
          coalesce(n.module, n.namespace, n.package, n.kind) as source_group,
          coalesce(m.module, m.namespace, m.package, m.kind) as target_group,
          r
        RETURN
          count(r) as total_edges,
          sum(CASE WHEN source_group = target_group THEN 1 ELSE 0 END) as internal_edges
        """
        result = self._execute_query(cypher)
        if not result:
            return None

        total_edges = result[0].get("total_edges") or 0
        internal_edges = result[0].get("internal_edges") or 0
        if total_edges <= 0:
            return None
        return max(0.0, min(1.0, internal_edges / total_edges))

    async def _detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies using Neo4j APOC or pure Cypher.
        Using pure Cypher (limited depth) for portability.
        """
        # Find cycles up to length 5
        if not self.client:
            return []

        cypher = """
        MATCH path = (n)-[*1..5]->(n)
        RETURN [x in nodes(path) | x.display_name] as cycle
        LIMIT 10
        """
        try:
            results = self._execute_query(cypher)
            return [r["cycle"] for r in results]
        except Exception as e:
            logger.warning(f"Cycle detection failed: {e}")
            return []

    async def _identify_patterns(self) -> List[str]:
        """Identify architectural patterns."""
        patterns = []

        # Check for Layered Architecture
        # (Simplified: if we have distinct clusters of UI, Logic, Data)
        # For now, just checking node kinds presence
        has_api = await self._count_nodes(NodeKind.API_ENDPOINT) > 0
        has_db = await self._count_nodes(NodeKind.DB_TABLE) > 0

        if has_api and has_db:
            patterns.append("Layered (implied)")

        return patterns

    def _generate_recommendations(
        self,
        coupling: Optional[float],
        cohesion: Optional[float],
        cycles: List[List[str]],
        patterns: List[str],
    ) -> List[str]:
        recs = []
        if cycles:
            recs.append("Eliminate circular dependencies to improve stability.")
        if coupling is not None and coupling > 0.6:
            recs.append("Refactor highly coupled modules to improve testability.")
        if cohesion is not None and cohesion < 0.4:
            recs.append("Group related functions into cohesive modules.")
        if coupling is None or cohesion is None:
            recs.append("Connect and populate the code graph before scoring architecture quality.")
        if not patterns:
            recs.append("Define clear architectural layers.")
        return recs

    def _calculate_score(
        self, coupling: Optional[float], cohesion: Optional[float], cycles_count: int
    ) -> Optional[float]:
        """Calculate overall architecture score (0-10)."""
        if coupling is None or cohesion is None:
            return None
        score = 10.0
        score -= coupling * 3
        score += (cohesion - 0.5) * 2
        score -= min(5, cycles_count * 0.5)
        return max(0.0, min(10.0, score))

    def _execute_query(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.client:
            return []
        try:
            if params is None:
                return self.client.execute_query(cypher)
            return self.client.execute_query(cypher, params)
        except Exception as exc:
            logger.warning("Architect graph query failed: %s", exc)
            return []

    def _coverage(
        self,
        coupling: Optional[float],
        cohesion: Optional[float],
        cycles: List[List[str]],
    ) -> str:
        if not self.client:
            return "no_code_graph_connection"
        parts = []
        if coupling is not None:
            parts.append("coupling")
        if cohesion is not None:
            parts.append("cohesion")
        if cycles:
            parts.append("cycles")
        return "+".join(parts) if parts else "code_graph_without_edges"

    def _required_evidence(
        self, coupling: Optional[float], cohesion: Optional[float]
    ) -> List[str]:
        required = []
        if not self.client:
            return ["Neo4j code graph connection", "parsed nodes and dependency edges"]
        if coupling is None:
            required.append("code graph nodes and dependency edges")
        if cohesion is None:
            required.append("module/namespace/package metadata on graph nodes")
        return required

    def _scalability_risk(self, coupling: Optional[float]) -> str:
        if coupling is None:
            return "unknown"
        return "high" if coupling > 0.8 else "low"
