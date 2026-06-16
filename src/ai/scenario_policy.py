"""
Scenario Policy (experimental)
------------------------------

Политика выполнения сценариев в зависимости от уровня автономности
и риск-профиля шагов.

Цель:
- дать Orchestrator/CLI простой механизм оценки, какие шаги можно
  выполнять автоматически, какие требуют approval, а какие запрещены
  при текущем уровне автономности.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

from src.ai.scenario_hub import (
    AutonomyLevel,
    ScenarioPlan,
    ScenarioRiskLevel,
    ScenarioStep,
)


class StepDecision(str, Enum):
    """Решение по шагу сценария с точки зрения политики."""

    AUTO = "auto"  # можно выполнять автоматически
    NEEDS_APPROVAL = "needs_approval"  # требуется явное подтверждение человека
    FORBIDDEN = "forbidden"  # запрещено в текущем режиме


@dataclass
class AutonomyPolicy:
    """
    Простая политика: на каком уровне автономности какие уровни риска
    можно выполнять автоматически / под approval / запрещать.
    """

    # Максимальный риск, который можно выполнять автоматически
    max_auto_risk: ScenarioRiskLevel
    # Максимальный риск, который вообще допускается (выше — запрещено)
    max_allowed_risk: ScenarioRiskLevel


# Базовая политика по умолчанию для каждого уровня автономности
DEFAULT_POLICIES: Dict[AutonomyLevel, AutonomyPolicy] = {
    AutonomyLevel.A0_PROPOSE_ONLY: AutonomyPolicy(
        max_auto_risk=ScenarioRiskLevel.READ_ONLY,
        max_allowed_risk=ScenarioRiskLevel.READ_ONLY,
    ),
    AutonomyLevel.A1_SAFE_AUTOMATION: AutonomyPolicy(
        max_auto_risk=ScenarioRiskLevel.READ_ONLY,
        max_allowed_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
    ),
    AutonomyLevel.A2_NON_PROD_CHANGES: AutonomyPolicy(
        max_auto_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        max_allowed_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
    ),
    AutonomyLevel.A3_RESTRICTED_PROD: AutonomyPolicy(
        max_auto_risk=ScenarioRiskLevel.PROD_LOW,
        max_allowed_risk=ScenarioRiskLevel.PROD_HIGH,
    ),
}


def compare_risk(a: ScenarioRiskLevel, b: ScenarioRiskLevel) -> int:
    """
    Сравнить два уровня риска.

    Возвращает:
    -1 если a < b, 0 если a == b, 1 если a > b.
    """
    order = [
        ScenarioRiskLevel.READ_ONLY,
        ScenarioRiskLevel.NON_PROD_CHANGE,
        ScenarioRiskLevel.PROD_LOW,
        ScenarioRiskLevel.PROD_HIGH,
    ]
    ia = order.index(a)
    ib = order.index(b)
    return (ia > ib) - (ia < ib)


def decide_step_execution(
    step: ScenarioStep,
    autonomy: AutonomyLevel,
    policies: Dict[AutonomyLevel, AutonomyPolicy] | None = None,
) -> StepDecision:
    """
    Определить, можно ли выполнять шаг автоматически, требуется ли approval
    или шаг запрещён при текущем уровне автономности.
    """
    if policies is None:
        policies = DEFAULT_POLICIES

    policy = policies.get(autonomy)
    if policy is None:
        # если уровень автономности не знаком — ничего не выполняем автоматически
        return StepDecision.NEEDS_APPROVAL

    if compare_risk(step.risk_level, policy.max_allowed_risk) > 0:
        return StepDecision.FORBIDDEN
    if compare_risk(step.risk_level, policy.max_auto_risk) <= 0:
        return StepDecision.AUTO
    return StepDecision.NEEDS_APPROVAL


def assess_plan_execution(
    plan: ScenarioPlan,
    autonomy: AutonomyLevel,
    policies: Dict[AutonomyLevel, AutonomyPolicy] | None = None,
) -> Dict[str, StepDecision]:
    """
    Оценить весь план: для каждого шага выдать StepDecision.

    Возвращает dict step_id -> StepDecision.
    """
    decisions: Dict[str, StepDecision] = {}
    for step in plan.steps:
        decisions[step.id] = decide_step_execution(step, autonomy, policies)
    return decisions
