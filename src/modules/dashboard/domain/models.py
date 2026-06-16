"""
Доменные модели дашбордов.

Pydantic модели для всех ответов API дашбордов.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ==================== COMMON MODELS ====================


class HealthScore(BaseModel):
    """Модель оценки здоровья системы."""

    status: str = Field(..., description="Health status: healthy, warning, critical")
    score: int = Field(..., ge=0, le=100, description="Health score 0-100")
    message: str = Field(..., description="Health status message")


class Metric(BaseModel):
    """Общая модель метрики."""

    value: float = Field(..., description="Metric value")
    previous_value: Optional[float] = Field(None, description="Previous period value")
    change: Optional[float] = Field(None, description="Percentage change")
    trend: Optional[str] = Field(None, description="Trend: up, down, stable")
    status: Optional[str] = Field(None, description="Status: good, warning, critical")
    format: str = Field(
        default="number", description="Format: number, currency, percentage")


# ==================== EXECUTIVE DASHBOARD ====================


class Alert(BaseModel):
    """Модель алерта (уведомления)."""

    id: str
    type: str = Field(..., description="Alert type: info, warning, error")
    title: str
    message: str
    timestamp: str
    read: bool = Field(default=False)


class Objective(BaseModel):
    """Модель бизнес-цели."""

    id: str
    title: str
    progress: int = Field(..., ge=0, le=100)
    status: str = Field(..., description="Status: on_track, behind, at_risk")
    target_date: str


class Initiative(BaseModel):
    """Модель ключевой инициативы."""

    id: str
    name: str
    status: str
    users: int = Field(default=0)
    eta: Optional[str] = None


class UsageStats(BaseModel):
    """Модель статистики использования."""

    api_calls: int
    ai_queries: int
    storage_gb: float
    uptime: float


class ExecutiveDashboard(BaseModel):
    """Модель ответа для исполнительного дашборда."""

    health: HealthScore
    roi: Metric
    users: Metric
    growth: Metric
    revenue_trend: List[Dict[str, Any]]
    alerts: List[Alert]
    objectives: List[Objective]
    top_initiatives: List[Initiative]
    usage_stats: UsageStats


# ==================== PM DASHBOARD ====================


class ProjectsSummary(BaseModel):
    """Сводка по проектам."""

    active: int
    completed: int
    paused: int
    at_risk: int


class ProjectTimeline(BaseModel):
    """Элемент таймлайна проекта."""

    project_id: str
    project_name: str
    progress: int = Field(..., ge=0, le=100)
    status: str
    current_phase: str


class TeamMemberWorkload(BaseModel):
    """Загрузка участника команды."""

    member_id: str
    member_name: str
    workload: int = Field(..., ge=0, le=100)
    tasks_count: int
    status: str


class SprintProgress(BaseModel):
    """Прогресс спринта."""

    sprint_number: int
    tasks_total: int
    tasks_done: int
    progress: int = Field(..., ge=0, le=100)
    blockers: int
    end_date: str


class Activity(BaseModel):
    """Модель активности."""

    id: str
    type: str
    actor: str
    description: str
    timestamp: str
    project_id: str


class PMDashboard(BaseModel):
    """Модель ответа для дашборда PM."""

    projects_summary: ProjectsSummary
    timeline: List[ProjectTimeline]
    team_workload: List[TeamMemberWorkload]
    sprint_progress: SprintProgress
    recent_activity: List[Activity]


# ==================== DEVELOPER DASHBOARD ====================


class Task(BaseModel):
    """Модель задачи."""

    id: str
    title: str
    description: str
    status: str
    priority: str
    assignee: str
    due_date: str
    project_id: str


class CodeReview(BaseModel):
    """Модель код-ревью."""

    id: str
    pr_number: int
    title: str
    author: str
    status: str
    comments_count: int
    created_at: str


class BuildStatus(BaseModel):
    """Статус сборки."""

    status: str
    last_build_at: str
    duration_seconds: int
    tests_passed: int
    tests_total: int


class CodeQuality(BaseModel):
    """Метрики качества кода."""

    coverage: int = Field(..., ge=0, le=100)
    complexity: int
    maintainability: int = Field(..., ge=0, le=100)
    security_score: int = Field(..., ge=0, le=100)
    issues: Dict[str, int]


class AISuggestion(BaseModel):
    """Предложение от AI."""

    id: str
    type: str
    title: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class DeveloperDashboard(BaseModel):
    """Модель ответа для дашборда разработчика."""

    assigned_tasks: List[Task]
    code_reviews: List[CodeReview]
    build_status: BuildStatus
    code_quality: CodeQuality
    ai_suggestions: List[AISuggestion]


# ==================== TEAM LEAD DASHBOARD ====================


class TeamMetrics(BaseModel):
    """Метрики команды."""

    velocity: int = Field(..., ge=0, le=100)
    code_quality: int = Field(..., ge=0, le=100)
    bug_rate: float
    deployment_frequency: int


class TeamPerformance(BaseModel):
    """Производительность участника команды."""

    name: str
    role: str
    workload: int = Field(..., ge=0, le=100)
    tasks_active: int
    tasks_completed_week: int
    status: str


class TrendData(BaseModel):
    """Точка данных тренда."""

    week: str
    quality: Optional[int] = None
    completed: Optional[int] = None


class TechnicalDebt(BaseModel):
    """Метрики технического долга."""

    total_debt_hours: int
    critical_items: int
    blocked_tasks: int
    trend: str


class TeamLeadDashboard(BaseModel):
    """Модель ответа для дашборда тимлида."""

    team_metrics: TeamMetrics
    code_quality_trends: List[TrendData]
    velocity_chart: List[TrendData]
    technical_debt: TechnicalDebt
    team_performance: List[TeamPerformance]


# ==================== BA DASHBOARD ====================


class RequirementsSummary(BaseModel):
    """Сводка по требованиям."""

    total: int
    approved: int
    pending: int
    rejected: int


class Requirement(BaseModel):
    """Модель требования."""

    id: str
    title: str
    status: str
    priority: str
    stakeholder: str
    created_at: str


class TraceabilityMatrix(BaseModel):
    """Элемент матрицы трассируемости."""

    requirement_id: str
    requirement_title: str
    linked_tasks: int
    test_coverage: int = Field(..., ge=0, le=100)
    status: str


class GapAnalysis(BaseModel):
    """Элемент gap-анализа."""

    area: str
    current_state: str
    desired_state: str
    gap_severity: str
    recommendations: List[str]


class ProcessDiagram(BaseModel):
    """Модель диаграммы процесса."""

    id: str
    name: str
    type: str
    url: str
    last_updated: str


class BADashboard(BaseModel):
    """Модель ответа для дашборда бизнес-аналитика."""

    requirements_summary: RequirementsSummary
    recent_requirements: List[Requirement]
    traceability_matrix: List[TraceabilityMatrix]
    gap_analysis: List[GapAnalysis]
    process_diagrams: List[ProcessDiagram]


# ==================== OWNER DASHBOARD ====================


class BusinessMetric(BaseModel):
    """Бизнес-метрика для владельца."""

    label: str
    value: str
    trend: str
    explanation: str


class OwnerDashboard(BaseModel):
    """Модель ответа для дашборда владельца (упрощенная)."""

    business_health: str
    key_metrics: List[BusinessMetric]
    summary: str
    recommendations: List[str]
