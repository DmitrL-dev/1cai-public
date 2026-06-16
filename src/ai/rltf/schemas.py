from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class Action(BaseModel):
    """Represents an action taken by the agent."""
    tool_name: str
    tool_input: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

class State(BaseModel):
    """Represents the state of the environment before an action."""
    context_summary: str
    open_files: List[str]
    last_error: Optional[str] = None

class Reward(BaseModel):
    """Represents the feedback signal received after an action."""
    source: str  # e.g., "compiler", "test_runner", "opa", "human"
    value: float # e.g., +1.0, -100.0
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class Trajectory(BaseModel):
    """Represents a complete learning episode: State -> Action -> Reward."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    state: State
    action: Action
    reward: Optional[Reward] = None
    next_state: Optional[State] = None
    
    def to_training_example(self) -> Dict[str, Any]:
        """Converts to a format suitable for Policy Gradient training."""
        return {
            "input": self.state.context_summary,
            "output": self.action.tool_name, # Simplified for now
            "reward": self.reward.value if self.reward else 0.0
        }
