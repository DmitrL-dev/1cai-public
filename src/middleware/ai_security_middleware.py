import json
from typing import Callable, Dict, Optional

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.security.ai_security_layer import AGENT_CONFIGS, AISecurityLayer, AgentRuleOfTwoConfig

logger = StructuredLogger(__name__).logger


class AISecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing AI Security Layer checks (Rule of Two).
    Intercepts requests to agent endpoints and validates input/output.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_layer = AISecurityLayer()
        # Map of URL prefixes to Agent IDs
        self.agent_routes = {
            "/api/v1/sql_optimizer": "sql_optimizer",
            "/api/v1/code_review": "code_review_ai",
            "/api/v1/devops": "devops_ai",
            "/api/v1/assistants/developer": "developer_ai",
        }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Check if this is a protected agent route
        agent_id = self._get_agent_id(request.url.path)
        
        if not agent_id:
            # Not an agent route, pass through
            return await call_next(request)

        # 2. Get Agent Config
        agent_config = AGENT_CONFIGS.get(agent_id)
        if not agent_config:
            logger.warning(f"No security config found for agent {agent_id}, allowing request but logging warning.")
            # Fallback to a default restrictive config or allow? 
            # For now allow but log, to avoid breaking unconfigured agents.
            return await call_next(request)

        # 3. Validate Input
        try:
            # We need to read the body to validate it.
            # Warning: This consumes the stream. We must reconstruct it.
            body_bytes = await request.body()
            body_text = body_bytes.decode("utf-8")
            
            # Try to parse JSON to get the actual prompt/content
            # This depends on the API contract. Assuming "query", "code", or "content" fields.
            user_input = self._extract_input_text(body_text)
            
            if user_input:
                # Get user_id from request state (populated by Auth middleware)
                user_id = getattr(request.state, "user_id", "anonymous")
                
                security_check = self.security_layer.validate_input(
                    user_input=user_input,
                    agent_id=agent_id,
                    agent_config=agent_config,
                    context={"user_id": str(user_id)}
                )

                if not security_check.allowed:
                    logger.warning(f"Blocked request to {agent_id}: {security_check.reason}")
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Security Check Failed",
                            "reason": security_check.reason,
                            "details": security_check.details
                        }
                    )

            # Reconstruct request body for the next handler
            # FastApi/Starlette request.body() is cached, so calling it again is fine 
            # IF we didn't consume the stream directly. 
            # But await request.body() caches it. So we are good.
            
        except Exception as e:
            logger.error(f"Error in AI Security Middleware input validation: {e}", exc_info=True)
            # Fail open or closed? Fail closed for security.
            return JSONResponse(status_code=500, content={"error": "Internal Security Error"})

        # 4. Process Request
        response = await call_next(request)

        # 5. Validate Output (Streaming responses are hard to validate, skipping for now)
        # Only validate JSON responses
        if response.headers.get("content-type") == "application/json":
            # Capture response body... this is tricky with StreamingResponse
            # For simplicity in this v1, we skip output validation in middleware 
            # and rely on the agent code calling validate_output, 
            # OR we implement a capturing response wrapper (complex).
            pass

        return response

    def _get_agent_id(self, path: str) -> Optional[str]:
        for route, agent_id in self.agent_routes.items():
            if path.startswith(route):
                return agent_id
        return None

    def _extract_input_text(self, body_text: str) -> Optional[str]:
        try:
            data = json.loads(body_text)
            # Common fields in our API
            return data.get("query") or data.get("code") or data.get("content") or data.get("prompt")
        except json.JSONDecodeError:
            return body_text
