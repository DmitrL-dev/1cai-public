"""
Metrics Domain Models
"""
from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field


class MetricRecord(BaseModel):
    """Metric record"""

    metric_type: str = Field(..., min_length=1, max_length=200,
                             description="Metric type")
    service_name: str = Field(..., min_length=1, max_length=100,
                              description="Service name")
    value: float = Field(..., description="Metric value")
    timestamp: datetime = Field(default_factory=datetime.now, description="Timestamp")
    tags: Dict[str, str] = Field(default_factory=dict, description="Tags")
    unit: Optional[str] = Field(None, max_length=20, description="Unit")

    @classmethod
    def validate_name(cls, v: str) -> str:
        """Sanitize name to prevent injection"""
        if not v:
            raise ValueError("Name cannot be empty")
        # Allow alphanumeric, underscores, dots, dashes
        import re

        if not re.match(r"^[a-zA-Z0-9_.-]+$", v):
            raise ValueError("Invalid characters in name")
        return v


class MetricCollectionRequest(BaseModel):
    """Request for metric collection"""

    event: str = Field(..., description="Event or action")
    service: str = Field(..., description="Service")
    metrics: Dict[str, Union[float, int, str]] = Field(..., description="Metrics")
    timestamp: Optional[datetime] = Field(default=None, description="Event time")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Context")


class AggregatedMetrics(BaseModel):
    """Aggregated metrics"""

    metric_name: str
    avg_value: float
    min_value: float
    max_value: float
    count: int
    unit: Optional[str] = None
    time_range: Dict[str, datetime]
