"""
Сервис дашборда бизнес-аналитика.

Бизнес-логика для работы с требованиями и трассируемостью.
"""
from datetime import datetime, timedelta
from typing import Any, Dict

import asyncpg

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class BAService:
    """Бизнес-логика дашборда BA."""

    async def get_dashboard(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает данные для дашборда бизнес-аналитика.

        Args:
            conn: Подключение к БД.

        Returns:
            Dict[str, Any]: Словарь с данными дашборда.
        """
        try:
            # Get tenant
            tenant_id = await conn.fetchval("SELECT id FROM tenants LIMIT 1")

            if not tenant_id:
                return self._get_demo_dashboard()

            # Requirements summary (simplified - use demo if no table)
            try:
                total_reqs = (
                    await conn.fetchval(
                        "SELECT COUNT(*) FROM requirements WHERE tenant_id = $1",
                        tenant_id,
                    )
                    or 0
                )

                if total_reqs == 0:
                    return self._get_demo_dashboard()

                approved_reqs = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM requirements
                    WHERE tenant_id = $1 AND status = 'approved'
                    """,
                        tenant_id,
                    )
                    or 0
                )

                pending_reqs = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM requirements
                    WHERE tenant_id = $1 AND status = 'pending'
                    """,
                        tenant_id,
                    )
                    or 0
                )

                rejected_reqs = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*) FROM requirements
                    WHERE tenant_id = $1 AND status = 'rejected'
                    """,
                        tenant_id,
                    )
                    or 0
                )

                requirements_summary = {
                    "total": total_reqs,
                    "approved": approved_reqs,
                    "pending": pending_reqs,
                    "rejected": rejected_reqs,
                }

                # Recent requirements
                recent_requirements = []
                req_rows = await conn.fetch(
                    """
                    SELECT id, title, status, priority, stakeholder, created_at
                    FROM requirements
                    WHERE tenant_id = $1
                    ORDER BY created_at DESC
                    LIMIT 5
                    """,
                    tenant_id,
                )

                for row in req_rows:
                    recent_requirements.append(
                        {
                            "id": str(row["id"]),
                            "title": row["title"],
                            "status": row["status"],
                            "priority": row["priority"],
                            "stakeholder": row["stakeholder"],
                            "created_at": row["created_at"].isoformat(),
                        }
                    )

                # Use demo for other sections
                demo = self._get_demo_dashboard()

                return {
                    "requirements_summary": requirements_summary,
                    "recent_requirements": recent_requirements if recent_requirements else demo["recent_requirements"],
                    "traceability_matrix": demo["traceability_matrix"],
                    "gap_analysis": demo["gap_analysis"],
                    "process_diagrams": demo["process_diagrams"],
                }

            except Exception:
                return self._get_demo_dashboard()

        except Exception as e:
            logger.error(
                "Error fetching BA dashboard",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return self._get_demo_dashboard()

    def _get_demo_dashboard(self) -> Dict[str, Any]:
        """Возвращает демонстрационные данные для дашборда BA."""
        return {
            "requirements_summary": {
                "total": 45,
                "approved": 32,
                "pending": 10,
                "rejected": 3,
            },
            "recent_requirements": [
                {
                    "id": "req-1",
                    "title": "User authentication with OAuth2",
                    "status": "approved",
                    "priority": "high",
                    "stakeholder": "Product Manager",
                    "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                },
                {
                    "id": "req-2",
                    "title": "Multi-tenant data isolation",
                    "status": "pending",
                    "priority": "critical",
                    "stakeholder": "Security Team",
                    "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                },
            ],
            "traceability_matrix": [
                {
                    "requirement_id": "req-1",
                    "requirement_title": "User authentication",
                    "linked_tasks": 5,
                    "test_coverage": 80,
                    "status": "in_progress",
                },
                {
                    "requirement_id": "req-2",
                    "requirement_title": "Data isolation",
                    "linked_tasks": 3,
                    "test_coverage": 60,
                    "status": "pending",
                },
            ],
            "gap_analysis": [
                {
                    "area": "Security",
                    "current_state": "Basic authentication",
                    "desired_state": "OAuth2 + MFA",
                    "gap_severity": "high",
                    "recommendations": [
                        "Implement OAuth2 provider",
                        "Add MFA support",
                        "Security audit",
                    ],
                },
            ],
            "process_diagrams": [
                {
                    "id": "bpmn-1",
                    "name": "User Onboarding Process",
                    "type": "BPMN",
                    "url": "/api/bpmn/user-onboarding",
                    "last_updated": datetime.now().isoformat(),
                },
            ],
        }
