"""EDT-MCP bridge API for planning native EDT tool usage from 1cAI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.services.edt_mcp_bridge import (
    DEFAULT_BASE_URL,
    build_connection_config,
    call_live_edt_mcp_tool,
    check_edt_mcp_status,
    list_edt_mcp_toolsets,
    list_live_edt_mcp_tools,
    plan_edt_mcp_workflow,
)

router = APIRouter(prefix="/api/v1/edt-mcp", tags=["EDT MCP Bridge"])


class PlanRequest(BaseModel):
    task: str = Field(..., min_length=1, max_length=2000)
    intent: str | None = Field(default=None, max_length=500)


class LiveCallRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)
    base_url: str = Field(default=DEFAULT_BASE_URL, min_length=1, max_length=300)
    confirm: bool = False
    actor: str | None = Field(default=None, max_length=160)
    approval_reason: str | None = Field(default=None, max_length=1000)
    approval_ticket: str | None = Field(default=None, max_length=160)
    approval_id: str | None = Field(default=None, max_length=80)
    timeout_s: float = Field(default=30.0, ge=1.0, le=300.0)


async def _authenticated_actor(request: Request) -> str | None:
    try:
        from src.security import get_current_user

        user = await get_current_user(request)
    except Exception:
        return None
    return getattr(user, "username", None) or getattr(user, "user_id", None)


@router.get("/toolsets")
def toolsets() -> dict[str, Any]:
    """Return the curated EDT-MCP tool catalog and integration notes."""

    return list_edt_mcp_toolsets()


@router.post("/plan")
def plan(req: PlanRequest) -> dict[str, Any]:
    """Map a user task to EDT-MCP toolsets and companion 1cAI tools."""

    return plan_edt_mcp_workflow(req.task, intent=req.intent)


@router.get("/connection-config")
def connection_config(
    base_url: str = Query(DEFAULT_BASE_URL, min_length=1, max_length=300)
) -> dict[str, Any]:
    """Return MCP client snippets for connecting to a local EDT-MCP server."""

    try:
        return build_connection_config(base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
async def status(
    base_url: str = Query(DEFAULT_BASE_URL, min_length=1, max_length=300),
    timeout_s: float = Query(5.0, ge=1.0, le=30.0),
    x_edt_mcp_token: str | None = Header(default=None, alias="X-EDT-MCP-Token"),
) -> dict[str, Any]:
    """Probe a live local EDT-MCP server."""

    return await check_edt_mcp_status(
        base_url,
        auth_token=x_edt_mcp_token,
        timeout_s=timeout_s,
    )


@router.get("/live-tools")
async def live_tools(
    base_url: str = Query(DEFAULT_BASE_URL, min_length=1, max_length=300),
    timeout_s: float = Query(10.0, ge=1.0, le=60.0),
    x_edt_mcp_token: str | None = Header(default=None, alias="X-EDT-MCP-Token"),
) -> dict[str, Any]:
    """Return live EDT-MCP tools/list enriched with 1cAI risk classifications."""

    return await list_live_edt_mcp_tools(
        base_url,
        auth_token=x_edt_mcp_token,
        timeout_s=timeout_s,
    )


@router.post("/call")
async def call_tool(
    request: Request,
    req: LiveCallRequest,
    x_edt_mcp_token: str | None = Header(default=None, alias="X-EDT-MCP-Token"),
    x_1cai_actor: str | None = Header(default=None, alias="X-1CAI-Actor"),
) -> dict[str, Any]:
    """Call a live EDT-MCP tool through the bridge safety gate."""

    actor = await _authenticated_actor(request) or x_1cai_actor or req.actor
    return await call_live_edt_mcp_tool(
        req.tool_name,
        req.arguments,
        base_url=req.base_url,
        auth_token=x_edt_mcp_token,
        confirm=req.confirm,
        actor=actor,
        approval_reason=req.approval_reason,
        approval_ticket=req.approval_ticket,
        approval_id=req.approval_id,
        timeout_s=req.timeout_s,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "catalog": True, "default_base_url": DEFAULT_BASE_URL}
