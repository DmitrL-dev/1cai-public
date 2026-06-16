
"""
Role-Based AI Router
Маршрутизация запросов в зависимости от роли пользователя.
Использует Micro-Swarm MicroModel для умного определения роли
с fallback на keyword matching.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.micro_swarm.domains import (
    ROLE_DETECTION_DOMAIN,
    extract_role_features,
)
from src.micro_swarm.model import MicroModel, MicroModelConfig
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class UserRole(Enum):
    """Роли пользователей в системе"""

    DEVELOPER = "developer"
    BUSINESS_ANALYST = "business_analyst"
    QA_ENGINEER = "qa_engineer"
    ARCHITECT = "architect"
    DEVOPS = "devops"
    TECHNICAL_WRITER = "technical_writer"


@dataclass
class RoleConfig:
    """Конфигурация для роли"""

    role: UserRole
    primary_agent: str
    fallback_agents: List[str]
    specializations: List[str]
    temperature: float = 0.3
    max_tokens: int = 2000
    language: str = "ru"


class RoleDetector:
    """Определение роли по запросу (MicroModel + keyword fallback)"""

    # Keywords для каждой роли (используются как fallback и для feature extraction)
    ROLE_KEYWORDS = {
        UserRole.DEVELOPER: [
            "сгенерируй код",
            "напиши функцию",
            "создай процедуру",
            "оптимизируй",
            "рефактор",
            "исправь код",
            "code",
            "function",
            "генерируй bsl",
            "реализуй",
            "доработай",
        ],
        UserRole.BUSINESS_ANALYST: [
            "требования",
            "ТЗ",
            "техническое задание",
            "бизнес-процесс",
            "user story",
            "use case",
            "сценарий",
            "анализ требований",
            "specification",
            "requirements",
            "процесс",
        ],
        UserRole.QA_ENGINEER: [
            "тест",
            "тестирование",
            "покрытие",
            "баг",
            "bug",
            "vanessa",
            "bdd",
            "smoke",
            "regression",
            "дефект",
            "проверка",
            "quality",
            "qa",
        ],
        UserRole.ARCHITECT: [
            "архитектура",
            "паттерн",
            "зависимости",
            "структура",
            "anti-pattern",
            "best practice",
            "design",
            "модульность",
            "coupling",
            "cohesion",
            "технический долг",
        ],
        UserRole.DEVOPS: [
            "ci/cd",
            "deployment",
            "производительность",
            "мониторинг",
            "docker",
            "kubernetes",
            "pipeline",
            "логи",
            "performance",
            "optimize",
            "infrastructure",
            "capacity",
        ],
        UserRole.TECHNICAL_WRITER: [
            "документация",
            "описание",
            "справка",
            "api docs",
            "user guide",
            "readme",
            "release notes",
            "мануал",
            "инструкция",
            "help",
            "documentation",
        ],
    }

    def __init__(self) -> None:
        """Инициализация RoleDetector с MicroModel."""
        self._micro_model = None
        try:
            config = MicroModelConfig(
                n_features=ROLE_DETECTION_DOMAIN.n_features,
                n_embd=16,
                n_head=4,
                n_layer=1,
            )
            self._micro_model = MicroModel(config)
            logger.info(
                "RoleDetector: MicroModel initialized "
                f"({self._micro_model.param_count} params)"
            )
        except Exception as e:
            logger.warning("RoleDetector MicroModel init failed: %s", e)

    def detect_role(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> UserRole:
        """
        Определяет роль пользователя по запросу и контексту.

        Primary: keyword matching (проверенный)
        Enhancement: MicroModel score для усиления решения
        """
        query_lower = query.lower()

        # Подсчет совпадений для каждой роли
        role_scores = {role: 0.0 for role in UserRole}

        for role, keywords in self.ROLE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    role_scores[role] += 1.0

        # Micro-Swarm enhancement: model score adds signal
        if self._micro_model is not None:
            try:
                raw_features = extract_role_features(query)
                features = ROLE_DETECTION_DOMAIN.extract(raw_features)
                model_score, _ = self._micro_model.forward(features)
                # Boost top keyword-matched role by model confidence
                max_keyword_role = max(role_scores, key=role_scores.get)
                if role_scores[max_keyword_role] > 0:
                    role_scores[max_keyword_role] += model_score * 2.0
            except Exception as e:
                logger.debug("RoleDetector MicroModel scoring failed: %s", e)

        # Если есть контекст, учитываем его
        if context:
            current_file = context.get("current_file", "")
            if current_file.endswith(".bsl"):
                role_scores[UserRole.DEVELOPER] += 2
            elif current_file.endswith(".feature"):
                role_scores[UserRole.QA_ENGINEER] += 2
            elif current_file.endswith(".md"):
                role_scores[UserRole.TECHNICAL_WRITER] += 2

            if "role" in context:
                try:
                    return UserRole(context["role"])
                except ValueError:
                    pass

        # Находим роль с максимальным score
        max_score = max(role_scores.values())

        if max_score > 0:
            for role, score in role_scores.items():
                if score == max_score:
                    return role

        # По умолчанию - разработчик
        return UserRole.DEVELOPER


class RoleBasedRouter:
    """
    Маршрутизатор запросов на основе ролей
    """

    def __init__(self):
        self.detector = RoleDetector()
        self.role_configs = self._load_role_configs()

        # Импорты AI клиентов
        try:
            from src.ai.qwen_client import QwenClient

            self.qwen_client = QwenClient()
        except (ImportError, Exception):
            self.qwen_client = None
            logger.warning("QwenClient not available")

        # Phase 7: replaced phantom *_extended agents with real ones
        try:
            from src.ai.agents.security_agent import SecurityAgent

            self.devops_agent = (
                None  # DevOpsAgentExtended removed, use SecurityAgent for infra
            )
            self.security_agent = SecurityAgent()
        except Exception as e:
            self.devops_agent = None
            self.security_agent = None
            logger.warning("SecurityAgent not available: %s", e)

        try:
            from src.ai.agents.qa_engineer_agent import QAEngineerAgent

            self.qa_agent = QAEngineerAgent()
        except Exception as e:
            self.qa_agent = None
            logger.warning("QAEngineerAgent not available: %s", e)

        try:
            from src.ai.agents.business_analyst_agent import BusinessAnalystAgent

            self.ba_agent = BusinessAnalystAgent()
        except Exception as e:
            self.ba_agent = None
            logger.warning("BusinessAnalystAgent not available: %s", e)

        # TechnicalWriterAgentExtended removed — no replacement yet
        self.tw_agent = None

    def _load_role_configs(self) -> Dict[UserRole, RoleConfig]:
        """Загружает конфигурации для ролей"""
        return {
            UserRole.DEVELOPER: RoleConfig(
                role=UserRole.DEVELOPER,
                primary_agent="qwen3-coder",
                fallback_agents=["1c-naparnik", "openai-gpt4"],
                specializations=["code_generation", "optimization", "refactoring"],
                temperature=0.2,
                max_tokens=2000,
                language="ru",
            ),
            UserRole.BUSINESS_ANALYST: RoleConfig(
                role=UserRole.BUSINESS_ANALYST,
                primary_agent="gigachat",
                fallback_agents=["yandex-gpt", "openai-gpt4"],
                specializations=[
                    "requirements_analysis",
                    "documentation",
                    "business_process",
                ],
                temperature=0.5,
                max_tokens=4000,
                language="ru",
            ),
            UserRole.QA_ENGINEER: RoleConfig(
                role=UserRole.QA_ENGINEER,
                primary_agent="qwen3-coder",
                fallback_agents=["openai-gpt4"],
                specializations=[
                    "test_generation",
                    "bug_analysis",
                    "coverage_analysis",
                ],
                temperature=0.3,
                max_tokens=2000,
                language="ru",
            ),
            UserRole.ARCHITECT: RoleConfig(
                role=UserRole.ARCHITECT,
                primary_agent="openai-gpt4",
                fallback_agents=["claude-3-opus"],
                specializations=[
                    "architecture_analysis",
                    "pattern_detection",
                    "best_practices",
                ],
                temperature=0.4,
                max_tokens=3000,
                language="ru",
            ),
            UserRole.DEVOPS: RoleConfig(
                role=UserRole.DEVOPS,
                primary_agent="openai-gpt4",
                fallback_agents=["qwen3-coder"],
                specializations=[
                    "cicd_optimization",
                    "performance_analysis",
                    "infrastructure",
                ],
                temperature=0.3,
                max_tokens=2000,
                language="ru",
            ),
            UserRole.TECHNICAL_WRITER: RoleConfig(
                role=UserRole.TECHNICAL_WRITER,
                primary_agent="openai-gpt4",
                fallback_agents=["gigachat"],
                specializations=[
                    "documentation_generation",
                    "api_docs",
                    "translations",
                ],
                temperature=0.6,
                max_tokens=4000,
                language="ru",
            ),
        }

    async def route_query(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Маршрутизирует запрос к соответствующему AI агенту

        Args:
            query: Запрос пользователя
            context: Контекст запроса

        Returns:
            Ответ от AI агента
        """
        # Определяем роль
        role = self.detector.detect_role(query, context)
        config = self.role_configs[role]

        logger.info(
            "Detected role",
            extra={"role": role.value, "primary_agent": config.primary_agent},
        )

        # Маршрутизируем к соответствующему обработчику
        if role == UserRole.DEVELOPER:
            return await self._handle_developer(query, config, context)
        elif role == UserRole.BUSINESS_ANALYST:
            return await self._handle_business_analyst(query, config, context)
        elif role == UserRole.QA_ENGINEER:
            return await self._handle_qa_engineer(query, config, context)
        elif role == UserRole.ARCHITECT:
            return await self._handle_architect(query, config, context)
        elif role == UserRole.DEVOPS:
            return await self._handle_devops(query, config, context)
        elif role == UserRole.TECHNICAL_WRITER:
            return await self._handle_technical_writer(query, config, context)
        else:
            return {"error": f"Unknown role: {role}"}

    async def _handle_developer(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов разработчика"""
        if self.qwen_client:
            # Используем Qwen3-Coder для генерации кода
            response = await self.qwen_client.generate_code(query, context or {})
            return {
                "role": "developer",
                "agent": "qwen3-coder",
                "response": response,
                "specialization": "code_generation",
            }
        else:
            return {
                "role": "developer",
                "agent": "placeholder",
                "response": f"[Developer AI] Обработка запроса: {query}",
                "note": "Qwen3-Coder not available",
            }

    async def _handle_business_analyst(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов бизнес-аналитика"""
        if self.ba_agent:
            query_lower = query.lower()

            # Requirements extraction
            if any(
                kw in query_lower
                for kw in ["требования", "извлечь", "tz", "техническое задание"]
            ):
                document_path = context.get("document_path") if context else None
                document_type = context.get("document_type") if context else None
                if document_path:
                    result = await self.ba_agent.extract_requirements_from_file(
                        document_path, document_type
                    )
                else:
                    document_text = (
                        context.get("document_text", query) if context else query
                    )
                    doc_type = document_type or "tz"
                    result = await self.ba_agent.extract_requirements(
                        document_text, doc_type
                    )
                return {
                    "role": "business_analyst",
                    "agent": "ba_agent_extended",
                    "function": "extract_requirements",
                    "result": result,
                    "specialization": "requirements_extraction",
                }

            # BPMN generation
            elif any(
                kw in query_lower
                for kw in ["bpmn", "бизнес-процесс", "процесс", "диаграмма"]
            ):
                result = await self.ba_agent.generate_bpmn(query)
                return {
                    "role": "business_analyst",
                    "agent": "ba_agent_extended",
                    "function": "generate_bpmn",
                    "result": result,
                    "specialization": "bpmn_generation",
                }

            # Gap analysis
            elif any(kw in query_lower for kw in ["gap", "разрыв", "текущ", "желаем"]):
                current_state = context.get("current_state", {}) if context else {}
                desired_state = context.get("desired_state", {}) if context else {}
                result = await self.ba_agent.analyze_gap(current_state, desired_state)
                return {
                    "role": "business_analyst",
                    "agent": "ba_agent_extended",
                    "function": "analyze_gap",
                    "result": result,
                    "specialization": "gap_analysis",
                }

            # Traceability matrix
            elif any(
                kw in query_lower for kw in ["матриц", "прослеживаем", "traceability"]
            ):
                requirements = context.get("requirements", []) if context else []
                test_cases = context.get("test_cases", []) if context else []
                result = await self.ba_agent.generate_traceability_matrix(
                    requirements, test_cases
                )
                return {
                    "role": "business_analyst",
                    "agent": "ba_agent_extended",
                    "function": "generate_traceability_matrix",
                    "result": result,
                    "specialization": "traceability_matrix",
                }

        # Fallback
        return {
            "role": "business_analyst",
            "agent": "placeholder",
            "response": f"[Business Analyst AI] Анализ: {query}",
            "note": "BA Agent Extended not available",
        }

    async def _handle_qa_engineer(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов тестировщика"""
        if self.qa_agent:
            query_lower = query.lower()

            # Test generation
            if any(
                kw in query_lower for kw in ["генерир", "создай тест", "напиши тест"]
            ):
                function_code = context.get("function_code", "") if context else ""
                function_name = (
                    context.get("function_name", "Функция") if context else "Функция"
                )
                result = await self.qa_agent.generate_tests(
                    function_code, function_name
                )
                return {
                    "role": "qa_engineer",
                    "agent": "qa_agent_extended",
                    "function": "generate_tests",
                    "result": result,
                    "specialization": "smart_test_generation",
                }

            # Coverage analysis
            elif any(
                kw in query_lower for kw in ["покрытие", "coverage", "анализ тестов"]
            ):
                config_name = context.get("config_name", "ERP") if context else "ERP"
                result = await self.qa_agent.analyze_coverage(config_name)
                return {
                    "role": "qa_engineer",
                    "agent": "qa_agent_extended",
                    "function": "analyze_coverage",
                    "result": result,
                    "specialization": "coverage_analysis",
                }

            # Bug pattern analysis
            elif any(kw in query_lower for kw in ["баг", "bug", "паттерн", "hotspot"]):
                bug_history = context.get("bug_history", []) if context else []
                result = await self.qa_agent.analyze_bugs(bug_history)
                return {
                    "role": "qa_engineer",
                    "agent": "qa_agent_extended",
                    "function": "analyze_bugs",
                    "result": result,
                    "specialization": "bug_pattern_analysis",
                }

            # Performance test generation
            elif any(
                kw in query_lower for kw in ["performance", "нагрузк", "k6", "jmeter"]
            ):
                endpoints = context.get("endpoints", []) if context else []
                load_profile = context.get("load_profile", {}) if context else {}
                result = await self.qa_agent.generate_performance_test(
                    endpoints, load_profile
                )
                return {
                    "role": "qa_engineer",
                    "agent": "qa_agent_extended",
                    "function": "generate_performance_test",
                    "result": result,
                    "specialization": "performance_testing",
                }

        # Fallback
        return {
            "role": "qa_engineer",
            "agent": "placeholder",
            "response": f"[QA Engineer AI] Генерация тестов: {query}",
            "note": "QA Agent Extended not available",
        }

    async def _handle_architect(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов архитектора"""
        system_prompt = """Ты - AI ассистент для архитектора 1С.
Твои задачи:
- Анализировать архитектуру конфигурации
- Выявлять anti-patterns и code smells
- Рекомендовать design patterns
- Проверять соблюдение best practices
- Анализировать зависимости между модулями
- Вычислять технический долг

Используй знания о 1С best practices и паттернах проектирования."""

        return {
            "role": "architect",
            "agent": "openai-gpt4",
            "response": f"[Architect AI] Архитектурный анализ: {query}",
            "system_prompt": system_prompt,
            "specialization": "architecture_analysis",
            "note": "OpenAI GPT-4 integration pending",
        }

    async def _handle_devops(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов DevOps инженера"""
        if self.devops_agent:
            query_lower = query.lower()

            # CI/CD pipeline optimization
            if any(
                kw in query_lower
                for kw in ["ci/cd", "pipeline", "оптимизир", "github actions"]
            ):
                pipeline_config = context.get("pipeline_config", {}) if context else {}
                metrics = context.get("metrics", {}) if context else {}
                result = await self.devops_agent.optimize_pipeline(
                    pipeline_config, metrics
                )
                return {
                    "role": "devops",
                    "agent": "devops_agent_extended",
                    "function": "optimize_pipeline",
                    "result": result,
                    "specialization": "cicd_optimization",
                }

            # Log analysis
            elif any(
                kw in query_lower for kw in ["логи", "log", "анализ логов", "ошибк"]
            ):
                log_source = context.get("log_source", query) if context else query
                log_type = (
                    context.get("log_type", "application") if context else "application"
                )
                result = await self.devops_agent.analyze_logs(log_source, log_type)
                return {
                    "role": "devops",
                    "agent": "devops_agent_extended",
                    "function": "analyze_logs",
                    "result": result,
                    "specialization": "log_analysis",
                }

            # Cost optimization
            elif any(
                kw in query_lower
                for kw in ["cost", "затраты", "стоимость", "optimize", "экономи"]
            ):
                infrastructure = context.get("infrastructure", {}) if context else {}
                metrics = context.get("metrics", {}) if context else {}
                result = await self.devops_agent.optimize_costs(infrastructure, metrics)
                return {
                    "role": "devops",
                    "agent": "devops_agent_extended",
                    "function": "optimize_costs",
                    "result": result,
                    "specialization": "cost_optimization",
                }

            # IaC generation
            elif any(
                kw in query_lower
                for kw in ["terraform", "iac", "infrastructure", "генерир"]
            ):
                requirements = context.get("requirements", {}) if context else {}
                result = await self.devops_agent.generate_iac(requirements)
                return {
                    "role": "devops",
                    "agent": "devops_agent_extended",
                    "function": "generate_iac",
                    "result": result,
                    "specialization": "iac_generation",
                }

        # Fallback
        return {
            "role": "devops",
            "agent": "placeholder",
            "response": f"[DevOps AI] Анализ: {query}",
            "note": "DevOps Agent Extended not available",
        }

    async def _handle_technical_writer(
        self, query: str, config: RoleConfig, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Обработка запросов технического писателя"""
        if self.tw_agent:
            query_lower = query.lower()

            # API documentation
            if any(
                kw in query_lower for kw in ["api", "openapi", "swagger", "postman"]
            ):
                code = context.get("code", "") if context else ""
                module_type = (
                    context.get("module_type", "http_service")
                    if context
                    else "http_service"
                )
                result = await self.tw_agent.generate_api_docs(code, module_type)
                return {
                    "role": "technical_writer",
                    "agent": "tw_agent_extended",
                    "function": "generate_api_docs",
                    "result": result,
                    "specialization": "api_documentation",
                }

            # User guide
            elif any(
                kw in query_lower
                for kw in ["руководство", "guide", "инструкц", "мануал"]
            ):
                feature = context.get("feature", query) if context else query
                audience = (
                    context.get("audience", "end_user") if context else "end_user"
                )
                result = await self.tw_agent.generate_user_guide(feature, audience)
                return {
                    "role": "technical_writer",
                    "agent": "tw_agent_extended",
                    "function": "generate_user_guide",
                    "result": result,
                    "specialization": "user_guide_generation",
                }

            # Release notes
            elif any(
                kw in query_lower for kw in ["release", "релиз", "changelog", "версия"]
            ):
                commits = context.get("commits", []) if context else []
                version = context.get("version", "v1.0.0") if context else "v1.0.0"
                result = await self.tw_agent.generate_release_notes(commits, version)
                return {
                    "role": "technical_writer",
                    "agent": "tw_agent_extended",
                    "function": "generate_release_notes",
                    "result": result,
                    "specialization": "release_notes_generation",
                }

            # Code documentation
            elif any(
                kw in query_lower
                for kw in ["документир", "комментари", "описание функции"]
            ):
                code = context.get("code", "") if context else ""
                language = context.get("language", "bsl") if context else "bsl"
                result = await self.tw_agent.document_code(code, language)
                return {
                    "role": "technical_writer",
                    "agent": "tw_agent_extended",
                    "function": "document_code",
                    "result": result,
                    "specialization": "code_documentation",
                }

        # Fallback
        return {
            "role": "technical_writer",
            "agent": "placeholder",
            "response": f"[Technical Writer AI] Генерация документации: {query}",
            "note": "TW Agent Extended not available",
        }


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        router = RoleBasedRouter()

        # Тестовые запросы для разных ролей
        queries = [
            "Сгенерируй функцию проверки ИНН",
            "Проанализируй требования из ТЗ",
            "Создай Vanessa BDD тесты для модуля Продажи",
            "Найди циклические зависимости в архитектуре",
            "Оптимизируй CI/CD pipeline",
            "Создай API документацию для модуля",
        ]

        for query in queries:
            print(f"\n{'=' * 60}")
            print(f"Query: {query}")
            result = await router.route_query(query)
            print(f"Role: {result['role']}")
            print(f"Agent: {result['agent']}")
            print(f"Response: {result['response'][:100]}...")

    asyncio.run(test())
