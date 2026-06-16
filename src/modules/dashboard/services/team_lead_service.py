"""
Сервис дашборда тимлида.

Бизнес-логика для метрик производительности команды и качества кода.
"""
from typing import Any, Dict

import asyncpg

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class TeamLeadService:
    """Бизнес-логика дашборда тимлида."""

    async def get_dashboard(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает данные для дашборда тимлида.

        Args:
            conn: Подключение к БД.

        Returns:
            Dict[str, Any]: Словарь с данными дашборда.
        """
        try:
            # Get tenant (for now, first one)
            tenant_id = await conn.fetchval("SELECT id FROM tenants LIMIT 1")

            if not tenant_id:
                return self._get_demo_dashboard()

            # Calculate team velocity
            tasks_completed_this_week = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND status = 'completed'
                  AND completed_at > NOW() - INTERVAL '7 days'
                """,
                    tenant_id,
                )
                or 0
            )

            total_tasks_this_week = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND created_at > NOW() - INTERVAL '7 days'
                """,
                    tenant_id,
                )
                or 1
            )

            velocity = (
                int((tasks_completed_this_week / total_tasks_this_week)
                    * 100) if total_tasks_this_week > 0 else 0
            )

            # Calculate code quality
            approved_reviews = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM code_reviews
                WHERE tenant_id = $1
                  AND status = 'approved'
                  AND created_at > NOW() - INTERVAL '30 days'
                """,
                    tenant_id,
                )
                or 0
            )

            total_reviews = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM code_reviews
                WHERE tenant_id = $1
                  AND created_at > NOW() - INTERVAL '30 days'
                """,
                    tenant_id,
                )
                or 1
            )

            code_quality = int((approved_reviews / total_reviews)
                               * 100) if total_reviews > 0 else 85

            # Calculate bug rate
            bug_tasks = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND (title ILIKE '%bug%' OR description ILIKE '%bug%' OR title ILIKE '%fix%')
                  AND created_at > NOW() - INTERVAL '30 days'
                """,
                    tenant_id,
                )
                or 0
            )

            total_tasks_month = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND created_at > NOW() - INTERVAL '30 days'
                """,
                    tenant_id,
                )
                or 1
            )

            bug_rate = round((bug_tasks / total_tasks_month) * 100,
                             1) if total_tasks_month > 0 else 0

            # Deployment frequency
            deployments = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM activities
                WHERE tenant_id = $1
                  AND type = 'deployment'
                  AND created_at > NOW() - INTERVAL '30 days'
                """,
                    tenant_id,
                )
                or 0
            )

            team_metrics = {
                "velocity": velocity,
                "code_quality": code_quality,
                "bug_rate": bug_rate,
                "deployment_frequency": deployments,
            }

            # Team performance (simplified - use demo if no data)
            team_performance = []
            team_rows = await conn.fetch(
                """
                SELECT name, role, workload, tasks_count
                FROM team_members
                WHERE tenant_id = $1
                ORDER BY workload DESC
                LIMIT 10
                """,
                tenant_id,
            )

            if not team_rows:
                return self._get_demo_dashboard()

            for row in team_rows:
                member_completed = (
                    await conn.fetchval(
                        """
                    SELECT COUNT(*)
                    FROM tasks t
                    JOIN team_members tm ON t.assignee_id = tm.user_id
                    WHERE tm.tenant_id = $1
                      AND tm.name = $2
                      AND t.status = 'completed'
                      AND t.completed_at > NOW() - INTERVAL '7 days'
                    """,
                        tenant_id,
                        row["name"],
                    )
                    or 0
                )

                team_performance.append(
                    {
                        "name": row["name"],
                        "role": row["role"],
                        "workload": row["workload"],
                        "tasks_active": row["tasks_count"],
                        "tasks_completed_week": member_completed,
                        "status": (
                            "overloaded" if row["workload"] > 90 else "normal" if row["workload"] > 60 else "available"
                        ),
                    }
                )

            # Code quality trends (last 6 weeks)
            code_quality_trends = []
            for week_offset in range(6, 0, -1):
                week_start = f"NOW() - INTERVAL '{week_offset} weeks'"
                week_end = f"NOW() - INTERVAL '{week_offset - 1} weeks'"

                week_quality = (
                    await conn.fetchval(
                        f"""
                    SELECT COALESCE(
                        ROUND(
                            (SELECT COUNT(*) FROM code_reviews
                             WHERE tenant_id = $1 AND status = 'approved'
                               AND created_at BETWEEN {week_start} AND {week_end})::numeric /
                            NULLIF((SELECT COUNT(*) FROM code_reviews
                                    WHERE tenant_id = $1
                                      AND created_at BETWEEN {week_start} AND {week_end}), 0) * 100
                        ), 0
                    )
                    """,
                        tenant_id,
                    )
                    or 85
                )

                code_quality_trends.append(
                    {"week": f"Week -{week_offset}", "quality": int(week_quality)})

            # Velocity chart (last 6 weeks)
            velocity_chart = []
            for week_offset in range(6, 0, -1):
                week_completed = (
                    await conn.fetchval(
                        f"""
                    SELECT COUNT(*)
                    FROM tasks
                    WHERE tenant_id = $1
                      AND status = 'completed'
                      AND completed_at BETWEEN NOW() - INTERVAL '{week_offset} weeks'
                                           AND NOW() - INTERVAL '{week_offset - 1} weeks'
                    """,
                        tenant_id,
                    )
                    or 0
                )

                velocity_chart.append(
                    {"week": f"Week -{week_offset}", "completed": week_completed})

            # Technical debt
            blocked_tasks = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND status = 'blocked'
                """,
                    tenant_id,
                )
                or 0
            )

            critical_bugs = (
                await conn.fetchval(
                    """
                SELECT COUNT(*)
                FROM tasks
                WHERE tenant_id = $1
                  AND priority = 'critical'
                  AND (title ILIKE '%bug%' OR description ILIKE '%bug%')
                  AND status != 'completed'
                """,
                    tenant_id,
                )
                or 0
            )

            technical_debt = {
                "total_debt_hours": blocked_tasks * 8,
                "critical_items": critical_bugs,
                "blocked_tasks": blocked_tasks,
                "trend": ("improving" if blocked_tasks < 5 else "stable" if blocked_tasks < 10 else "growing"),
            }

            return {
                "team_metrics": team_metrics,
                "code_quality_trends": code_quality_trends,
                "velocity_chart": velocity_chart,
                "technical_debt": technical_debt,
                "team_performance": team_performance,
            }

        except Exception as e:
            logger.error(
                "Error fetching team lead dashboard",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return self._get_demo_dashboard()

    def _get_demo_dashboard(self) -> Dict[str, Any]:
        """Возвращает демонстрационные данные для дашборда тимлида."""
        return {
            "team_metrics": {
                "velocity": 75,
                "code_quality": 88,
                "bug_rate": 2.3,
                "deployment_frequency": 12,
            },
            "code_quality_trends": [
                {"week": "Week -6", "quality": 82},
                {"week": "Week -5", "quality": 84},
                {"week": "Week -4", "quality": 86},
                {"week": "Week -3", "quality": 87},
                {"week": "Week -2", "quality": 88},
                {"week": "Week -1", "quality": 88},
            ],
            "velocity_chart": [
                {"week": "Week -6", "completed": 12},
                {"week": "Week -5", "completed": 15},
                {"week": "Week -4", "completed": 18},
                {"week": "Week -3", "completed": 16},
                {"week": "Week -2", "completed": 20},
                {"week": "Week -1", "completed": 22},
            ],
            "technical_debt": {
                "total_debt_hours": 96,
                "critical_items": 4,
                "blocked_tasks": 12,
                "trend": "improving",
            },
            "team_performance": [
                {
                    "name": "Alice Johnson",
                    "role": "developer",
                    "workload": 85,
                    "tasks_active": 8,
                    "tasks_completed_week": 5,
                    "status": "normal",
                },
                {
                    "name": "Bob Smith",
                    "role": "developer",
                    "workload": 95,
                    "tasks_active": 12,
                    "tasks_completed_week": 6,
                    "status": "overloaded",
                },
                {
                    "name": "Carol White",
                    "role": "qa",
                    "workload": 60,
                    "tasks_active": 6,
                    "tasks_completed_week": 4,
                    "status": "available",
                },
            ],
        }
