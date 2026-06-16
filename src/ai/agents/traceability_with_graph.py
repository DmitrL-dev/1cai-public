
"""
Traceability & Compliance с Unified Change Graph
------------------------------------------------

Расширенная реализация BA-05 с использованием Unified Change Graph
для полного traceability: requirements → code → tests → releases → incidents.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from src.ai.code_analysis.graph import CodeGraphBackend, EdgeKind, Node

logger = logging.getLogger(__name__)


class TraceabilityWithGraph:
    """
    Построение traceability matrix с использованием Unified Change Graph.

    Использует граф для автоматического обнаружения связей между:
    - требованиями (BA_REQUIREMENT)
    - кодом (MODULE, FUNCTION)
    - тестами (TEST_CASE, TEST_SUITE)
    - релизами (через метаданные)
    - инцидентами (INCIDENT)
    """

    def __init__(self, backend: Optional[CodeGraphBackend] = None) -> None:
        """
        Args:
            backend: Backend графа (опционально)
        """
        self.backend = backend

    def set_backend(self, backend: CodeGraphBackend) -> None:
        """Установить backend графа."""
        self.backend = backend

    async def build_traceability_matrix(
        self,
        requirement_ids: List[str],
        *,
        include_code: bool = True,
        include_tests: bool = True,
        include_incidents: bool = True,
    ) -> Dict[str, Any]:
        """
        Построить полную матрицу traceability с использованием графа.

        Args:
            requirement_ids: Список ID требований
            include_code: Включать связи с кодом
            include_tests: Включать связи с тестами
            include_incidents: Включать связи с инцидентами

        Returns:
            Матрица traceability с полными связями
        """
        if not self.backend:
            logger.warning("Graph backend not available, returning basic matrix")
            return self._build_basic_matrix(requirement_ids)

        matrix: List[Dict[str, Any]] = []

        for req_id in requirement_ids:
            req_node_id = f"ba_requirement:{req_id}"
            req_node = await self.backend.get_node(req_node_id)

            if not req_node:
                # Если узла нет в графе, создаём базовую запись
                matrix.append(
                    {
                        "requirement_id": req_id,
                        "requirement_title": req_id,
                        "code_nodes": [],
                        "test_nodes": [],
                        "incident_nodes": [],
                        "coverage": "unknown",
                    }
                )
                continue

            traceability: Dict[str, Any] = {
                "requirement_id": req_id,
                "requirement_title": req_node.display_name,
                "code_nodes": [],
                "test_nodes": [],
                "incident_nodes": [],
            }

            # Найти код, реализующий требование (через IMPLEMENTS)
            code_nodes: List[Node] = []
            if include_code:
                code_nodes = await self.backend.neighbors(
                    req_node_id,
                    kinds=[EdgeKind.IMPLEMENTS],
                )
                traceability["code_nodes"] = [
                    {
                        "id": node.id,
                        "kind": node.kind.value,
                        "display_name": node.display_name,
                    }
                    for node in code_nodes
                ]

            # Найти тесты, покрывающие требование (через TESTED_BY)
            if include_tests:
                # Ищем тесты через код (код → тесты)
                all_test_nodes: List[Node] = []
                for code_node in code_nodes:
                    test_nodes = await self.backend.neighbors(
                        code_node.id,
                        kinds=[EdgeKind.TESTED_BY],
                    )
                    all_test_nodes.extend(test_nodes)

                # Удалить дубликаты
                seen_test_ids: Set[str] = set()
                unique_tests: List[Node] = []
                for test_node in all_test_nodes:
                    if test_node.id not in seen_test_ids:
                        seen_test_ids.add(test_node.id)
                        unique_tests.append(test_node)

                traceability["test_nodes"] = [
                    {
                        "id": node.id,
                        "kind": node.kind.value,
                        "display_name": node.display_name,
                    }
                    for node in unique_tests
                ]

            # Найти инциденты, связанные с требованием (через TRIGGERS_INCIDENT)
            if include_incidents:
                # Ищем через код (код → инциденты)
                all_incident_nodes: List[Node] = []
                for code_node in code_nodes if code_nodes else []:
                    incident_nodes = await self.backend.neighbors(
                        code_node.id,
                        kinds=[EdgeKind.TRIGGERS_INCIDENT],
                    )
                    all_incident_nodes.extend(incident_nodes)

                # Удалить дубликаты
                seen_incident_ids: Set[str] = set()
                unique_incidents: List[Node] = []
                for incident_node in all_incident_nodes:
                    if incident_node.id not in seen_incident_ids:
                        seen_incident_ids.add(incident_node.id)
                        unique_incidents.append(incident_node)

                traceability["incident_nodes"] = [
                    {
                        "id": node.id,
                        "kind": node.kind.value,
                        "display_name": node.display_name,
                    }
                    for node in unique_incidents
                ]

            # Вычислить coverage
            has_code = len(traceability["code_nodes"]) > 0
            has_tests = len(traceability["test_nodes"]) > 0
            if has_code and has_tests:
                traceability["coverage"] = "full"
            elif has_code:
                traceability["coverage"] = "partial_code_only"
            elif has_tests:
                traceability["coverage"] = "partial_tests_only"
            else:
                traceability["coverage"] = "none"

            matrix.append(traceability)

        # Общая статистика
        total_reqs = len(requirement_ids)
        full_coverage = sum(1 for m in matrix if m.get("coverage") == "full")
        partial_coverage = sum(
            1 for m in matrix if m.get("coverage", "").startswith("partial")
        )
        no_coverage = sum(1 for m in matrix if m.get("coverage") == "none")

        return {
            "matrix": matrix,
            "summary": {
                "total_requirements": total_reqs,
                "full_coverage": full_coverage,
                "partial_coverage": partial_coverage,
                "no_coverage": no_coverage,
                "coverage_percent": (
                    int((full_coverage / total_reqs) * 100) if total_reqs > 0 else 0
                ),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def build_risk_register(
        self,
        requirement_ids: List[str],
        *,
        include_incidents: bool = True,
    ) -> Dict[str, Any]:
        """
        Построить Risk Register на основе traceability matrix.

        Риски определяются по:
        - Отсутствие тестов для требований
        - Наличие инцидентов, связанных с требованием
        - Отсутствие кода, реализующего требование

        Args:
            requirement_ids: Список ID требований
            include_incidents: Учитывать инциденты при оценке рисков

        Returns:
            Risk Register с оценкой рисков для каждого требования
        """
        matrix_result = await self.build_traceability_matrix(
            requirement_ids,
            include_code=True,
            include_tests=True,
            include_incidents=include_incidents,
        )

        risk_register: List[Dict[str, Any]] = []

        for entry in matrix_result["matrix"]:
            req_id = entry["requirement_id"]
            coverage = entry.get("coverage", "unknown")
            code_nodes = entry.get("code_nodes", [])
            test_nodes = entry.get("test_nodes", [])
            incident_nodes = entry.get("incident_nodes", [])

            # Определить уровень риска
            risk_level = "low"
            risk_reasons: List[str] = []

            if coverage == "none":
                risk_level = "high"
                risk_reasons.append("requirement_not_implemented")
            elif coverage == "partial_code_only":
                risk_level = "high"
                risk_reasons.append("no_tests_for_requirement")
            elif coverage == "partial_tests_only":
                risk_level = "medium"
                risk_reasons.append("tests_without_implementation")
            elif len(incident_nodes) > 0:
                risk_level = "high"
                risk_reasons.append(f"requirement_has_{len(incident_nodes)}_incidents")

            if risk_level != "low":
                risk_register.append(
                    {
                        "requirement_id": req_id,
                        "requirement_title": entry.get("requirement_title", req_id),
                        "risk_level": risk_level,
                        "risk_reasons": risk_reasons,
                        "code_nodes_count": len(code_nodes),
                        "test_nodes_count": len(test_nodes),
                        "incident_nodes_count": len(incident_nodes),
                    }
                )

        # Risk Heatmap
        high_risks = sum(1 for r in risk_register if r["risk_level"] == "high")
        medium_risks = sum(1 for r in risk_register if r["risk_level"] == "medium")
        low_risks = len(requirement_ids) - high_risks - medium_risks

        return {
            "risk_register": risk_register,
            "risk_heatmap": {
                "high": high_risks,
                "medium": medium_risks,
                "low": low_risks,
            },
            "total_requirements": len(requirement_ids),
            "total_risks": len(risk_register),
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def build_full_traceability_report(
        self,
        requirement_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Построить полный отчёт traceability & compliance.

        Включает:
        - Traceability matrix
        - Risk register
        - Risk heatmap
        - Compliance status

        Args:
            requirement_ids: Список ID требований

        Returns:
            Полный отчёт traceability & compliance
        """
        matrix_result = await self.build_traceability_matrix(requirement_ids)
        risk_result = await self.build_risk_register(requirement_ids)

        # Compliance status
        summary = matrix_result["summary"]
        compliance_status = "compliant"
        if summary["no_coverage"] > 0:
            compliance_status = "non_compliant"
        elif summary["partial_coverage"] > 0:
            compliance_status = "partially_compliant"

        return {
            "ba_feature": "BA-05",
            "traceability": matrix_result,
            "risk_register": risk_result["risk_register"],
            "risk_heatmap": risk_result["risk_heatmap"],
            "compliance": {
                "status": compliance_status,
                "requirements_with_full_coverage": summary["full_coverage"],
                "requirements_with_partial_coverage": summary["partial_coverage"],
                "requirements_with_no_coverage": summary["no_coverage"],
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

    def _build_basic_matrix(self, requirement_ids: List[str]) -> Dict[str, Any]:
        """Построить базовую матрицу без графа (fallback)."""
        matrix = [
            {
                "requirement_id": req_id,
                "requirement_title": req_id,
                "code_nodes": [],
                "test_nodes": [],
                "incident_nodes": [],
                "coverage": "unknown",
            }
            for req_id in requirement_ids
        ]

        return {
            "matrix": matrix,
            "summary": {
                "total_requirements": len(requirement_ids),
                "full_coverage": 0,
                "partial_coverage": 0,
                "no_coverage": len(requirement_ids),
                "coverage_percent": 0,
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
