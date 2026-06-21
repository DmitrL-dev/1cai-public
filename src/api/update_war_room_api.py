"""Update War Room API for 1C update and upgrade planning."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.api._rentgen_store import store_or_none
from src.services.rentgen.update_war_room import build_update_war_room

router = APIRouter(prefix="/api/v1/update-war-room", tags=["Update War Room"])


class UpdateWarRoomRequest(BaseModel):
    release_name: str | None = Field(default=None, max_length=160)
    config_path: str | None = Field(default=None, max_length=2000)
    target_platform_version: str | None = Field(default=None, max_length=80)
    changed_modules: list[str] = Field(default_factory=list, max_length=200)
    diff: str | None = None
    include_security: bool = False


@router.post("/plan")
def plan(req: UpdateWarRoomRequest) -> dict[str, Any]:
    """Build an update/upgrade war-room plan with platform, release and extension gates."""

    return build_update_war_room(
        store_or_none(),
        config_path=req.config_path,
        target_platform_version=req.target_platform_version,
        release_name=req.release_name,
        changed_modules=req.changed_modules,
        diff=req.diff,
        include_security=req.include_security,
    )


@router.get("/health")
def health() -> dict[str, Any]:
    report = build_update_war_room(store_or_none())
    return {
        "status": report["decision"]["status"],
        "score": report["decision"]["score"],
        "checks": len(report["checks"]),
    }
