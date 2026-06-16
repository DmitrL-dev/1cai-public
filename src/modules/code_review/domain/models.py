"""
Code Review Domain Models
"""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CodeContextRequest(BaseModel):
    """Code analysis request"""

    content: str = Field(..., max_length=100000, description="Source code for analysis")
    language: Literal["bsl", "typescript", "javascript", "python", "java", "csharp"] = Field(
        default="bsl", description="Programming language"
    )
    fileName: Optional[str] = Field(None, max_length=500, description="File name")
    projectContext: Optional[dict] = Field(None, description="Project context")
    cursorPosition: Optional[dict] = Field(None, description="Cursor position")
    recentChanges: Optional[List[str]] = Field(None, description="Recent changes")


class CodeSuggestion(BaseModel):
    """Code improvement suggestion"""

    id: str
    type: Literal["error", "warning", "info", "hint"]
    severity: Literal["critical", "high", "medium", "low"]
    message: str
    description: str
    suggestion: Optional[str] = None
    code: Optional[str] = None
    position: dict
    category: Literal["performance", "security",
        "best-practice", "style", "bug", "optimization"]
    autoFixable: bool
    confidence: float = Field(..., ge=0, le=1)


class CodeMetrics(BaseModel):
    """Code quality metrics"""

    complexity: int = Field(..., ge=0, le=100)
    maintainability: int = Field(..., ge=0, le=100)
    securityScore: int = Field(..., ge=0, le=100)
    performanceScore: int = Field(..., ge=0, le=100)
    codeQuality: int = Field(..., ge=0, le=100)


class CodeStatistics(BaseModel):
    """Code statistics"""

    totalLines: int
    functions: int
    variables: int
    comments: int
    potentialIssues: int


class CodeAnalysisResponse(BaseModel):
    """Code analysis response"""

    suggestions: List[CodeSuggestion]
    metrics: CodeMetrics
    statistics: CodeStatistics
    recommendations: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)
    analysisId: str


class AutoFixRequest(BaseModel):
    """Auto-fix request"""

    suggestionId: str = Field(..., max_length=100)
    code: str = Field(..., max_length=100000)


class AutoFixResponse(BaseModel):
    """Auto-fix result"""

    fixedCode: str
    changes: List[dict]
    success: bool
    message: str
