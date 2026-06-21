
"""
Extended MCP Server with Multi-Role Support
Расширенный MCP Server с поддержкой множественных ролей
"""

import asyncio
from typing import Any, Dict, List

from src.ai.agents.business_analyst_agent import BusinessAnalystAgent
from src.ai.agents.qa_engineer_agent import QAEngineerAgent
from src.ai.role_based_router import RoleBasedRouter
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class MultiRoleMCPServer:
    """
    MCP Server с поддержкой множественных ролей
    """

    def __init__(self, host="0.0.0.0", port=6001):
        self.host = host
        self.port = port
        self.router = RoleBasedRouter()

        # Специализированные агенты
        self.ba_agent = BusinessAnalystAgent()
        self.qa_agent = QAEngineerAgent()

        # Регистрация tools для всех ролей
        self.tools = self._register_tools()

    def _offline_contract(
        self,
        *,
        tool: str,
        role: str,
        summary: str,
        context: Dict[str, Any],
        required_evidence: List[str],
        data: Dict[str, Any] | None = None,
        status: str = "needs_evidence",
    ) -> Dict[str, Any]:
        context = context or {}
        return {
            "status": status,
            "tool": tool,
            "role": role,
            "mode": "offline_mcp_contract",
            "coverage": "context_evidence" if context else "no_project_evidence",
            "summary": summary,
            "data": data or {},
            "context_keys": sorted(str(key) for key in context.keys()),
            "required_evidence": required_evidence,
            "caveats": [
                "MCP tool returned an evidence contract instead of fabricated analysis."
            ],
        }

    def _register_tools(self) -> Dict[str, callable]:
        """Регистрирует все MCP tools"""
        return {
            # Developer tools (existing)
            "dev:generate_code": self._dev_generate_code,
            "dev:optimize_function": self._dev_optimize_function,
            "dev:search_code": self._dev_search_code,
            "dev:analyze_dependencies": self._dev_analyze_dependencies,
            # Business Analyst tools
            "ba:analyze_requirements": self._ba_analyze_requirements,
            "ba:generate_spec": self._ba_generate_spec,
            "ba:extract_user_stories": self._ba_extract_user_stories,
            "ba:analyze_process": self._ba_analyze_process,
            "ba:generate_use_cases": self._ba_generate_use_cases,
            # QA Engineer tools
            "qa:generate_vanessa_tests": self._qa_generate_vanessa_tests,
            "qa:generate_smoke_tests": self._qa_generate_smoke_tests,
            "qa:analyze_coverage": self._qa_analyze_coverage,
            "qa:generate_test_data": self._qa_generate_test_data,
            "qa:analyze_bug": self._qa_analyze_bug,
            "qa:generate_regression_tests": self._qa_generate_regression_tests,
            # Architect tools
            "arch:analyze_architecture": self._arch_analyze_architecture,
            "arch:check_patterns": self._arch_check_patterns,
            "arch:detect_anti_patterns": self._arch_detect_anti_patterns,
            "arch:calculate_tech_debt": self._arch_calculate_tech_debt,
            # DevOps tools
            "devops:optimize_cicd": self._devops_optimize_cicd,
            "devops:analyze_performance": self._devops_analyze_performance,
            "devops:analyze_logs": self._devops_analyze_logs,
            "devops:capacity_planning": self._devops_capacity_planning,
            # Technical Writer tools
            "tw:generate_api_docs": self._tw_generate_api_docs,
            "tw:generate_user_guide": self._tw_generate_user_guide,
            "tw:document_function": self._tw_document_function,
            "tw:generate_release_notes": self._tw_generate_release_notes,
        }

    # ===== Developer Tools =====

    async def _dev_generate_code(self, prompt: str, context: Dict) -> Dict:
        """Генерация BSL кода"""
        result = await self.router.route_query(prompt, {**context, "role": "developer"})
        return result

    async def _dev_optimize_function(self, code: str, context: Dict) -> Dict:
        """Оптимизация функции"""
        prompt = f"Оптимизируй эту функцию:\n{code}"
        return await self.router.route_query(prompt, {**context, "role": "developer"})

    async def _dev_search_code(self, query: str, context: Dict) -> Dict:
        """Семантический поиск кода"""
        return self._offline_contract(
            tool="dev:search_code",
            role="developer",
            summary=f"Поиск кода требует подключенного индекса или переданного code_index: {query}",
            context=context,
            required_evidence=["code_index", "repository_path", "semantic_index"],
        )

    async def _dev_analyze_dependencies(self, object_name: str, context: Dict) -> Dict:
        """Анализ зависимостей"""
        dependencies = context.get("dependencies") if context else None
        if dependencies is not None:
            return self._offline_contract(
                tool="dev:analyze_dependencies",
                role="developer",
                summary=f"Зависимости для {object_name} взяты из переданного контекста.",
                context=context,
                required_evidence=[],
                data={"object_name": object_name, "dependencies": dependencies},
                status="success",
            )
        return self._offline_contract(
            tool="dev:analyze_dependencies",
            role="developer",
            summary=f"Для {object_name} не передан граф зависимостей.",
            context=context,
            required_evidence=["metadata_graph", "dependencies", "repository_path"],
        )

    # ===== Business Analyst Tools =====

    async def _ba_analyze_requirements(self, text: str, context: Dict) -> Dict:
        """Анализ требований"""
        result = await self.ba_agent.analyze_requirements(text)
        return {"status": "success", "data": result}

    async def _ba_generate_spec(self, requirements: str, context: Dict) -> Dict:
        """Генерация ТЗ"""
        spec = await self.ba_agent.generate_technical_spec(requirements)
        return {"status": "success", "spec": spec}

    async def _ba_extract_user_stories(self, text: str, context: Dict) -> Dict:
        """Извлечение user stories"""
        stories = await self.ba_agent.extract_user_stories(text)
        return {"status": "success", "user_stories": stories}

    async def _ba_analyze_process(self, description: str, context: Dict) -> Dict:
        """Анализ бизнес-процесса"""
        analysis = await self.ba_agent.analyze_business_process(description)
        return {"status": "success", "analysis": analysis}

    async def _ba_generate_use_cases(self, feature: str, context: Dict) -> Dict:
        """Генерация use case диаграммы"""
        diagram = await self.ba_agent.generate_use_cases(feature)
        return {"status": "success", "diagram": diagram}

    # ===== QA Engineer Tools =====

    async def _qa_generate_vanessa_tests(self, module_name: str, context: Dict) -> Dict:
        """Генерация Vanessa BDD тестов"""
        functions = context.get("functions", [])
        tests = await self.qa_agent.generate_vanessa_tests(module_name, functions)
        return {"status": "success", "tests": tests}

    async def _qa_generate_smoke_tests(self, configuration: str, context: Dict) -> Dict:
        """Генерация smoke-тестов"""
        tests = await self.qa_agent.generate_smoke_tests(configuration)
        return {"status": "success", "tests": tests}

    async def _qa_analyze_coverage(self, code: str, context: Dict) -> Dict:
        """Анализ покрытия тестами"""
        coverage = await self.qa_agent.analyze_test_coverage(code)
        return {"status": "success", "coverage": coverage}

    async def _qa_generate_test_data(self, entity_type: str, context: Dict) -> Dict:
        """Генерация тестовых данных"""
        count = context.get("count", 10)
        data = await self.qa_agent.generate_test_data(entity_type, count)
        return {"status": "success", "data": data}

    async def _qa_analyze_bug(self, description: str, context: Dict) -> Dict:
        """Анализ бага"""
        stacktrace = context.get("stacktrace", "")
        analysis = await self.qa_agent.analyze_bug(description, stacktrace)
        return {"status": "success", "analysis": analysis}

    async def _qa_generate_regression_tests(
        self, bug_fixes: List[str], context: Dict
    ) -> Dict:
        """Генерация регрессионных тестов"""
        tests = await self.qa_agent.generate_regression_tests(bug_fixes)
        return {"status": "success", "tests": tests}

    # ===== Architect Tools =====

    async def _arch_analyze_architecture(self, config_name: str, context: Dict) -> Dict:
        """Анализ архитектуры"""
        modules = context.get("modules", []) if context else []
        dependencies = context.get("dependencies", []) if context else []
        status = "success" if modules or dependencies else "needs_evidence"
        return self._offline_contract(
            tool="arch:analyze_architecture",
            role="architect",
            summary=f"Архитектурный анализ {config_name} строится только по переданному графу.",
            context=context,
            required_evidence=[] if status == "success" else ["metadata_graph", "modules", "dependencies"],
            data={
                "config_name": config_name,
                "modules_count": len(modules),
                "dependencies_count": len(dependencies),
                "issues": [],
            },
            status=status,
        )

    async def _arch_check_patterns(self, code: str, context: Dict) -> Dict:
        """Проверка паттернов"""
        return self._offline_contract(
            tool="arch:check_patterns",
            role="architect",
            summary="Проверка паттернов требует исходного кода и правил архитектуры.",
            context={**(context or {}), "code_provided": bool(code.strip())},
            required_evidence=[] if code.strip() else ["code"],
            data={"patterns_found": [], "recommendations": []},
            status="success" if code.strip() else "needs_evidence",
        )

    async def _arch_detect_anti_patterns(self, code: str, context: Dict) -> Dict:
        """Поиск anti-patterns"""
        return self._offline_contract(
            tool="arch:detect_anti_patterns",
            role="architect",
            summary="Anti-patterns не называются без анализа AST/метрик по переданному коду.",
            context={**(context or {}), "code_provided": bool(code.strip())},
            required_evidence=[] if code.strip() else ["code", "metadata_graph"],
            data={"anti_patterns": []},
            status="success" if code.strip() else "needs_evidence",
        )

    async def _arch_calculate_tech_debt(self, config_name: str, context: Dict) -> Dict:
        """Расчет технического долга"""
        return self._offline_contract(
            tool="arch:calculate_tech_debt",
            role="architect",
            summary=f"Технический долг {config_name} требует метрик, правил оценки и истории дефектов.",
            context=context,
            required_evidence=["quality_metrics", "duplication_report", "complexity_report", "bug_history"],
            data={"tech_debt": {"measured": False, "total_days": None, "by_category": {}}},
        )

    # ===== DevOps Tools =====

    async def _devops_optimize_cicd(self, pipeline: str, context: Dict) -> Dict:
        """Оптимизация CI/CD"""
        recommendations = []
        lower = pipeline.lower()
        if pipeline.strip():
            if "cache" not in lower:
                recommendations.append("Проверить кеширование зависимостей/build artifacts.")
            if "test" not in lower and "тест" not in lower:
                recommendations.append("Добавить явный test gate перед deploy.")
            if "approval" not in lower and "approve" not in lower:
                recommendations.append("Добавить approval gate для deploy/apply шагов.")
        return self._offline_contract(
            tool="devops:optimize_cicd",
            role="devops",
            summary="CI/CD рекомендации построены только по переданному pipeline text.",
            context=context,
            required_evidence=[] if pipeline.strip() else ["pipeline_config"],
            data={"recommendations": recommendations},
            status="success" if pipeline.strip() else "needs_evidence",
        )

    async def _devops_analyze_performance(self, metrics: Dict, context: Dict) -> Dict:
        """Анализ производительности"""
        bottlenecks = []
        for key, value in (metrics or {}).items():
            if isinstance(value, (int, float)) and value >= 80:
                bottlenecks.append({"metric": key, "value": value, "reason": ">= 80 threshold"})
        return self._offline_contract(
            tool="devops:analyze_performance",
            role="devops",
            summary="Performance triage использует только переданные числовые метрики.",
            context={**(context or {}), "metrics_keys": sorted((metrics or {}).keys())},
            required_evidence=[] if metrics else ["metrics", "tech_journal", "slow_query_log"],
            data={"bottlenecks": bottlenecks, "recommendations": []},
            status="success" if metrics else "needs_evidence",
        )

    async def _devops_analyze_logs(self, logs: str, context: Dict) -> Dict:
        """Анализ логов"""
        lines = [line for line in logs.splitlines() if line.strip()]
        error_lines = [
            line for line in lines if any(marker in line.lower() for marker in ("error", "ошиб", "exception"))
        ]
        warning_lines = [
            line for line in lines if any(marker in line.lower() for marker in ("warn", "предупреж"))
        ]
        return self._offline_contract(
            tool="devops:analyze_logs",
            role="devops",
            summary="Логи просканированы локально без выдуманных паттернов.",
            context=context,
            required_evidence=[] if logs.strip() else ["logs", "tech_journal_path"],
            data={
                "total_lines": len(lines),
                "errors": len(error_lines),
                "warnings": len(warning_lines),
                "patterns": [],
                "sample_errors": error_lines[:5],
            },
            status="success" if logs.strip() else "needs_evidence",
        )

    async def _devops_capacity_planning(self, usage_data: Dict, context: Dict) -> Dict:
        """Планирование мощностей"""
        current = usage_data.get("current_capacity") or usage_data.get("utilization")
        data = {"forecast": {"measured": bool(current), "current_capacity": current}}
        return self._offline_contract(
            tool="devops:capacity_planning",
            role="devops",
            summary="Capacity planning требует фактической утилизации и тренда.",
            context={**(context or {}), "usage_keys": sorted((usage_data or {}).keys())},
            required_evidence=[] if current else ["usage_data.current_capacity", "trend_history"],
            data=data,
            status="success" if current else "needs_evidence",
        )

    # ===== Technical Writer Tools =====

    async def _tw_generate_api_docs(self, module_name: str, context: Dict) -> Dict:
        """Генерация API документации"""
        code = (context or {}).get("code", "")
        return self._offline_contract(
            tool="tw:generate_api_docs",
            role="technical_writer",
            summary=f"API docs для {module_name} требуют кода, OpenAPI или списка endpoints.",
            context=context,
            required_evidence=[] if code else ["code", "openapi", "endpoints"],
            data={"documentation": f"# API Documentation: {module_name}\n\nИсточник: переданный код.\n" if code else ""},
            status="success" if code else "needs_evidence",
        )

    async def _tw_generate_user_guide(self, feature: str, context: Dict) -> Dict:
        """Генерация user guide"""
        return self._offline_contract(
            tool="tw:generate_user_guide",
            role="technical_writer",
            summary=f"User guide для {feature} требует сценариев и аудитории.",
            context=context,
            required_evidence=["feature_scenarios", "audience", "screenshots_or_steps"],
            data={"guide": ""},
        )

    async def _tw_document_function(self, code: str, context: Dict) -> Dict:
        """Документирование функции"""
        has_code = bool(code.strip())
        return self._offline_contract(
            tool="tw:document_function",
            role="technical_writer",
            summary="Документирование функции требует исходного кода.",
            context={**(context or {}), "code_provided": has_code},
            required_evidence=[] if has_code else ["code"],
            data={"documentation": "Описание должно быть сформировано из сигнатуры и комментариев переданного кода." if has_code else ""},
            status="success" if has_code else "needs_evidence",
        )

    async def _tw_generate_release_notes(self, version: str, context: Dict) -> Dict:
        """Генерация release notes"""
        commits = (context or {}).get("commits", [])
        return self._offline_contract(
            tool="tw:generate_release_notes",
            role="technical_writer",
            summary=f"Release notes v{version} требуют commits/change set.",
            context=context,
            required_evidence=[] if commits else ["commits", "change_set", "fixed_bugs"],
            data={"release_notes": f"# Release Notes v{version}\n\n" + "\n".join(f"- {commit}" for commit in commits)},
            status="success" if commits else "needs_evidence",
        )

    async def handle_request(self, tool_name: str, args: Dict) -> Dict:
        """
        Обрабатывает запрос к MCP tool

        Args:
            tool_name: Название tool (например, "ba:analyze_requirements")
            args: Аргументы

        Returns:
            Результат выполнения
        """
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            handler = self.tools[tool_name]
            result = await handler(**args)
            return result
        except Exception as e:
            logger.error(
                "Error handling tool",
                extra={
                    "tool_name": tool_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return {"error": str(e)}

    def start(self):
        """Запускает MCP Server"""
        logger.info(
            "Starting Multi-Role MCP Server",
            extra={"host": self.host, "port": self.port},
        )
        logger.info(
            "Registered tools", extra={"tools_count": len(self.tools), "roles_count": 6}
        )

        # Embedded registry mode: protocol hosting is provided by src.ai.mcp.server.

        print(
            f"""
╔══════════════════════════════════════════════════════════════╗
║       Multi-Role MCP Tool Registry Ready                     ║
║       Port: {self.port}                                              ║
║       Roles: 6                                                ║
║       Tools: {len(self.tools)}                                              ║
╚══════════════════════════════════════════════════════════════╝

Available Roles:
  👨‍💻 Developer      - {len([t for t in self.tools if t.startswith('dev:')])} tools
  📊 Business Analyst - {len([t for t in self.tools if t.startswith('ba:')])} tools
  🧪 QA Engineer      - {len([t for t in self.tools if t.startswith('qa:')])} tools
  🏗️ Architect        - {len([t for t in self.tools if t.startswith('arch:')])} tools
  ⚙️ DevOps           - {len([t for t in self.tools if t.startswith('devops:')])} tools
  📝 Technical Writer - {len([t for t in self.tools if t.startswith('tw:')])} tools
"""
        )


# Example usage
if __name__ == "__main__":
    server = MultiRoleMCPServer()
    server.start()

    # Test requests
    async def test():
        # Test Business Analyst tool
        result = await server.handle_request(
            "ba:analyze_requirements",
            {"text": "Нужна система учета продаж", "context": {}},
        )
        print("\n=== BA Tool Test ===")
        print(f"User Stories: {len(result['data']['user_stories'])}")

        # Test QA tool
        result = await server.handle_request(
            "qa:generate_smoke_tests",
            {"configuration": "Управление продажами", "context": {}},
        )
        print("\n=== QA Tool Test ===")
        print(f"Smoke Tests: {len(result['tests'])}")

    asyncio.run(test())
