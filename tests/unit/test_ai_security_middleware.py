import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, Response
from src.middleware.ai_security_middleware import AISecurityMiddleware

@pytest.mark.asyncio
async def test_dispatch_extracts_user_id():
    # Setup
    app = MagicMock()
    middleware = AISecurityMiddleware(app)
    
    # Mock Security Layer
    middleware.security_layer = MagicMock()
    middleware.security_layer.validate_input.return_value = MagicMock(allowed=True)
    
    # Mock Request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/assistants/developer"
    request.body = AsyncMock(return_value=b'{"query": "hello"}')
    
    # Mock Request State
    request.state = MagicMock()
    request.state.user_id = "test_user_123"
    
    # Mock call_next
    call_next = AsyncMock(return_value=Response(content="ok", media_type="application/json"))
    
    # Execute
    await middleware.dispatch(request, call_next)
    
    # Verify
    middleware.security_layer.validate_input.assert_called_once()
    call_args = middleware.security_layer.validate_input.call_args
    assert call_args.kwargs["context"]["user_id"] == "test_user_123"

@pytest.mark.asyncio
async def test_dispatch_fallback_anonymous():
    # Setup
    app = MagicMock()
    middleware = AISecurityMiddleware(app)
    
    # Mock Security Layer
    middleware.security_layer = MagicMock()
    middleware.security_layer.validate_input.return_value = MagicMock(allowed=True)
    
    # Mock Request
    request = MagicMock(spec=Request)
    request.url.path = "/api/v1/assistants/developer"
    request.body = AsyncMock(return_value=b'{"query": "hello"}')
    
    # Mock Request State (empty)
    request.state = MagicMock()
    del request.state.user_id # Ensure no user_id attribute
    
    # Mock call_next
    call_next = AsyncMock(return_value=Response(content="ok", media_type="application/json"))
    
    # Execute
    await middleware.dispatch(request, call_next)
    
    # Verify
    middleware.security_layer.validate_input.assert_called_once()
    call_args = middleware.security_layer.validate_input.call_args
    assert call_args.kwargs["context"]["user_id"] == "anonymous"
