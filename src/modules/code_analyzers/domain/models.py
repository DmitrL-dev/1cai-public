"""
Code Analyzers Domain Models
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisIssue(BaseModel):
    """Issue found during code analysis"""

    id: str
    type: str  # error, warning, hint
    severity: str  # critical, high, medium, low
    message: str
    description: str
    suggestion: Optional[str] = None
    position: Dict[str, int]  # line, column
    category: str
    autoFixable: bool = False
    confidence: float = 1.0


class AnalysisMetrics(BaseModel):
    """Code quality metrics"""

    complexity: int = 0
    maintainability: int = 0
    securityScore: int = 0
    performanceScore: int = 0
    codeQuality: int = 0


class AnalysisStatistics(BaseModel):
    """Code statistics"""

    totalLines: int = 0
    functions: int = 0
    variables: int = 0
    comments: int = 0
    potentialIssues: int = 0


class AnalysisResult(BaseModel):
    """Result of code analysis"""

    suggestions: List[AnalysisIssue] = Field(default_factory=list)
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    statistics: AnalysisStatistics = Field(default_factory=AnalysisStatistics)
    recommendations: List[str] = Field(default_factory=list)
