from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskAssessmentRequest(BaseModel):
    """Risk assessment request"""

    requirements: str = Field(..., description="Project requirements")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Project context")
    architecture: Optional[Dict[str, Any]] = Field(
        default=None, description="Architecture solution")


class RiskAssessmentResponse(BaseModel):
    """Risk assessment response"""

    risk_level: str  # low, medium, high, critical
    risks: List[Dict[str, Any]]
    mitigation_strategies: List[str]
    confidence_score: float
    timestamp: datetime


class RiskRecord(BaseModel):
    """Risk record"""

    id: str
    category: str  # technical, business, operational, security
    description: str
    impact: str  # low, medium, high, critical
    probability: float  # 0.0 - 1.0
    mitigation_plan: str
    owner: str
    status: str  # identified, assessing, mitigating, resolved
    created_at: datetime
