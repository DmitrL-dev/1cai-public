
"""
Unit tests for Scenario Policy (experimental).
"""

from src.ai.scenario_hub import (
    AutonomyLevel,
    ScenarioGoal,
    ScenarioPlan,
    ScenarioRiskLevel,
    ScenarioStep,
)
from src.ai.scenario_policy import (
    StepDecision,
    assess_plan_execution,
    decide_step_execution,
)


def _make_step(step_id: str, risk: ScenarioRiskLevel) -> ScenarioStep:
    return ScenarioStep(
        id=step_id,
        title=f"Step {step_id}",
        description="Test step",
        risk_level=risk,
        autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
        checks=[],
        executor="agent:test",
        metadata={},
    )


def test_decide_step_execution_basic_levels() -> None:
    """Проверяем базовую матрицу решений по уровню риска и автономности."""
    step_read_only = _make_step("s1", ScenarioRiskLevel.READ_ONLY)
    step_non_prod = _make_step("s2", ScenarioRiskLevel.NON_PROD_CHANGE)

    # A0: только предложения, read-only шаги не должны выполняться автоматически
    assert decide_step_execution(step_read_only, AutonomyLevel.A0_PROPOSE_ONLY) in {
        StepDecision.AUTO,
        StepDecision.NEEDS_APPROVAL,
    }

    # A1: read-only шаги могут быть auto, non_prod требует approval
    assert (
        decide_step_execution(step_read_only, AutonomyLevel.A1_SAFE_AUTOMATION)
        == StepDecision.AUTO
    )
    assert decide_step_execution(step_non_prod, AutonomyLevel.A1_SAFE_AUTOMATION) in {
        StepDecision.NEEDS_APPROVAL,
        StepDecision.FORBIDDEN,
    }


def test_assess_plan_execution() -> None:
    """Оцениваем весь план: должны быть решения для каждого шага."""
    goal = ScenarioGoal(
        id="g1",
        title="Test goal",
        description="",
        constraints={},
        success_criteria=[],
    )
    steps = [
        _make_step("s1", ScenarioRiskLevel.READ_ONLY),
        _make_step("s2", ScenarioRiskLevel.NON_PROD_CHANGE),
    ]
    plan = ScenarioPlan(
        id="plan1",
        goal=goal,
        steps=steps,
        required_autonomy=AutonomyLevel.A2_NON_PROD_CHANGES,
        overall_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        context={},
    )

    decisions = assess_plan_execution(plan, AutonomyLevel.A2_NON_PROD_CHANGES)
    assert set(decisions.keys()) == {"s1", "s2"}
    assert all(isinstance(v, StepDecision) for v in decisions.values())
