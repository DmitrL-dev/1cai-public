"""
Test Generation API Routes
"""
from datetime import datetime

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.middleware.rate_limiter import limiter
from src.modules.test_generation.domain.models import (
    GeneratedTest,
    TestGenerationRequest,
    TestGenerationResponse,
)
from src.modules.test_generation.services.generator import TestGeneratorService
from src.services.openai_code_analyzer import get_openai_analyzer

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Test Generation"])

# Initialize service
generator_service = TestGeneratorService()


@router.post(
    "/generate",
    response_model=TestGenerationResponse,
    summary="Generate tests for code",
    description="Automatically generate tests for the provided code",
)
@limiter.limit("10/minute")
async def generate_tests(request: Request, request_data: TestGenerationRequest) -> TestGenerationResponse:
    """
    Generate tests with input validation
    """
    try:
        # Input validation and sanitization
        code = request_data.code.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")

        # Limit code length
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            raise HTTPException(
                status_code=400,
                detail=f"Code too long. Maximum length: {max_code_length} characters",
            )

        # Generate tests
        tests = await generator_service.generate_tests(
            code=code,
            language=request_data.language,
            include_edge_cases=request_data.includeEdgeCases,
            timeout=30.0,
        )

        # Calculate summary
        total_functions = len(tests)
        total_test_cases = sum(len(t.get("testCases", [])) for t in tests)

        coverage_values = [t.get("coverage", {}).get("lines", 0)
                                 for t in tests if "coverage" in t]
        avg_coverage = sum(coverage_values) / \
                           len(coverage_values) if coverage_values else 0

        summary = {
            "totalTests": len(tests),
            "totalTestCases": total_test_cases,
            "totalFunctions": total_functions,
            "averageCoverage": round(avg_coverage, 2),
            "language": request_data.language,
            "framework": (tests[0].get("framework") if tests else None),
        }

        generation_id = f"gen-{datetime.now().timestamp()}"

        # Convert to domain models
        test_objects = [GeneratedTest(**t) for t in tests]

        return TestGenerationResponse(tests=test_objects, summary=summary, generationId=generation_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in test generation",
            extra={
                "error": str(e),
                "language": request_data.language,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while generating tests")


@router.get("/health", summary="Check service status")
async def health_check() -> Dict[str, Any]:
    """Check Test Generation service availability"""
    openai_analyzer = get_openai_analyzer()
    ai_enabled = getattr(openai_analyzer, "enabled", False)

    return {
        "status": "healthy",
        "service": "test-generation",
        "version": "1.1.0",
        "supported_languages": ["bsl", "typescript", "python", "javascript"],
        "features": {
            "unit_tests": True,
            "ai_generation": ai_enabled,
        },
    }
