"""
Сервис дашборда разработчика.

Бизнес-логика для метрик, специфичных для разработчиков.
"""
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class DeveloperService:
    """Бизнес-логика дашборда разработчика."""

    async def get_dashboard(self) -> Dict[str, Any]:
        """Получает данные для дашборда разработчика.

        Returns:
            Dict[str, Any]: Словарь с данными дашборда.
        """
        assigned_tasks = []
        code_reviews = []

        build_status = {
            "status": "not_measured",
            "measured": False,
            "last_build_at": None,
            "duration_seconds": None,
            "tests_passed": 0,
            "tests_total": 0,
            "caveat": "CI/build source is not connected.",
        }

        code_quality = {
            "coverage": 0,
            "coverage_measured": False,
            "complexity": None,
            "maintainability": None,
            "security_score": None,
            "issues": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "caveat": "Quality metrics require test reports and static analysis evidence.",
        }

        ai_suggestions = []

        return {
            "data_contract": {
                "mode": "dashboard_evidence_contract",
                "coverage": "no_developer_sources",
            },
            "assigned_tasks": assigned_tasks,
            "code_reviews": code_reviews,
            "build_status": build_status,
            "code_quality": code_quality,
            "ai_suggestions": ai_suggestions,
            "caveats": [
                "Developer dashboard avoids synthetic tasks, PRs, build results and quality scores.",
                "Connect issue tracker, VCS, CI and quality reports to populate measured sections.",
            ],
        }
