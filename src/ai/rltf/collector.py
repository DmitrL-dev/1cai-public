import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Set

try:
    from src.infrastructure.event_bus import Event, EventHandler, EventType
except ImportError:
    EventHandler = None  # type: ignore
    Event = None  # type: ignore
    EventType = None  # type: ignore
from src.ai.rltf.schemas import Action, Reward, State, Trajectory

logger = logging.getLogger(__name__)


class FeedbackCollector(EventHandler):
    """
    RLTF Feedback Collector.

    Subscribes to system events and aggregates them into 'Trajectories'
    (State -> Action -> Reward) for future reinforcement learning.
    """

    def __init__(self, storage_path: str = "data/rltf/trajectories.jsonl"):
        # WARNING: JSONL storage is for Development/MVP only.
        # For Production (Phase 7), this must be replaced with:
        # 1. Log Rotation (e.g., 100MB chunks)
        # 2. Compression (Gzip)
        # 3. VectorDB (Qdrant) for high-value examples
        self.storage_path = storage_path
        self._ensure_storage()
        logger.info(f"FeedbackCollector initialized. Storage: {self.storage_path}")

    def _ensure_storage(self):
        """Ensures the storage directory exists."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

    @property
    def event_types(self) -> Set[EventType]:
        """Events that trigger feedback collection."""
        return {
            EventType.STRATEGY_PERFORMANCE_RECORDED,
            EventType.AI_FEEDBACK_RECEIVED,
            EventType.CODE_TESTED,
            EventType.CODE_ERROR_DETECTED,
        }

    async def handle(self, event: Event) -> None:
        """Processes events and saves trajectories."""
        try:
            if event.type == EventType.STRATEGY_PERFORMANCE_RECORDED:
                await self._handle_performance_record(event)
            elif event.type == EventType.AI_FEEDBACK_RECEIVED:
                await self._handle_explicit_feedback(event)
        except Exception as e:
            logger.error(f"Failed to process event {event.id}: {e}", exc_info=True)

    async def _handle_performance_record(self, event: Event):
        """Converts a performance record into a Trajectory."""
        payload = event.payload

        # 1. Reconstruct State (Simplified)
        # In a real system, we would fetch the actual context from GAM using correlation_id
        state = State(
            context_summary=f"Query Type: {payload.get('query_type')}",
            open_files=[],
            last_error=None,  # Error details are absent from this event payload.
        )

        # 2. Reconstruct Action
        action = Action(
            tool_name=payload.get("service", "unknown"),
            tool_input={},  # We don't have the input in this event, need to enrich later
            timestamp=datetime.now(),
        )

        # 3. Calculate Reward
        # Simple reward function: Success = +1.0, Failure = -1.0
        reward_value = 1.0 if payload.get("success") else -1.0
        reward = Reward(
            source="system_telemetry",
            value=reward_value,
            message="Auto-generated from performance record",
        )

        # 4. Create Trajectory
        trajectory = Trajectory(
            session_id=event.correlation_id or "unknown",
            state=state,
            action=action,
            reward=reward,
        )

        # 5. Save
        self._save_trajectory(trajectory)

    async def _handle_explicit_feedback(self, event: Event):
        """Handles explicit human/system feedback (e.g. from OPA)."""
        payload = event.payload

        # Create a standalone reward record
        # In the future, this should update the *previous* trajectory using session_id
        reward = Reward(
            source=payload.get("source", "unknown"),
            value=float(payload.get("value", 0.0)),
            message=payload.get("message", ""),
            timestamp=datetime.now(),
        )

        # For now, we save it as a "Reward Event" trajectory
        # This allows offline RL to stitch State-Action-Reward later
        trajectory = Trajectory(
            session_id=event.correlation_id or "unknown",
            state=State(context_summary="FEEDBACK_ONLY", open_files=[]),
            action=Action(tool_name="feedback_received", tool_input={}),
            reward=reward,
        )

        self._save_trajectory(trajectory)

    def _save_trajectory(self, trajectory: Trajectory):
        """Appends the trajectory to the JSONL file."""
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(trajectory.json() + "\n")
            logger.debug(f"Saved trajectory {trajectory.id}")
        except Exception as e:
            logger.error(f"Failed to save trajectory: {e}")
