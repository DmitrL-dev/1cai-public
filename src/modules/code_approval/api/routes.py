"""
Code Approval API Routes
"""
import asyncio
from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.code_approval.domain.models import (
    BulkApprovalRequest,
    CodeApprovalRequest,
    CodeGenerationRequest,
)
from src.modules.code_approval.services.approval_service import CodeApprovalService

logger = StructuredLogger(__name__).logger

router = APIRouter(tags=["Code Approval"])
limiter = Limiter(key_func=get_remote_address)


# Dependency
def get_approval_service() -> CodeApprovalService:
    return CodeApprovalService()


@router.post(
    "/generate",
    summary="Generate code with AI",
    description="Generate code with AI and return suggestion with approval token",
    responses={
        200: {"description": "Code generated successfully"},
        400: {"description": "Invalid input"},
        403: {"description": "Request blocked by security"},
        429: {"description": "Rate limit exceeded"},
    },
)
@limiter.limit("10/minute")
async def generate_code(
    api_request: Request,
    request: CodeGenerationRequest,
    service: CodeApprovalService = Depends(get_approval_service),
) -> Dict[str, Any]:
    """
    Generate code with AI with input validation
    """
    try:
        # Input validation and sanitization
        prompt = request.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty")

        max_prompt_length = 5000
        if len(prompt) > max_prompt_length:
            raise HTTPException(
                status_code=400,
                detail=f"Prompt too long. Maximum length: {max_prompt_length} characters",
            )

        user_id = request.user_id.strip()[:100]
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID cannot be empty")

        result = service.generate_code(
            prompt=prompt, user_id=user_id, context=request.context)

        if result.get("blocked"):
            raise HTTPException(
                status_code=403,
                detail=result.get("error", "Request blocked by security"),
            )

        return {
            "success": True,
            "suggestion": result["suggestion"],
            "token": result["token"],
            "safety": result["safety"],
            "requires_approval": result["requires_approval"],
            "can_auto_apply": result["can_auto_apply"],
            "preview_url": result["preview_url"],
            "redacted": result.get("redacted", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unexpected error generating code",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "user_id": request.user_id,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred while generating code")


@router.get("/preview/{token}")
async def get_preview(token: str, service: CodeApprovalService = Depends(get_approval_service)) -> Dict[str, Any]:
    """
    Get preview suggestion for review
    """
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")

    max_token_length = 200
    if len(token) > max_token_length:
        raise HTTPException(status_code=400, detail="Token too long")

    try:
        suggestion_data = service.get_preview(token)
        if not suggestion_data:
            raise HTTPException(status_code=404, detail="Token not found or expired")

        return {
            "suggestion": suggestion_data["suggestion"],
            "prompt": suggestion_data["prompt"],
            "safety": suggestion_data["safety"],
            "created_at": suggestion_data["created_at"].isoformat(),
            "expires_at": (suggestion_data["created_at"] + timedelta(minutes=30)).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while retrieving preview")


@router.post("/approve")
@limiter.limit("30/minute")
async def approve_suggestion(
    api_request: Request,
    request: CodeApprovalRequest,
    service: CodeApprovalService = Depends(get_approval_service),
) -> Dict[str, Any]:
    """
    Approve and apply suggestion
    """
    if not request.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")

    if not request.approved_by_user.strip():
        raise HTTPException(status_code=400, detail="Approved by user cannot be empty")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.apply_suggestion,
                token=request.token,
                approved_by_user=request.approved_by_user,
                changes_made=request.changes_made,
            ),
            timeout=30.0,
        )

        if result.get("blocked"):
            raise HTTPException(status_code=403, detail=result.get(
                "error", "Application blocked"))

        logger.info(
            "Suggestion approved successfully",
            extra={
                "token": request.token[:50],
                "approved_by_user": request.approved_by_user,
            },
        )

        return {
            "success": True,
            "applied": True,
            "commit_sha": result.get("commit_sha"),
            "message": "Code suggestion applied successfully",
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in approve_suggestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while approving suggestion")


@router.post("/approve-all")
@limiter.limit("10/minute")
async def bulk_approve(
    api_request: Request,
    request: BulkApprovalRequest,
    service: CodeApprovalService = Depends(get_approval_service),
) -> Dict[str, Any]:
    """
    Bulk approval for multiple suggestions
    """
    if not request.tokens:
        raise HTTPException(status_code=400, detail="Tokens list cannot be empty")

    if len(request.tokens) > 100:
        request.tokens = request.tokens[:100]

    validated_tokens = [t.strip() for t in request.tokens if t.strip()]

    if not validated_tokens:
        raise HTTPException(status_code=400, detail="No valid tokens provided")

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.bulk_approve_safe_suggestions,
                tokens=validated_tokens,
                approved_by_user=request.approved_by_user,
            ),
            timeout=60.0,
        )

        return {
            "success": True,
            "approved": len(result["approved"]),
            "rejected": len(result["rejected"]),
            "errors": len(result["errors"]),
            "details": result,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Bulk operation timed out")
    except Exception as e:
        logger.error(f"Error in bulk_approve: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while processing bulk approval")


@router.delete("/reject/{token}")
async def reject_suggestion(token: str, service: CodeApprovalService = Depends(get_approval_service)) -> Dict[str, Any]:
    """
    Reject suggestion
    """
    if not token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty")

    try:
        if not service.reject_suggestion(token):
            raise HTTPException(status_code=404, detail="Token not found")

        return {"success": True, "message": "Suggestion rejected"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reject_suggestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An error occurred while rejecting suggestion")


@router.get("/pending")
async def get_pending_suggestions(user_id: str, service: CodeApprovalService = Depends(get_approval_service)) -> Dict[str, Any]:
    """
    Get all pending suggestions for user
    """
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="User ID cannot be empty")

    try:
        suggestions = service.get_pending_suggestions(user_id)
        return {"pending": len(suggestions), "suggestions": suggestions}
    except Exception as e:
        logger.error(f"Error in get_pending_suggestions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while retrieving pending suggestions",
        )
