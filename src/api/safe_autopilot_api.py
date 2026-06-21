"""Safe Autopilot API for read-only 1C change planning."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.middleware.jwt_user_context import principal_actor, require_auth
from src.services.edt_mcp_bridge import classify_edt_mcp_tool
from src.services.audit_log import record_event
from src.services.rentgen.approval_workflow import create_approval_record
from src.services.rentgen.safe_autopilot import build_safe_autopilot

router = APIRouter(prefix="/api/v1/safe-autopilot", tags=["Safe Autopilot"])


class SafeAutopilotRequest(BaseModel):
    goal: str = Field(default="Plan a safe 1C change", max_length=1000)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    diff: str | None = None
    allow_write: bool = False
    risk_threshold: int = Field(default=70, ge=0, le=100)
    impact_threshold: int = Field(default=300, ge=0, le=10000)


class SafeAutopilotApprovalRequest(SafeAutopilotRequest):
    tool_name: str = Field(default="write_module_source", min_length=1, max_length=200)
    approval_reason: str | None = Field(default=None, max_length=1000)
    approval_ticket: str | None = Field(default=None, max_length=160)
    expires_in_hours: float = Field(default=24, ge=1, le=24 * 30)


def _plan_id(req: SafeAutopilotApprovalRequest, report: dict[str, Any]) -> str:
    payload = {
        "goal": req.goal,
        "changed_modules": req.changed_modules,
        "diff": req.diff or "",
        "summary": report.get("summary") or {},
        "diff_candidates": [
            item.get("id")
            for item in (report.get("diff_proposal") or {}).get("candidates", [])
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return "sap_" + hashlib.sha1(encoded).hexdigest()[:16]


def _approval_constraints(req: SafeAutopilotApprovalRequest, report: dict[str, Any]) -> dict[str, Any]:
    candidates = (report.get("diff_proposal") or {}).get("candidates", [])
    candidate_targets = [
        str(item.get("target") or "").strip()
        for item in candidates
        if str(item.get("target") or "").strip()
    ]
    module_paths = [path.strip() for path in req.changed_modules if path.strip()]
    target = (candidate_targets or module_paths or [""])[0]
    constraints: dict[str, Any] = {
        "source": "safe-autopilot",
        "goal": req.goal,
        "diffCandidates": len(candidates),
    }
    if target:
        constraints["modulePath"] = target
    if module_paths:
        constraints["allowedModulePaths"] = module_paths[:20]
    return constraints


def _approval_reason(req: SafeAutopilotApprovalRequest, report: dict[str, Any]) -> str:
    if req.approval_reason and req.approval_reason.strip():
        return req.approval_reason.strip()
    summary = report.get("summary") or {}
    decision = report.get("decision") or {}
    return (
        f"Safe Autopilot approval for: {req.goal}. "
        f"Decision: {decision.get('status')} / {decision.get('score')}; "
        f"diff candidates: {summary.get('diff_candidates', 0)}; "
        f"tests: {summary.get('tests', 0)}; "
        "direct apply remains blocked until this approval is reviewed."
    )


def _actor(principal: Any) -> str:
    actor = principal_actor(principal)
    if not actor:
        raise HTTPException(401, "Not authenticated")
    return actor


@router.post("/plan")
def plan(req: SafeAutopilotRequest) -> dict[str, Any]:
    """Build a safe Ask/Plan/Impact/Diff/Test/Evidence route."""

    return build_safe_autopilot(
        store_or_none(),
        goal=req.goal,
        changed_modules=req.changed_modules,
        diff=req.diff,
        allow_write=req.allow_write,
        risk_threshold=req.risk_threshold,
        impact_threshold=req.impact_threshold,
    )


@router.post("/approval-request")
def request_approval(
    req: SafeAutopilotApprovalRequest,
    principal: Any = Depends(require_auth),
) -> dict[str, Any]:
    """Create an approval record from a Safe Autopilot plan and handoff."""

    report = build_safe_autopilot(
        store_or_none(),
        goal=req.goal,
        changed_modules=req.changed_modules,
        diff=req.diff,
        allow_write=req.allow_write,
        risk_threshold=req.risk_threshold,
        impact_threshold=req.impact_threshold,
    )
    handoff = report.get("approval_handoff") or {}
    if not handoff.get("can_request_approval"):
        raise HTTPException(400, "Safe Autopilot plan is not ready for approval request")

    actor = _actor(principal)
    classification = classify_edt_mcp_tool(req.tool_name)
    plan_id = _plan_id(req, report)
    constraints = _approval_constraints(req, report)
    record = create_approval_record(
        tool_name=req.tool_name,
        actor=actor,
        approval_reason=_approval_reason(req, report),
        risk=str(classification.get("risk") or "unknown"),
        approval_ticket=req.approval_ticket,
        requested_by=actor,
        linked_record_type="safe_autopilot_plan",
        linked_record_id=plan_id,
        argument_constraints=constraints,
        expires_in_hours=req.expires_in_hours,
    )
    record_event(
        action="safe_autopilot.approval.requested",
        actor=actor,
        target=record["id"],
        category="approval",
        metadata={
            "plan_id": plan_id,
            "tool_name": req.tool_name,
            "risk": record.get("risk"),
            "constraints": constraints,
        },
    )
    return {
        "record": record,
        "classification": classification,
        "plan_id": plan_id,
        "safe_autopilot": report,
        "handoff": handoff,
    }


@router.get("/health")
def health() -> dict[str, Any]:
    report = build_safe_autopilot(store_or_none())
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "mode": report["safety_policy"]["mode"],
    }
