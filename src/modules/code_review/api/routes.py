"""
Code Review API Routes
"""
import asyncio
from datetime import datetime

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.middleware.rate_limiter import PUBLIC_RATE_LIMIT, limiter
from src.modules.code_review.domain.models import (
    AutoFixRequest,
    AutoFixResponse,
    CodeAnalysisResponse,
    CodeContextRequest,
    CodeMetrics,
    CodeStatistics,
    CodeSuggestion,
)
from src.modules.code_review.services.analyzer import CodeAnalyzer
from src.modules.code_review.services.fixer import CodeFixer
from src.services.caching_service import get_cache_service
from src.services.openai_code_analyzer import get_openai_analyzer

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Code Review"])

# Initialize services
analyzer = CodeAnalyzer()
fixer = CodeFixer()


@router.post(
    "/analyze",
    response_model=CodeAnalysisResponse,
    summary="Real-time code analysis",
    description="""
    Analyze code and provide improvement suggestions in real-time.

    **Supported Languages:**
    - BSL (1C:Enterprise)
    - TypeScript
    - JavaScript
    - Python
    - Java
    - C#
    """,
)
@limiter.limit(PUBLIC_RATE_LIMIT)
async def analyze_code(request: Request, request_data: CodeContextRequest, response: Response) -> CodeAnalysisResponse:
    """
    Analyze code with improvement suggestions
    """
    try:
        # Input validation and sanitization
        code = request_data.content.strip()
        if not code:
            raise HTTPException(status_code=400, detail="Code cannot be empty")

        # Limit code length (prevent DoS)
        max_code_length = 100000  # 100KB max
        if len(code) > max_code_length:
            raise HTTPException(
                status_code=400,
                detail=f"Code too long. Maximum length: {max_code_length} characters",
            )

        # Validate language
        supported_languages = ["bsl", "typescript", "python", "javascript"]
        if request_data.language not in supported_languages:
            # Allow other languages but warn
            pass

        # Sanitize file name if provided
        file_name = None
        if request_data.fileName:
            file_name = request_data.fileName.strip()[:200]  # Limit length
            # Prevent path traversal
            if ".." in file_name or "/" in file_name or "\\" in file_name:
                file_name = None  # Use None if invalid

        # Use request_data as main request
        code_request = request_data
        code_request.content = code  # Use sanitized code
        if file_name:
            code_request.fileName = file_name

        # Determine AI variant
        ai_variant = "local"
        openai_analyzer = None
        try:
            openai_analyzer = get_openai_analyzer()
            if getattr(openai_analyzer, "enabled", False):
                ai_variant = f"ai:{getattr(openai_analyzer, 'model', 'unknown')}"
        except Exception as analyzer_init_error:
            logger.warning(
                "Failed to initialize AI analyzer, fallback to local analysis",
                extra={
                    "error": str(analyzer_init_error),
                    "error_type": type(analyzer_init_error).__name__,
                },
            )
            openai_analyzer = None

        # Generate cache key
        cache_service = get_cache_service()
        cache_key = cache_service.generate_key(
            "code_review",
            content=code_request.content,
            language=code_request.language,
            fileName=code_request.fileName or "",
            ai_variant=ai_variant,
        )

        # Try to get from cache
        cached_result = await cache_service.get(cache_key)
        if cached_result:
            return CodeAnalysisResponse(**cached_result)

        # Local code analysis
        # Note: All languages now use the unified analyzer
        result = analyzer.analyze_bsl_code(code_request.content)

        # Log language for monitoring
        if code_request.language != "bsl":
            logger.info(
                f"Analyzing {code_request.language} code with BSL analyzer", extra={"language": code_request.language}
            )

        # AI analysis via OpenAI (async if available) with timeout
        ai_suggestions = []
        if openai_analyzer and getattr(openai_analyzer, "enabled", False):
            # Timeout for AI analysis (30 seconds)
            ai_timeout = 30.0
            try:
                ai_suggestions = await asyncio.wait_for(
                    openai_analyzer.analyze_code(
                        code=code_request.content,
                        language=code_request.language,
                        context=code_request.projectContext,
                    ),
                    timeout=ai_timeout,
                )

                # Merge with local suggestions
                result["suggestions"].extend(ai_suggestions)

                logger.info(
                    "AI suggestions added to analysis",
                    extra={
                        "ai_suggestions_count": len(ai_suggestions),
                        "language": code_request.language,
                    },
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "AI analysis timeout",
                    extra={
                        "language": code_request.language,
                        "code_length": len(code_request.content),
                        "timeout": ai_timeout,
                    },
                )
                # Continue without AI suggestions
            except Exception as e:
                logger.warning(
                    "AI analysis unavailable, using local analysis only",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "language": code_request.language,
                    },
                    exc_info=True,
                )

        analysis_id = f"analysis-{datetime.now().timestamp()}"

        response_data = CodeAnalysisResponse(
            suggestions=[CodeSuggestion(**s) for s in result["suggestions"]],
            metrics=CodeMetrics(**result["metrics"]),
            statistics=CodeStatistics(**result["statistics"]),
            recommendations=result["recommendations"],
            analysisId=analysis_id,
        )

        # Cache the result
        await cache_service.set(cache_key, response_data.dict(), ttl=3600)

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error analyzing code",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while analyzing code")


@router.post(
    "/auto-fix",
    response_model=AutoFixResponse,
    summary="Automatic code fix",
    description="Apply automatic fix to code based on suggestion",
)
@limiter.limit("20/minute")
async def auto_fix_code_endpoint(api_request: Request, request: AutoFixRequest, response: Response) -> AutoFixResponse:
    return await fixer.apply_auto_fix(request)


@router.get(
    "/health",
    summary="Check service status",
)
async def health_check() -> Dict[str, Any]:
    """Check Code Review service availability"""
    # Check OpenAI availability
    openai_analyzer = get_openai_analyzer()
    ai_enabled = getattr(openai_analyzer, "enabled", False)

    return {
        "status": "healthy",
        "service": "code-review",
        "version": "1.1.0",
        "features": {
            "bsl": True,
            "typescript": True,
            "python": True,
            "javascript": True,
            "ai_analysis": ai_enabled,
        },
        "openai": {
            "enabled": ai_enabled,
            "model": getattr(openai_analyzer, "model", None) if ai_enabled else None,
        },
    }
