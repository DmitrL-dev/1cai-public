
"""
Tests for playbook_executor (experimental).
"""

from pathlib import Path

from src.ai.playbook_executor import (
    dry_run_playbook,
    dry_run_playbook_to_dict,
    load_playbook,
)
from src.ai.scenario_hub import AutonomyLevel, ScenarioPlan


def test_load_playbook_ba_dev_qa(tmp_path: Path) -> None:
    """YAML-плейбук BA→Dev→QA должен загружаться в ScenarioPlan."""
    # Используем реальный файл из playbooks
    playbook_path = Path("playbooks/ba_dev_qa_example.yaml")
    plan = load_playbook(playbook_path)

    assert isinstance(plan, ScenarioPlan)
    assert plan.goal.title.startswith("BA → Dev → QA")
    assert len(plan.steps) == 3


def test_dry_run_playbook_returns_report_dict() -> None:
    """dry_run_playbook_to_dict должен возвращать dict с ключевыми полями."""
    playbook_path = Path("playbooks/dr_vault_example.yaml")
    report_dict = dry_run_playbook_to_dict(
        playbook_path, autonomy="A2_non_prod_changes"
    )

    assert isinstance(report_dict, dict)
    assert report_dict.get("scenario_id") == "plan-dr-vault"
    assert "summary" in report_dict
    assert "timeline" in report_dict
    # Втаймлайне должны быть решения по шагам
    assert any("decision=" in entry for entry in report_dict["timeline"])


def test_dry_run_playbook_with_autonomy_level() -> None:
    """dry_run_playbook напрямую с уровнем автономности должен отрабатывать без ошибок."""
    playbook_path = Path("playbooks/ba_dev_qa_example.yaml")
    plan = load_playbook(playbook_path)

    report = dry_run_playbook(plan, autonomy=AutonomyLevel.A2_NON_PROD_CHANGES)
    assert report.summary.startswith("Dry-run сценария")
    assert any("decision=" in entry for entry in report.timeline)


def test_security_audit_playbook_loads() -> None:
    """Плейбук security-audit должен корректно загружаться и иметь read_only риск."""
    playbook_path = Path("playbooks/security_audit_example.yaml")
    plan = load_playbook(playbook_path)

    assert isinstance(plan, ScenarioPlan)
    assert plan.id == "plan-security-audit"
    assert plan.overall_risk.value == "read_only"


def test_code_review_playbook_loads() -> None:
    """Плейбук code review для PR должен загружаться и быть read_only."""
    playbook_path = Path("playbooks/code_review_pr_example.yaml")
    plan = load_playbook(playbook_path)

    assert isinstance(plan, ScenarioPlan)
    assert plan.id == "plan-code-review-EXTERNAL_PR"
    assert plan.overall_risk.value == "read_only"
