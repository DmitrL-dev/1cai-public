"""
Сервис исполнительного дашборда.

Бизнес-логика для KPI и метрик уровня руководства.
"""
import random
from datetime import datetime, timedelta
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

        # ROI metric (mock calculation)
        roi = {
            "value": 45200,
            "previous_value": 39300,
            "change": 15,
            "trend": "up",
            "status": "good",
            "format": "currency",
        }

        # Users metric
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users") or 1234

        users = {
            "value": users_count,
            "previous_value": users_count - 156,
            "change": 14,
            "trend": "up",
            "status": "good",
            "format": "number",
        }

        # Growth metric
        growth = {
            "value": 23,
            "change": 5,
            "trend": "up",
            "status": "good",
            "format": "percentage",
        }

        # Revenue trend (last 12 months)
        revenue_trend = []
        for i in range(12):
            month = (datetime.now() - timedelta(days=30 * (11 - i))).strftime("%b")
            value = 30000 + (i * 5000) + random.randint(-2000, 3000)
            revenue_trend.append({"date": month, "value": value})

        # Alerts
        alerts = [
            {
                "id": "alert-1",
                "type": "warning",
                "title": "Budget at 85%",
                "message": "Review budget allocation soon",
                "timestamp": datetime.now().isoformat(),
                "read": False,
            },
            {
                "id": "alert-2",
                "type": "info",
                "title": "Sprint on track",
                "message": "All tasks progressing well",
                "timestamp": datetime.now().isoformat(),
                "read": False,
            },
        ]

        # Objectives
        objectives = [
            {
                "id": "obj-1",
                "title": "Q1 2025: Launch Multi-Tenant SaaS",
                "progress": 80,
                "status": "on_track",
                "target_date": "2025-03-31",
            },
            {
                "id": "obj-2",
                "title": "Q1 2025: Acquire 100 Customers",
                "progress": 35,
                "status": "behind",
                "target_date": "2025-03-31",
            },
            {
                "id": "obj-3",
                "title": "Q2 2025: €50K MRR",
                "progress": 10,
                "status": "on_track",
                "target_date": "2025-06-30",
            },
        ]

        # Top initiatives
        top_initiatives = [
            {
                "id": "init-1",
                "name": "AI Code Review",
                "status": "beta",
                "users": 23,
                "eta": None,
            },
            {
                "id": "init-2",
                "name": "1C:Copilot",
                "status": "in_progress",
                "users": 0,
                "eta": "2 weeks",
            },
        ]

        usage_stats = {
            "api_calls": 125000,
            "ai_queries": 45000,
            "storage_gb": 450,
            "uptime": 99.9,
        }

        return {
            "health": health,
            "roi": roi,
            "users": users,
            "growth": growth,
            "revenue_trend": revenue_trend,
            "alerts": alerts,
            "objectives": objectives,
            "top_initiatives": top_initiatives,
            "usage_stats": usage_stats,
        }
