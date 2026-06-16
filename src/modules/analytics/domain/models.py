from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List


class MetricType(str, Enum):
    """Типы метрик."""

    PERFORMANCE = "performance"
    QUALITY = "quality"
    COST = "cost"
    USER_SATISFACTION = "user_satisfaction"
    BUSINESS = "business"


@dataclass
class AnalyticsReport:
    """Доменная модель аналитического отчета."""

    id: str
    title: str
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, Any] = field(default_factory=dict)
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализует отчет в словарь."""
        return {
            "id": self.id,
            "title": self.title,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "metrics": self.metrics,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }
