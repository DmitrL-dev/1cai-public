"""
BA Sessions Domain Models
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceabilityRequest(BaseModel):
    """Request for building traceability matrix"""

    requirement_ids: List[str] = Field(..., description="List of requirement IDs")
    include_code: bool = Field(default=True, description="Include code links")
    include_tests: bool = Field(default=True, description="Include test links")
    include_incidents: bool = Field(default=True, description="Include incident links")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class KPIGenerationRequest(BaseModel):
    """Request for KPI generation"""

    initiative_name: str = Field(..., description="Initiative/Feature name")
    feature_id: Optional[str] = Field(
        default=None, description="Feature ID for graph search")
    include_technical: bool = Field(default=True, description="Include technical KPIs")
    include_business: bool = Field(default=True, description="Include business KPIs")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class ProcessModelRequest(BaseModel):
    """Request for process model generation"""

    description: str = Field(..., description="Process description")
    requirement_id: Optional[str] = Field(
        default=None, description="Requirement ID for graph linking")
    format: str = Field(default="mermaid",
                        description="Output format (mermaid, plantuml, json)")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class JourneyMapRequest(BaseModel):
    """Request for Customer Journey Map generation"""

    journey_description: str = Field(..., description="Journey description")
    stages: Optional[List[str]] = Field(
        default=None, description="List of stages (optional)")
    format: str = Field(default="mermaid",
                        description="Output format (mermaid, plantuml, json)")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class SyncRequirementsRequest(BaseModel):
    """Request for syncing requirements to Jira"""

    requirement_ids: List[str] = Field(..., description="List of requirement IDs")
    project_key: Optional[str] = Field(default=None, description="Jira project key")
    issue_type: str = Field(
        default="Story", description="Issue type (Story, Task, Epic)")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class SyncBPMNRequest(BaseModel):
    """Request for syncing BPMN to Confluence"""

    process_model: Dict[str, Any] = Field(..., description="Process model")
    space_key: Optional[str] = Field(default=None, description="Confluence space key")
    parent_page_id: Optional[str] = Field(default=None, description="Parent page ID")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class EnablementPlanRequest(BaseModel):
    """Request for enablement plan generation"""

    feature_name: str = Field(..., description="Feature name")
    audience: str = Field(default="BA+Dev+QA", description="Target audience")
    include_examples: bool = Field(
        default=True, description="Include examples from graph")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class GuideRequest(BaseModel):
    """Request for guide generation"""

    topic: str = Field(..., description="Guide topic")
    format: str = Field(default="markdown",
                        description="Output format (markdown, confluence, html)")
    include_code_examples: bool = Field(
        default=True, description="Include code examples from graph")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")


class PresentationRequest(BaseModel):
    """Request for presentation outline generation"""

    topic: str = Field(..., description="Presentation topic")
    audience: str = Field(default="stakeholders",
                          description="Audience (stakeholders, technical, executive)")
    duration_minutes: int = Field(default=30, description="Duration in minutes")
    use_graph: bool = Field(default=True, description="Use Unified Change Graph")
