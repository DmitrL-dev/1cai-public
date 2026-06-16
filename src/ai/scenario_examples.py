
"""
Scenario Examples (experimental)
--------------------------------

Готовые примеры ScenarioPlan, показывающие, как использовать
типы из src/ai/scenario_hub.py для типовых сценариев:
- BA → Dev → QA поток для одной фичи;
- DR rehearsal для сервиса (например, vault).

Эти функции не подключены к API и нужны как reference/пример
для дальнейшей интеграции.
"""

from __future__ import annotations

from typing import List

from src.ai.graph_refs_builder import build_refs_for_feature, build_refs_for_service
from src.ai.scenario_hub import (
    AutonomyLevel,
    ScenarioExecutionReport,
    ScenarioGoal,
    ScenarioPlan,
    ScenarioRiskLevel,
    ScenarioStep,
    TrustScore,
)


def example_ba_dev_qa_scenario(feature_id: str) -> ScenarioPlan:
    """
    Пример сценария BA → Dev → QA для одной фичи.

    feature_id используется для привязки к артефактам (Jira/Confluence и т.д.).
    """

    goal = ScenarioGoal(
        id=f"ba-dev-qa-{feature_id}",
        title=f"BA → Dev → QA для фичи {feature_id}",
        description="Согласовать требования, реализовать фичу и покрыть её тестами.",
        constraints={"environment": "staging"},
        success_criteria=[
            "BA-спецификация согласована",
            "Изменения в конфигурации применены на staging",
            "Автотесты по фиче зелёные",
        ],
    )

    steps: List[ScenarioStep] = [
        ScenarioStep(
            id="ba-spec",
            title="Уточнение и фиксация требований BA",
            description="BA-агент готовит и согласует спецификацию по фиче.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "BA-спецификация сохранена в Wiki/Docflow",
                "Есть явное согласие ответственного BA/PO",
            ],
            executor="agent:BA",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    doc_paths=["docs/06-features/BUSINESS_ANALYST_GUIDE.md"],
                ),
            },
        ),
        ScenarioStep(
            id="dev-impl",
            title="Реализация изменений разработчиком",
            description="Dev-агент предлагает изменения в конфигурации/коде.",
            risk_level=ScenarioRiskLevel.NON_PROD_CHANGE,
            autonomy_required=AutonomyLevel.A2_NON_PROD_CHANGES,
            checks=[
                "Все изменения применены только на test/staging",
                "Проверка статических анализаторов зелёная",
            ],
            executor="agent:Dev",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    code_paths=[
                        "src/ai/role_based_router.py",
                        "src/ai/agents/developer_ai_secure.py",
                    ],
                ),
            },
        ),
        ScenarioStep(
            id="qa-coverage",
            title="Покрытие тестами и прогон E2E",
            description="QA-агент генерирует/обновляет тесты и запускает E2E.",
            risk_level=ScenarioRiskLevel.NON_PROD_CHANGE,
            autonomy_required=AutonomyLevel.A2_NON_PROD_CHANGES,
            checks=[
                "Все релевантные тесты по фиче зелёные",
                "E2E по критическим путям (API → AI → Response) прошли",
            ],
            executor="agent:QA",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    test_paths=["tests/system/test_e2e_ba_dev_qa.py"],
                    doc_paths=["monitoring/AI_SERVICES_MONITORING.md"],
                ),
            },
        ),
    ]

    return ScenarioPlan(
        id=f"plan-ba-dev-qa-{feature_id}",
        goal=goal,
        steps=steps,
        required_autonomy=AutonomyLevel.A2_NON_PROD_CHANGES,
        overall_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        context={"kind": "ba-dev-qa", "feature_id": feature_id},
    )


def example_dr_rehearsal_scenario(service_name: str) -> ScenarioPlan:
    """
    Пример сценария DR rehearsal для сервиса (например, vault).
    """

    goal = ScenarioGoal(
        id=f"dr-{service_name}",
        title=f"DR rehearsal для сервиса {service_name}",
        description="Отработать сценарий отказа и восстановления сервиса.",
        constraints={"environment": "staging"},
        success_criteria=[
            "DR-плейбук выполнен без критических ошибок",
            "Постмортем-черновик создан и заполнен",
        ],
    )

    steps: List[ScenarioStep] = [
        ScenarioStep(
            id="dr-plan-validate",
            title="Проверка актуальности DR-плана",
            description="Проверить, что DR-план и артефакты для сервиса актуальны.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "DR-план найден для сервиса",
                "Последний DR-отчёт учтён в плане",
            ],
            executor="agent:DevOps",
            metadata={
                "service": service_name,
                "graph_refs": build_refs_for_service(
                    service_name,
                    doc_paths=["docs/runbooks/dr_rehearsal_plan.md"],
                )
                + build_refs_for_feature(
                    f"dr-{service_name}",
                    code_paths=["scripts/runbooks/generate_dr_postmortem.py"],
                ),
            },
        ),
        ScenarioStep(
            id="dr-simulate",
            title="Симуляция отказа и восстановления",
            description="Выполнить DR rehearsal в staging по плейбуку.",
            risk_level=ScenarioRiskLevel.NON_PROD_CHANGE,
            autonomy_required=AutonomyLevel.A2_NON_PROD_CHANGES,
            checks=[
                "Все шаги DR-плейбука выполнены в staging",
                "Мониторинг/алерты сработали ожидаемым образом",
            ],
            executor="playbook:dr",
            metadata={
                "service": service_name,
                "graph_refs": build_refs_for_service(
                    service_name,
                    doc_paths=[
                        "playbooks/dr_vault_example.yaml",
                        "monitoring/AI_SERVICES_MONITORING.md",
                    ],
                ),
            },
        ),
        ScenarioStep(
            id="dr-postmortem",
            title="Генерация и доработка постмортема",
            description="Сгенерировать черновик постмортема и доработать его.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "Постмортем-черновик создан",
                "Ключевые выводы и follow-up задачи зафиксированы",
            ],
            executor="agent:DR",
            metadata={
                "service": service_name,
                "graph_refs": [
                    "node:docs/runbooks/postmortems:INCIDENT",
                ],
            },
        ),
    ]

    return ScenarioPlan(
        id=f"plan-dr-{service_name}",
        goal=goal,
        steps=steps,
        required_autonomy=AutonomyLevel.A2_NON_PROD_CHANGES,
        overall_risk=ScenarioRiskLevel.NON_PROD_CHANGE,
        context={"kind": "dr-rehearsal", "service": service_name},
    )


def example_code_review_scenario(feature_id: str) -> ScenarioPlan:
    """
    Пример сценария code review для PR / ветки.

    Сценарий не вносит изменений сам по себе (read_only), но
    описывает структурированный поток анализа для внешнего оркестратора.
    """

    goal = ScenarioGoal(
        id=f"code-review-{feature_id}",
        title=f"Code review для фичи {feature_id}",
        description=(
            "Провести структурированный code review: собрать diff, прогнать статические проверки, "
            "получить предложения от AI и сформировать краткий отчёт."
        ),
        constraints={"environment": "dev"},
        success_criteria=[
            "Все изменения по фиче рассмотрены",
            "Есть явный список рисков и рекомендаций",
        ],
    )

    steps: List[ScenarioStep] = [
        ScenarioStep(
            id="collect-diff",
            title="Сбор diff и контекста",
            description="Собрать diff по фиче/PR и связать его с задачами/тестами.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "Diff получен из VCS",
                "Есть ссылка на исходный PR/задачу",
            ],
            executor="script:git-diff",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_service("ai-orchestrator"),
            },
        ),
        ScenarioStep(
            id="static-analysis",
            title="Статический анализ",
            description="Запустить статические анализаторы и собрать результаты.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "Статические анализаторы отработали без ошибок",
                "Результаты сконсолидированы по файлам/правилам",
            ],
            executor="script:static-analysis",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    test_paths=["tests/unit/test_code_review_api.py"],
                ),
            },
        ),
        ScenarioStep(
            id="ai-review",
            title="AI-обзор изменений",
            description="Вызвать Developer AI Secure / Code Review Agent для анализа diff.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "AI-обзор получен для всех основных изменений",
                "Выделены потенциальные риски и smell'ы",
            ],
            executor="agent:DevReview",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    code_paths=["src/api/code_review.py"],
                ),
            },
        ),
        ScenarioStep(
            id="summary",
            title="Формирование итогового отчёта",
            description="Сформировать краткий отчёт по результатам review для команды.",
            risk_level=ScenarioRiskLevel.READ_ONLY,
            autonomy_required=AutonomyLevel.A1_SAFE_AUTOMATION,
            checks=[
                "Отчёт сформирован и доступен в системе отслеживания задач/PR",
            ],
            executor="agent:BA",
            metadata={
                "feature_id": feature_id,
                "graph_refs": build_refs_for_feature(
                    feature_id,
                    doc_paths=["docs/06-features/DEVELOPER_AGENT_GUIDE.md"],
                ),
            },
        ),
    ]

    return ScenarioPlan(
        id=f"plan-code-review-{feature_id}",
        goal=goal,
        steps=steps,
        required_autonomy=AutonomyLevel.A1_SAFE_AUTOMATION,
        overall_risk=ScenarioRiskLevel.READ_ONLY,
        context={"kind": "code-review", "feature_id": feature_id},
    )


def example_empty_execution_report(plan: ScenarioPlan) -> ScenarioExecutionReport:
    """
    Пример "пустого" отчёта о выполнении сценария с базовым trust-score.

    Нужен как reference того, что пользователь увидит в будущем.
    """

    trust = TrustScore(
        score=0.5, level="medium", reasons=["Пример-заглушка, без реальных метрик"]
    )

    return ScenarioExecutionReport(
        scenario_id=plan.id,
        goal=plan.goal,
        trust_before=trust,
        trust_after=trust,
        summary="Пример отчёта: здесь будет краткое резюме выполнения сценария.",
        timeline=["Сценарий ещё не был выполнен (пример-заглушка)."],
        artifacts={},
    )
