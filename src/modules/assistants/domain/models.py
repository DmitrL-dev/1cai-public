"""
Assistants Domain Models
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request for chat with assistant"""

    query: str = Field(..., max_length=5000, description="User message")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context")
    conversation_id: Optional[str] = Field(
        default=None, max_length=100, description="Conversation ID")


class ChatResponse(BaseModel):
    """Response from assistant"""

    message_id: str
    content: str
    role: str
    timestamp: datetime
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float
    conversation_id: str


class AnalyzeRequirementsRequest(BaseModel):
    """Request for requirements analysis"""

    requirements_text: str = Field(..., max_length=10000,
                                   description="Requirements text")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Project context")


class GenerateDiagramRequest(BaseModel):
    """Request for diagram generation"""

    architecture_proposal: Dict[str,
        Any] = Field(..., description="Architecture proposal")
    diagram_type: str = Field(default="flowchart", max_length=50,
                              description="Diagram type")
    diagram_requirements: Optional[Dict[str, Any]] = Field(
        default=None, description="Diagram requirements")


class ComprehensiveAnalysisRequest(BaseModel):
    """Request for comprehensive analysis"""

    requirements_text: str = Field(..., max_length=10000,
                                   description="Requirements text")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Project context")


class RiskAssessmentRequest(BaseModel):
    """Request for risk assessment"""

    architecture: Dict[str, Any] = Field(..., description="Architecture solution")
    project_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Project context")
