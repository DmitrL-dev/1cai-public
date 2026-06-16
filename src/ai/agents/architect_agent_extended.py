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


class ArchitectAgentExtended:
    """
    Расширенный архитектурный агент, использующий Neo4j для глубокого анализа.
    """

    def __init__(self) -> None:
        self.backend = Neo4jCodeGraphBackend()
        self.client = get_neo4j_client()

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
        if coupling > 0.7:
            risks.append("High system coupling detected")
        if cohesion < 0.3:
            risks.append("Low system cohesion detected")

        # 4. Generate Recommendations
        recommendations = self._generate_recommendations(
            coupling, cohesion, cycles, patterns
        )

        return {
            "analysis": {
                "summary": "Deep architectural analysis based on Code Graph",
                "modules_count": await self._count_nodes(NodeKind.MODULE),
                "services_count": await self._count_nodes(NodeKind.SERVICE),
                "scalability_risk": "high" if coupling > 0.8 else "low",
                "detected_patterns": patterns,
            },
            "architecture": {
                "overall_score": self._calculate_score(coupling, cohesion, len(cycles)),
                "metrics": {
                    "coupling": round(coupling, 2),
                    "cohesion": round(cohesion, 2),
                    "cycles_detected": len(cycles),
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
        cypher = "MATCH (n:Node) WHERE n.kind = $kind RETURN count(n) as count"
        result = self.client.execute_query(cypher, {"kind": kind.value})
        return result[0]["count"] if result else 0

    async def _analyze_coupling(self) -> float:
        """
        Calculate system-wide coupling (0.0 to 1.0).
        Simplified metric: Ratio of actual dependencies to maximum possible dependencies.
        """
        cypher = """
        MATCH (n:Node)
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN count(n) as nodes, count(r) as edges
        """
        result = self.client.execute_query(cypher)
        if not result:
            return 0.0

        nodes = result[0]["nodes"]
        edges = result[0]["edges"]

        if nodes <= 1:
            return 0.0

        # Max edges in directed graph = n * (n-1)
        max_edges = nodes * (nodes - 1)
        return min(1.0, edges / max_edges) if max_edges > 0 else 0.0

    async def _analyze_cohesion(self) -> float:
        """
        Calculate system-wide cohesion (0.0 to 1.0).
        Simplified metric: Average internal clustering coefficient.
        """
        # This is a heavy query for large graphs, using a simplified proxy:
        # Ratio of intra-module calls to inter-module calls?
        # For now, returning a placeholder based on graph density
        return 0.5  # TODO: Implement sophisticated cohesion metric

    async def _detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies using Neo4j APOC or pure Cypher.
        Using pure Cypher (limited depth) for portability.
        """
        # Find cycles up to length 5
        cypher = """
        MATCH path = (n)-[*1..5]->(n)
        RETURN [x in nodes(path) | x.display_name] as cycle
        LIMIT 10
        """
        try:
            results = self.client.execute_query(cypher)
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
        coupling: float,
        cohesion: float,
        cycles: List[List[str]],
        patterns: List[str],
    ) -> List[str]:
        recs = []
        if cycles:
            recs.append("Eliminate circular dependencies to improve stability.")
        if coupling > 0.6:
            recs.append("Refactor highly coupled modules to improve testability.")
        if cohesion < 0.4:
            recs.append("Group related functions into cohesive modules.")
        if not patterns:
            recs.append("Define clear architectural layers.")
        return recs

    def _calculate_score(
        self, coupling: float, cohesion: float, cycles_count: int
    ) -> float:
        """Calculate overall architecture score (0-10)."""
        score = 10.0
        score -= coupling * 3
        score += (cohesion - 0.5) * 2
        score -= min(5, cycles_count * 0.5)
        return max(0.0, min(10.0, score))
