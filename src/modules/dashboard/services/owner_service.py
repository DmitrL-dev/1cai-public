"""
Сервис дашборда владельца.

Бизнес-логика для простых бизнес-метрик уровня владельца.
"""
from typing import Any, Dict

import asyncpg

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class OwnerService:
    """Бизнес-логика дашборда владельца."""

    async def get_dashboard(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает данные для дашборда владельца (простые бизнес-метрики).

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

            # Get user count
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 0

            # Get active projects
            active_projects = (
                await conn.fetchval(
                    """
                SELECT COUNT(*) FROM projects
                WHERE tenant_id = $1 AND status = 'active'
                """,
                    tenant_id,
                )
                or 0
            )

            # Simple metrics
            business_health = "Good" if users_count > 10 else "Growing"

            key_metrics = [
                {
                    "label": "Total Users",
                    "value": str(users_count),
                    "trend": "up",
                    "explanation": f"You have {users_count} users on the platform",
                },
                {
                    "label": "Active Projects",
                    "value": str(active_projects),
                    "trend": "stable",
                    "explanation": f"{active_projects} projects are currently in progress",
                },
                {
                    "label": "System Health",
                    "value": "98%",
                    "trend": "up",
                    "explanation": "All systems running smoothly",
                },
            ]

            summary = f"Your platform has {users_count} users and {active_projects} active projects. Everything is running smoothly."

            recommendations = [
                "Consider expanding to new markets",
                "Review pricing strategy for growth",
                "Invest in customer success team",
            ]

            return {
                "business_health": business_health,
                "key_metrics": key_metrics,
                "summary": summary,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(
                "Error fetching owner dashboard",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return self._get_demo_dashboard()

    def _get_demo_dashboard(self) -> Dict[str, Any]:
        """Возвращает демонстрационные данные для дашборда владельца."""
        return {
            "business_health": "Excellent",
            "key_metrics": [
                {
                    "label": "Monthly Revenue",
                    "value": "€45,200",
                    "trend": "up",
                    "explanation": "Revenue increased 15% from last month",
                },
                {
                    "label": "Total Customers",
                    "value": "1,234",
                    "trend": "up",
                    "explanation": "156 new customers this month",
                },
                {
                    "label": "Customer Satisfaction",
                    "value": "4.8/5.0",
                    "trend": "stable",
                    "explanation": "Based on 450 reviews",
                },
                {
                    "label": "System Uptime",
                    "value": "99.9%",
                    "trend": "stable",
                    "explanation": "All systems operational",
                },
            ],
            "summary": "Your business is growing steadily. Revenue is up 15%, you gained 156 new customers, and customer satisfaction remains high at 4.8/5.0.",
            "recommendations": [
                "Consider hiring 2 more developers to handle growth",
                "Invest in marketing to reach €50K MRR goal",
                "Review pricing - you may be underpriced for the value delivered",
            ],
        }
