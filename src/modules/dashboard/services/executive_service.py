"""
Сервис исполнительного дашборда.

Бизнес-логика для KPI и метрик уровня руководства.
"""
from datetime import datetime
from typing import Any, Dict

import asyncpg

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.dashboard.services.health_calculator import HealthCalculator

logger = StructuredLogger(__name__).logger


class ExecutiveService:
    """Бизнес-логика исполнительного дашборда."""

    def __init__(self) -> None:
        self.health_calculator = HealthCalculator()

    async def get_dashboard(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает данные для исполнительного дашборда.

        Args:
            conn: Подключение к БД.

        Returns:
            Dict[str, Any]: Словарь с данными дашборда.
        """
        # Calculate REAL health score
        health_score = await self.health_calculator.calculate_health_score(conn)

        health = {
            "status": self.health_calculator.get_health_status(health_score),
            "score": health_score,
            "message": self.health_calculator.get_health_message(health_score),
        }

        roi = {
            "value": 0,
            "previous_value": 0,
            "change": 0,
            "measured": False,
            "trend": "up",
            "status": "not_measured",
            "format": "currency",
            "caveat": "ROI is not calculated without linked cost and value metrics.",
        }

        users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 0

        users = {
            "value": users_count,
            "previous_value": users_count,
            "change": 0,
            "measured": True,
            "trend": "stable",
            "status": "measured",
            "format": "number",
        }

        growth = {
            "value": 0,
            "change": 0,
            "measured": False,
            "trend": "unknown",
            "status": "not_measured",
            "format": "percentage",
            "caveat": "Growth requires historical user or revenue snapshots.",
        }

        revenue_trend = []
        alerts = []
        objectives = []
        top_initiatives = []

        usage_stats = {
            "api_calls": 0,
            "ai_queries": 0,
            "storage_gb": 0,
            "uptime": 0,
            "measured": False,
            "caveat": "Usage stats require telemetry snapshots.",
        }

        return {
            "data_contract": {
                "mode": "dashboard_evidence_contract",
                "coverage": "partial_database_evidence",
                "generated_at": datetime.utcnow().isoformat(),
            },
            "health": health,
            "roi": roi,
            "users": users,
            "growth": growth,
            "revenue_trend": revenue_trend,
            "alerts": alerts,
            "objectives": objectives,
            "top_initiatives": top_initiatives,
            "usage_stats": usage_stats,
            "caveats": [
                "Executive dashboard avoids synthetic ROI, revenue and objective data.",
                "Connect billing, telemetry and planning sources to turn not_measured fields into measured metrics.",
            ],
        }
