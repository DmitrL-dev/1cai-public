"""
Test Generation Domain Models
"""
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class TestGenerationRequest(BaseModel):
    """Request for test generation"""

    code: str = Field(..., max_length=50000, description="Source code for testing")
    language: Literal["bsl", "typescript", "python", "javascript"] = Field(
        default="bsl", description="Programming language"
    )
    functionName: Optional[str] = Field(
        None, max_length=200, description="Specific function name to test")
    testType: Literal["unit", "integration", "e2e", "all"] = Field(
        default="unit", description="Type of tests to generate"
    )
    includeEdgeCases: bool = Field(default=True, description="Include edge cases")
    framework: Optional[str] = Field(
        None, max_length=100, description="Testing framework")


class TestCase(BaseModel):
    """Test case definition"""

    id: str = Field(..., max_length=100)
    name: str = Field(..., max_length=200)
    description: str = Field(..., max_length=1000)
    input: dict
    expectedOutput: Any
    type: Literal["unit", "integration", "e2e"]
    category: Literal["positive", "negative", "edge", "boundary"]


class CoverageMetrics(BaseModel):
    """Code coverage metrics"""

    lines: int = Field(..., ge=0, le=100)
    branches: int = Field(..., ge=0, le=100)
    functions: int = Field(..., ge=0, le=100)


class GeneratedTest(BaseModel):
    """Generated test suite"""

    id: str = Field(..., max_length=100)
    functionName: str = Field(..., max_length=200)
    testCases: List[TestCase]
    code: str = Field(..., max_length=50000)
    language: str = Field(..., max_length=50)
    framework: str = Field(..., max_length=100)
    coverage: CoverageMetrics


class TestGenerationResponse(BaseModel):
    """Response with generated tests"""

    tests: List[GeneratedTest]
    summary: dict
    timestamp: datetime = Field(default_factory=datetime.now)
    generationId: str = Field(..., max_length=100)
