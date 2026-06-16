
"""Sandbox manager with basic result storage."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

RESULTS_DIR = Path(__file__).resolve().parent / "runs"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _results_path(run_id: str) -> Path:
    safe_name = f"{run_id}.json"
    return RESULTS_DIR / safe_name


class RunRequest(BaseModel):
    targets: list[str] = Field(default_factory=list)
    instruction: Optional[str] = None
    profile: Optional[str] = None


class RunResultPayload(BaseModel):
    run_id: Optional[str] = None
    generated_at: Optional[str] = None
    profile: Optional[str] = None
    results: list[dict] = Field(default_factory=list)


@dataclass
class RunState:
    run_id: str
    status: str = "pending"
    message: Optional[str] = None
    targets: list[str] = field(default_factory=list)
    instruction: Optional[str] = None
    profile: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    results_path: Optional[str] = None


class SandboxManager:
    """In-memory sandbox manager with filesystem persistence for results."""

    def __init__(self) -> None:
        self._store: Dict[str, RunState] = {}

    def submit(self, run_id: str, request: RunRequest) -> RunState:
        state = RunState(
            run_id=run_id,
            status="queued",
            message="Sandbox integration TBD",
            targets=request.targets,
            instruction=request.instruction,
            profile=request.profile,
        )
        self._store[run_id] = state
        return state

    def complete(self, run_id: str, payload: RunResultPayload) -> RunState:
        state = self._store.get(run_id)
        if state is None:
            state = RunState(
                run_id=run_id,
                status="completed",
                message="Completed without prior registration.",
                targets=[],
                instruction=None,
                profile=payload.profile,
            )
        state.status = "completed"
        state.completed_at = datetime.now(timezone.utc)
        if payload.profile and not state.profile:
            state.profile = payload.profile

        path = _results_path(run_id)
        path.write_text(payload.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
        state.results_path = str(path)
        self._store[run_id] = state
        return state

    def get(self, run_id: str) -> Optional[RunState]:
        return self._store.get(run_id)

    def get_results(self, run_id: str) -> dict:
        path = _results_path(run_id)
        if not path.exists():
            raise FileNotFoundError
        return json.loads(path.read_text(encoding="utf-8"))


manager = SandboxManager()
app = FastAPI(title="Security Sandbox Manager (stub)")


@app.post("/runs/{run_id}")
def submit_run(run_id: str, request: RunRequest) -> RunState:  # pragma: no cover - FastAPI path stub
    return manager.submit(run_id, request)


@app.post("/runs/{run_id}/complete")
def complete_run(run_id: str, payload: RunResultPayload) -> RunState:  # pragma: no cover - FastAPI path stub
    return manager.complete(run_id, payload)


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> RunState:  # pragma: no cover - FastAPI path stub
    state = manager.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return state


@app.get("/runs/{run_id}/results")
def get_run_results(run_id: str) -> dict:  # pragma: no cover - FastAPI path stub
    try:
        return manager.get_results(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="results not found") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9100)
