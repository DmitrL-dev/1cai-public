"""Модуль схем данных для аналитики и дашбордов."""
    
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

# --- Dashboard Schemas ---


class RevenueData(BaseModel):
    """Данные о выручке.

    Attributes:
        this_month: Выручка за текущий месяц.
        last_month: Выручка за прошлый месяц.
        change_percent: Процент изменения.
        trend: Тренд ("up" или "down").
    """
    this_month: float
    last_month: float
    change_percent: float
    trend: str  # "up" or "down"


class CustomersData(BaseModel):
    """Данные о клиентах.

    Attributes:
        total: Всего клиентов.
        new_this_month: Новых клиентов за месяц.
    """
    total: int
    new_this_month: int


class MetricData(BaseModel):
    """Общая модель метрики.

    Attributes:
        value: Значение метрики.
        change: Изменение.
        trend: Направление тренда.
        status: Статус (good/warning/critical).
    """
    value: float
    change: float
    trend: str
    status: str


class OwnerDashboardResponse(BaseModel):
    """Ответ для дашборда владельца.

    Attributes:
        revenue: Данные о выручке.
        customers: Данные о клиентах.
        growth_percent: Процент роста.
        system_status: Статус системы.
        recent_activities: Список недавних активностей.
    """
    revenue: RevenueData
    customers: CustomersData
    growth_percent: float
    system_status: str  # "healthy", "warning", "critical"
    recent_activities: List[Dict[str, Any]]


class ExecutiveDashboardResponse(BaseModel):
    """Ответ для исполнительного дашборда.

    Attributes:
        id: ID дашборда.
        health: Метрики здоровья.
        roi: Метрики ROI.
        users: Метрики пользователей.
        growth: Метрики роста.
        revenue_trend: Тренд выручки.
        alerts: Активные алерты.
        objectives: Стратегические цели.
        metrics: Прочие метрики.
    """
    id: str
    health: Dict[str, str]
    roi: MetricData
    users: MetricData
    growth: MetricData
    revenue_trend: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    objectives: List[Dict[str, Any]]
    metrics: Dict[str, Any]


class SprintProgress(BaseModel):
    """Прогресс спринта.

    Attributes:
        sprint_number: Номер спринта.
        tasks_done: Выполнено задач.
        tasks_total: Всего задач.
        progress: Прогресс (%).
        blockers: Количество блокеров.
        end_date: Дата окончания.
    """
    sprint_number: int
    tasks_done: int
    tasks_total: int
    progress: float
    blockers: int
    end_date: str


class PMDashboardResponse(BaseModel):
    """Ответ для дашборда PM.

    Attributes:
        id: ID дашборда.
        projects: Список проектов.
        projects_summary: Сводка по проектам.
        timeline: Таймлайн.
        team_workload: Загрузка команды.
        sprint_progress: Прогресс текущего спринта.
    """
    id: str
    projects: List[Dict[str, Any]]
    projects_summary: Dict[str, Any]
    timeline: List[Dict[str, Any]]
    team_workload: List[Dict[str, Any]]
    sprint_progress: SprintProgress


class DeveloperDashboardResponse(BaseModel):
    """Ответ для дашборда разработчика.

    Attributes:
        id: ID дашборда.
        name: Имя разработчика.
        assigned_tasks: Назначенные задачи.
        code_reviews: Код-ревью.
        build_status: Статус сборки.
        code_quality: Метрики качества кода.
        ai_suggestions: Предложения AI.
    """
    id: str
    name: str
    assigned_tasks: List[Dict[str, Any]]
    code_reviews: List[Dict[str, Any]]
    build_status: Dict[str, Any]
    code_quality: Dict[str, Any]
    ai_suggestions: Optional[List[Dict[str, Any]]] = None


# --- Analytics Report Schemas ---


class ReportRequest(BaseModel):
    """Запрос на генерацию отчета.

    Attributes:
        title: Заголовок отчета.
        period_days: Период в днях.
        components: Список компонентов для анализа.
    """
    title: str
    period_days: int = 7
    components: Optional[List[str]] = None


class ReportResponse(BaseModel):
    """Ответ с данными отчета.

    Attributes:
        id: ID отчета.
        title: Заголовок.
        period_start: Начало периода.
        period_end: Конец периода.
        metrics: Метрики отчета.
        insights: Инсайты от AI.
        recommendations: Рекомендации.
        timestamp: Время создания.
    """
    id: str
    title: str
    period_start: datetime
    period_end: datetime
    metrics: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    timestamp: datetime
