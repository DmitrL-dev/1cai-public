"""
Code Analyzers API Routes
"""

from typing import Dict, Any
from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from src.modules.auth.api.dependencies import get_current_user
from src.modules.code_analyzers.services.analyzer_service import CodeAnalyzerService
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

router = APIRouter(prefix="/code_analyzers", tags=["Code Analyzers"])


class CodeRequest(BaseModel):
    code: str


def get_analyzer_service():
    return CodeAnalyzerService()


@router.post(
    "/analyze/python",
    summary="Analyze Python code",
    description="Static analysis of Python code for issues and metrics",
)
async def analyze_python(
    request: CodeRequest,
    current_user=Depends(get_current_user),
    service: CodeAnalyzerService = Depends(get_analyzer_service),
) -> Dict[str, Any]:
    """
    Analyze Python code
    """
    try:
        logger.info("Analyzing Python code", user_id=current_user.id)
        return service.analyze_python(request.code)
    except Exception as e:
        logger.error("Failed to analyze Python code: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/analyze/typescript",
    summary="Analyze TypeScript code",
    description="Static analysis of TypeScript code for issues and metrics",
)
async def analyze_typescript(
    request: CodeRequest,
    current_user=Depends(get_current_user),
    service: CodeAnalyzerService = Depends(get_analyzer_service),
) -> Dict[str, Any]:
    """
    Analyze TypeScript code
    """
    try:
        logger.info("Analyzing TypeScript code", user_id=current_user.id)
        return service.analyze_typescript(request.code)
    except Exception as e:
        logger.error("Failed to analyze TypeScript code: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post(
    "/analyze/javascript",
    summary="Analyze JavaScript code",
    description="Static analysis of JavaScript code for issues and metrics",
)
async def analyze_javascript(
    request: CodeRequest,
    current_user=Depends(get_current_user),
    service: CodeAnalyzerService = Depends(get_analyzer_service),
) -> Dict[str, Any]:
    """
    Analyze JavaScript code
    """
    try:
        logger.info("Analyzing JavaScript code", user_id=current_user.id)
        return service.analyze_javascript(request.code)
    except Exception as e:
        logger.error("Failed to analyze JavaScript code: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
