"""
Scenario Hub (experimental)
---------------------------

Central definitions for Scenario Planning and Execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ScenarioRiskLevel(str, Enum):
    """Risk levels for scenario steps."""

    READ_ONLY = "read_only"
    NON_PROD_CHANGE = "non_prod_change"
    PROD_LOW = "prod_low"
    PROD_HIGH = "prod_high"


class AutonomyLevel(str, Enum):
    """Autonomy levels for execution."""

    A0_PROPOSE_ONLY = "A0_propose_only"
    A1_SAFE_AUTOMATION = "A1_safe_automation"
    A2_NON_PROD_CHANGES = "A2_non_prod_changes"
    A3_RESTRICTED_PROD = "A3_restricted_prod"


@dataclass
class ScenarioGoal:
    """Goal definition for a scenario."""

    id: str
    title: str
    description: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    success_criteria: List[str] = field(default_factory=list)


@dataclass
class ScenarioStep:
    """A single step in a scenario."""

    id: str
    title: str
    description: str
    risk_level: ScenarioRiskLevel
    autonomy_required: AutonomyLevel
    checks: List[str] = field(default_factory=list)
    executor: str = "agent:default"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioPlan:
    """Complete plan for a scenario."""

    id: str
    goal: ScenarioGoal
    steps: List[ScenarioStep]
    required_autonomy: AutonomyLevel
    overall_risk: ScenarioRiskLevel
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustScore:
    """Trust score for execution."""

    score: float
    level: str
    reasons: List[str] = field(default_factory=list)


@dataclass
class ScenarioExecutionReport:
    """Report of scenario execution."""

    scenario_id: str
    goal: ScenarioGoal
    trust_before: TrustScore
    trust_after: TrustScore
    summary: str
    timeline: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
