
"""
Playbook Executor (experimental)
--------------------------------

Простой загрузчик YAML-плейбуков в структуры ScenarioPlan и
dry-run исполнитель, который печатает шаги и собирает базовый отчёт.

Цель:
- показать, как YAML/JSON-плейбуки могут быть связаны с Scenario Hub;
- не выполнять реальных действий (никаких вызовов DR-скриптов и т.п.).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict

import yaml

from src.ai.scenario_hub import (
    AutonomyLevel,
    ScenarioExecutionReport,
    ScenarioGoal,
    ScenarioPlan,
    ScenarioRiskLevel,
    ScenarioStep,
    TrustScore,
)
from src.ai.scenario_policy import StepDecision, assess_plan_execution


def _parse_risk(value: str) -> ScenarioRiskLevel:
    mapping = {
        "read_only": ScenarioRiskLevel.READ_ONLY,
        "non_prod_change": ScenarioRiskLevel.NON_PROD_CHANGE,
        "prod_low": ScenarioRiskLevel.PROD_LOW,
        "prod_high": ScenarioRiskLevel.PROD_HIGH,
    }
    return mapping.get(value, ScenarioRiskLevel.NON_PROD_CHANGE)


def _parse_autonomy(value: str) -> AutonomyLevel:
    mapping = {
        "A0_propose_only": AutonomyLevel.A0_PROPOSE_ONLY,
        "A1_safe_automation": AutonomyLevel.A1_SAFE_AUTOMATION,
        "A2_non_prod_changes": AutonomyLevel.A2_NON_PROD_CHANGES,
        "A3_restricted_prod": AutonomyLevel.A3_RESTRICTED_PROD,
    }
    return mapping.get(value, AutonomyLevel.A1_SAFE_AUTOMATION)


def load_playbook(path: str | Path) -> ScenarioPlan:
    """
    Загрузить YAML-плейбук с диска и сконструировать ScenarioPlan.

    Плейбук должен иметь структуру, подобную файлам в playbooks/*.yaml.
    """
    path = Path(path)
    data: Dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))

    goal_data = data["goal"]
    goal = ScenarioGoal(
        id=goal_data["id"],
        title=goal_data["title"],
        description=goal_data["description"],
        constraints=goal_data.get("constraints", {}),
        success_criteria=goal_data.get("success_criteria", []),
    )

    steps = []
    for step_data in data.get("steps", []):
        step = ScenarioStep(
            id=step_data["id"],
            title=step_data["title"],
            description=step_data["description"],
            risk_level=_parse_risk(step_data.get("risk_level", "non_prod_change")),
            autonomy_required=_parse_autonomy(
                step_data.get("autonomy_required", "A1_safe_automation")
            ),
            checks=step_data.get("checks", []),
            executor=step_data.get("executor", "agent:orchestrator"),
            metadata=step_data.get("metadata", {}),
        )
        steps.append(step)

    plan = ScenarioPlan(
        id=data["id"],
        goal=goal,
        steps=steps,
        required_autonomy=_parse_autonomy(
            data.get("required_autonomy", "A1_safe_automation")
        ),
        overall_risk=_parse_risk(data.get("overall_risk", "non_prod_change")),
        context=data.get("context", {}),
    )

    return plan


def dry_run_playbook(
    plan: ScenarioPlan,
    autonomy: AutonomyLevel | None = None,
) -> ScenarioExecutionReport:
    """
    Dry-run сценария:
    - не выполняет реальные действия;
    - собирает базовый trust-score и текстовый отчёт по шагам.
    """
    # Простейшая оценка доверия: read-only / non-prod считаем средним риском
    trust = TrustScore(
        score=0.6,
        level="medium",
        reasons=[
            "Dry-run отчёт без реальных метрик",
            "Плейбук загружен корректно и имеет последовательность шагов",
        ],
    )

    # Оценка шагов через Scenario Policy (если указан уровень автономности)
    timeline: list[str] = []
    decisions: dict[str, StepDecision] = {}
    if autonomy is not None:
        decisions = assess_plan_execution(plan, autonomy)

    for idx, step in enumerate(plan.steps, start=1):
        decision = decisions.get(step.id, StepDecision.NEEDS_APPROVAL)
        timeline.append(
            f"Шаг {idx}: {step.title} "
            f"(risk={step.risk_level.value}, autonomy={step.autonomy_required.value}, "
            f"decision={decision.value})"
        )

    summary = (
        f"Dry-run сценария '{plan.goal.title}': {len(plan.steps)} шаг(ов), "
        f"общий риск={plan.overall_risk.value}."
    )

    return ScenarioExecutionReport(
        scenario_id=plan.id,
        goal=plan.goal,
        trust_before=trust,
        trust_after=trust,
        summary=summary,
        timeline=timeline,
        artifacts={"plan": "inline"},
    )


def dry_run_playbook_to_dict(
    path: str | Path,
    autonomy: str | None = None,
) -> Dict[str, Any]:
    """
    Утилита для CLI/скриптов: dry-run плейбука и возврат отчёта как dict.
    """
    plan = load_playbook(path)

    autonomy_level: AutonomyLevel | None = None
    if autonomy is not None:
        # Преобразуем строку в AutonomyLevel, если она валидна
        mapping = {
            "A0_propose_only": AutonomyLevel.A0_PROPOSE_ONLY,
            "A1_safe_automation": AutonomyLevel.A1_SAFE_AUTOMATION,
            "A2_non_prod_changes": AutonomyLevel.A2_NON_PROD_CHANGES,
            "A3_restricted_prod": AutonomyLevel.A3_RESTRICTED_PROD,
        }
        autonomy_level = mapping.get(autonomy)

    report = dry_run_playbook(plan, autonomy=autonomy_level)
    return asdict(report)
