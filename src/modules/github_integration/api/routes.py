"""
GitHub Integration API Routes
FastAPI endpoints for GitHub webhook and manual review
"""
import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.github_integration.services.github_client import GitHubClient
from src.modules.github_integration.services.review_service import ReviewService
from src.modules.github_integration.services.webhook_handler import WebhookHandler

logger = StructuredLogger(__name__).logger

# Create router
router = APIRouter(tags=["GitHub Integration"])

# Initialize services
github_client = GitHubClient()
webhook_handler = WebhookHandler()
review_service = ReviewService(github_client)


@router.post("/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None),
    x_hub_signature_256: str = Header(None),
) -> Dict[str, Any]:
    """
    GitHub Webhook endpoint

    Accepts events from GitHub:
    - pull_request
    - push
    - etc.

    Args:
        request: FastAPI request object
        x_github_event: GitHub event type header
        x_hub_signature_256: Webhook signature header

    Returns:
        Processing result dictionary

    Raises:
        HTTPException: On validation or processing errors
    """
    try:
        # Read payload with timeout
        payload = await asyncio.wait_for(request.body(), timeout=30.0)

        # Validate payload size (prevent DoS)
        max_payload_size = 10 * 1024 * 1024  # 10 MB
        if len(payload) > max_payload_size:
            logger.warning(
                "Payload too large",
                extra={"payload_size": len(payload), "max_size": max_payload_size},
            )
            raise HTTPException(status_code=413, detail="Payload too large")

        # Verify signature
        if x_hub_signature_256:
            if not isinstance(x_hub_signature_256, str) or not x_hub_signature_256.strip():
                logger.warning("Invalid signature header")
                raise HTTPException(status_code=401, detail="Invalid signature format")

            if not github_client.verify_webhook_signature(payload, x_hub_signature_256):
                logger.warning("Invalid webhook signature", extra={
                               "event_type": x_github_event})
                raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse JSON with timeout
        try:
            event_data = await asyncio.wait_for(request.json(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error("Timeout parsing JSON")
            raise HTTPException(status_code=504, detail="Timeout parsing request")
        except Exception as e:
            logger.error(
                "Error parsing JSON",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise HTTPException(status_code=400, detail="Invalid JSON payload")

        # Validate event type
        if not x_github_event or not isinstance(x_github_event, str):
            logger.warning("Missing or invalid x_github_event header")
            return {"status": "error", "reason": "Missing event type"}

        # Limit event type length
        if len(x_github_event) > 100:
            logger.warning("Event type too long", extra={
                           "event_type_length": len(x_github_event)})
            x_github_event = x_github_event[:100]

        # Handle pull_request events
        if x_github_event == "pull_request":
            # Parse and validate PR event
            try:
                pr_event = await webhook_handler.handle_pull_request_event(event_data)
            except ValueError as e:
                logger.error("Invalid PR event: %s", e)
                return {"status": "error", "reason": str(e)}

            # Check if event should be processed
            if not webhook_handler.should_process_event(pr_event):
                return {
                    "status": "skipped",
                    "reason": f"Action {pr_event.action} not handled",
                }

            # Process PR review with timeout
            result = await asyncio.wait_for(
                review_service.review_pull_request(
                    pr_event.repository_full_name, pr_event.number),
                timeout=60.0,  # 60 seconds for PR processing
            )
            return result

        logger.info("Unhandled GitHub event type", extra={"event_type": x_github_event})
        return {"status": "event_not_handled", "event_type": x_github_event}

    except HTTPException:
        raise
    except asyncio.TimeoutError:
        logger.error("Timeout in github_webhook")
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        logger.error(
            "Unexpected error in github_webhook",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "event_type": x_github_event,
            },
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/review")
async def manual_review(code: str, filename: str = "code.bsl") -> Dict[str, Any]:
    """
    Manual code review endpoint (for testing)

    Args:
        code: Code content to review
        filename: File name (default: code.bsl)

    Returns:
        Review result dictionary

    Raises:
        HTTPException: On validation or processing errors
    """
    # Input validation
    if not isinstance(code, str):
        logger.warning("Invalid code type", extra={"code_type": type(code).__name__})
        raise HTTPException(status_code=400, detail="Code must be a string")

    # Limit code length (prevent DoS)
    max_code_length = 10 * 1024 * 1024  # 10 MB
    if len(code) > max_code_length:
        logger.warning(
            "Code too long",
            extra={"code_length": len(code), "max_length": max_code_length},
        )
        raise HTTPException(status_code=413, detail="Code too large")

    if not isinstance(filename, str) or not filename.strip():
        logger.warning("Invalid filename", extra={
                       "filename_type": type(filename).__name__})
        filename = "code.bsl"

    # Sanitize filename (prevent path traversal)
    filename = filename.replace("..", "").replace("/", "_").replace("\\", "_")
    if len(filename) > 255:
        filename = filename[:255]

    try:
        # Timeout for review operation (60 seconds)
        review_result = await asyncio.wait_for(review_service.review_code(code, filename), timeout=60.0)

        logger.info(
            "Manual review completed",
            extra={
                "filename": filename,
                "code_length": len(code),
                "review_status": review_result.get("overall_status", "unknown"),
            },
        )

        return review_result

    except asyncio.TimeoutError:
        logger.error(
            "Timeout in manual_review",
            extra={"filename": filename, "code_length": len(code)},
        )
        raise HTTPException(status_code=504, detail="Review operation timed out")
    except Exception as e:
        logger.error(
            "Error in manual_review",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "filename": filename,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="An error occurred during code review")
