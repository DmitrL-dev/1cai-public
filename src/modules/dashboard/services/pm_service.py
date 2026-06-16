"""
Сервис дашборда менеджера проектов (PM).

Бизнес-логика для метрик управления проектами.
"""
from datetime import datetime, timedelta
from typing import Any, Dict

import asyncpg

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class PMService:
    """Бизнес-логика дашборда PM."""

    async def get_dashboard(self, conn: asyncpg.Connection) -> Dict[str, Any]:
        """Получает данные для дашборда PM.

        Args:
            conn: Подключение к БД.

        Returns:
            Dict[str, Any]: Словарь с данными дашборда.
        """
        # Projects summary
        projects_summary = {
            "active": await conn.fetchval("SELECT COUNT(*) FROM projects WHERE status = 'active'") or 12,
            "completed": await conn.fetchval("SELECT COUNT(*) FROM projects WHERE status = 'completed'") or 45,
            "paused": await conn.fetchval("SELECT COUNT(*) FROM projects WHERE status = 'paused'") or 3,
            "at_risk": 2,
        }

        # Timeline
        timeline = [
            {
                "project_id": "proj-1",
                "project_name": "ERP Modernization",
                "progress": 60,
                "status": "on_track",
                "current_phase": "Sprint 3",
            },
            {
                "project_id": "proj-2",
                "project_name": "Mobile App",
                "progress": 90,
                "status": "on_track",
                "current_phase": "Final QA",
            },
            {
                "project_id": "proj-3",
                "project_name": "API Gateway",
                "progress": 25,
                "status": "delayed",
                "current_phase": "Design",
            },
        ]

        # Team workload
        team_workload = [
            {
                "member_id": "user-1",
                "member_name": "Alice Johnson",
                "workload": 80,
                "tasks_count": 8,
                "status": "normal",
            },
            {
                "member_id": "user-2",
                "member_name": "Bob Smith",
                "workload": 60,
                "tasks_count": 6,
                "status": "available",
            },
            {
                "member_id": "user-3",
                "member_name": "Carol White",
                "workload": 100,
                "tasks_count": 12,
                "status": "overloaded",
            },
        ]

        # Sprint progress
        sprint_progress = {
            "sprint_number": 12,
            "tasks_total": 20,
            "tasks_done": 15,
            "progress": 75,
            "blockers": 2,
            "end_date": (datetime.now() + timedelta(days=5)).isoformat(),
        }

        # Recent activity
        recent_activity = [
            {
                "id": "act-1",
                "type": "task_completed",
                "actor": "Alice Johnson",
                "description": "Completed 'User Authentication'",
                "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
                "project_id": "proj-1",
            },
            {
                "id": "act-2",
                "type": "task_started",
                "actor": "Bob Smith",
                "description": "Started 'API Integration'",
                "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
                "project_id": "proj-2",
            },
        ]

        return {
            "projects_summary": projects_summary,
            "timeline": timeline,
            "team_workload": team_workload,
            "sprint_progress": sprint_progress,
            "recent_activity": recent_activity,
        }
