
"""
MCP Server для AI Архитектора - Полный функционал
Все возможности архитектора через MCP protocol
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from typing import Dict, List

from src.ai.agents.architect_agent_extended import ArchitectAgentExtended
from src.ai.agents.onec_server_optimizer import OneCServerOptimizer
from src.ai.agents.performance_analyzer import PerformanceAnalyzer
from src.ai.agents.sql_optimizer import SQLOptimizer
from src.ai.agents.technology_selector import TechnologySelector
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class ArchitectMCPServer:
    """
    MCP Server специально для AI Архитектора
    Предоставляет все архитектурные функции через MCP
    """

    def __init__(self, host="0.0.0.0", port=6002):
        self.host = host
        self.port = port

        # AI Agents
        self.architect = ArchitectAgentExtended()
        self.tech_selector = TechnologySelector()
        self.perf_analyzer = PerformanceAnalyzer()
        self.sql_optimizer = SQLOptimizer("postgresql")
        self.server_optimizer = OneCServerOptimizer()

        # MCP Tools
        self.tools = self._register_tools()

    def _register_tools(self) -> Dict[str, callable]:
        """Регистрация всех архитектурных MCP tools"""
        return {
            # Graph Analysis
            "arch:analyze_graph": self._analyze_graph,
            "arch:find_cycles": self._find_cycles,
            "arch:find_god_objects": self._find_god_objects,
            "arch:calculate_coupling": self._calculate_coupling,
            # ADR
            "arch:generate_adr": self._generate_adr,
            "arch:list_adrs": self._list_adrs,
            "arch:get_adr": self._get_adr,
            # Anti-Patterns
            "arch:detect_anti_patterns": self._detect_anti_patterns,
            "arch:get_quality_score": self._get_quality_score,
            "arch:refactoring_roadmap": self._refactoring_roadmap,
            # Technology Selection
            "arch:recommend_tech_stack": self._recommend_tech_stack,
            "arch:compare_technologies": self._compare_technologies,
            # Performance
            "arch:analyze_performance": self._analyze_performance,
            "arch:find_bottlenecks": self._find_bottlenecks,
            "arch:optimize_query": self._optimize_query,
            # Design
            "arch:generate_diagram": self._generate_diagram,
            "arch:analyze_requirements": self._analyze_requirements,
            "arch:assess_risks": self._assess_risks,
            # Integration Architecture
            "arch:design_integration": self._design_integration,
            "arch:generate_api_spec": self._generate_api_spec,
            # SQL Optimization
            "arch:optimize_sql": self._optimize_sql,
            "arch:detect_sql_antipatterns": self._detect_sql_antipatterns,
            "arch:recommend_indexes": self._recommend_indexes,
            "arch:optimize_1c_query": self._optimize_1c_query,
            "arch:recommend_db_config": self._recommend_db_config,
            # 1C Server Optimization
            "arch:optimize_1c_server": self._optimize_1c_server,
            "arch:tune_working_processes": self._tune_working_processes,
        }

    # ===== Graph Analysis Tools =====

    async def _analyze_graph(self, config_name: str, context: Dict) -> Dict:
        """Полный граф-анализ архитектуры"""
        result = await self.architect.analyze_architecture_graph(
            config_name, deep_analysis=context.get("deep_analysis", True)
        )
        return {"status": "success", "data": result}

    async def _find_cycles(self, config_name: str, context: Dict) -> Dict:
        """Поиск циклических зависимостей"""
        cycles = await self.architect._find_cyclic_dependencies(config_name)
        return {"status": "success", "cycles_count": len(cycles), "cycles": cycles}

    async def _find_god_objects(self, config_name: str, context: Dict) -> Dict:
        """Поиск God Objects"""
        god_objects = await self.architect._find_god_objects(config_name)
        return {
            "status": "success",
            "god_objects_count": len(god_objects),
            "god_objects": god_objects,
        }

    async def _calculate_coupling(self, config_name: str, context: Dict) -> Dict:
        """Расчет coupling метрик"""
        coupling = await self.architect._analyze_coupling(config_name)
        cohesion = await self.architect._analyze_cohesion(config_name)
        return {"status": "success", "coupling": coupling, "cohesion": cohesion}

    # ===== ADR Tools =====

    async def _generate_adr(self, title: str, context: Dict) -> Dict:
        """Генерация ADR"""
        adr_data = await self.architect.generate_adr(
            title=title,
            context=context.get("context", ""),
            problem=context.get("problem", ""),
            alternatives=context.get("alternatives", []),
            decision=context.get("decision", ""),
            rationale=context.get("rationale", ""),
            consequences=context.get("consequences", {}),
        )
        return {"status": "success", "adr": adr_data}

    async def _list_adrs(self, filter_params: Dict, context: Dict) -> Dict:
        """Список всех ADR"""
        # TODO: Query from PostgreSQL
        return {
            "status": "success",
            "adrs": [
                {
                    "adr_id": "ADR-001",
                    "title": "Выбор шины данных",
                    "date": "2025-11-03",
                    "status": "accepted",
                }
            ],
        }

    async def _get_adr(self, adr_id: str, context: Dict) -> Dict:
        """Получить конкретный ADR"""
        # TODO: Query from PostgreSQL
        return {"status": "success", "adr": {}}

    # ===== Anti-Pattern Detection Tools =====

    async def _detect_anti_patterns(self, config_name: str, context: Dict) -> Dict:
        """Детекция anti-patterns"""
        include_code = context.get("include_code_analysis", True)
        result = await self.architect.detect_anti_patterns(
            config_name, include_code_analysis=include_code
        )
        return {"status": "success", "analysis": result}

    async def _get_quality_score(self, config_name: str, context: Dict) -> Dict:
        """Получить quality score"""
        result = await self.architect.detect_anti_patterns(config_name, False)
        return {
            "status": "success",
            "quality_score": result["overall_score"],
            "grade": result["quality_grade"],
        }

    async def _refactoring_roadmap(self, config_name: str, context: Dict) -> Dict:
        """Генерация roadmap рефакторинга"""
        result = await self.architect.detect_anti_patterns(config_name, False)
        return {"status": "success", "roadmap": result["refactoring_roadmap"]}

    # ===== Technology Selection Tools =====

    async def _recommend_tech_stack(self, requirements: Dict, context: Dict) -> Dict:
        """Рекомендация технологического стека"""
        constraints = context.get("constraints", {})
        result = await self.tech_selector.recommend_technology_stack(
            requirements, constraints
        )
        return {"status": "success", "recommendation": result}

    async def _compare_technologies(self, tech_list: List[str], context: Dict) -> Dict:
        """Сравнение технологий"""
        # TODO: Implement comparison matrix
        return {
            "status": "success",
            "comparison": {"technologies": tech_list, "matrix": []},
        }

    # ===== Performance Tools =====

    async def _analyze_performance(self, config_name: str, context: Dict) -> Dict:
        """Анализ производительности"""
        metrics = context.get("metrics", None)
        result = await self.perf_analyzer.analyze_performance(config_name, metrics)
        return {"status": "success", "analysis": result}

    async def _find_bottlenecks(self, config_name: str, context: Dict) -> Dict:
        """Поиск узких мест"""
        result = await self.perf_analyzer.analyze_performance(config_name)
        return {"status": "success", "bottlenecks": result["bottlenecks"]}

    async def _optimize_query(self, query_info: Dict, context: Dict) -> Dict:
        """Рекомендации по оптимизации запроса"""
        tips = self.perf_analyzer._get_query_optimization_tips(query_info)
        return {"status": "success", "recommendations": tips}

    # ===== Design Tools =====

    async def _generate_diagram(self, architecture: Dict, context: Dict) -> Dict:
        """Генерация архитектурной диаграммы"""
        # TODO: Implement with real architect assistant
        return {"status": "success", "diagram": "graph TD\n  A --> B"}

    async def _analyze_requirements(
        self, requirements_text: str, context: Dict
    ) -> Dict:
        """Анализ требований"""
        # TODO: Implement with real architect assistant
        return {"status": "success", "requirements": []}

    async def _assess_risks(self, architecture: Dict, context: Dict) -> Dict:
        """Оценка рисков"""
        # TODO: Implement with real architect assistant
        return {"status": "success", "risks": []}

    # ===== Integration Architecture Tools =====

    async def _design_integration(self, systems: List[Dict], context: Dict) -> Dict:
        """Проектирование интеграционной архитектуры"""
        # TODO: Full implementation
        return {
            "status": "success",
            "integration_architecture": {"flows": [], "diagram": ""},
        }

    async def _generate_api_spec(self, api_info: Dict, context: Dict) -> Dict:
        """Генерация OpenAPI спецификации"""
        # TODO: Implement
        return {"status": "success", "openapi_spec": {}}

    # ===== SQL Optimization Tools =====

    async def _optimize_sql(self, query: str, context: Dict) -> Dict:
        """Оптимизация SQL запроса"""
        result = await self.sql_optimizer.optimize_query(query, context)
        return {"status": "success", "optimization": result}

    async def _detect_sql_antipatterns(self, query: str, context: Dict) -> Dict:
        """Детекция SQL anti-patterns"""
        patterns = await self.sql_optimizer._detect_sql_anti_patterns(query)
        return {"status": "success", "anti_patterns": patterns, "count": len(patterns)}

    async def _recommend_indexes(self, query: str, context: Dict) -> Dict:
        """Рекомендации по индексам"""
        structure = await self.sql_optimizer._analyze_query_structure(query)
        indexes = await self.sql_optimizer._recommend_indexes(query, structure, context)
        return {
            "status": "success",
            "index_recommendations": [
                {
                    "table": idx.table,
                    "columns": idx.columns,
                    "type": idx.index_type,
                    "create_statement": idx.create_statement,
                    "speedup": idx.estimated_speedup,
                }
                for idx in indexes
            ],
        }

    async def _optimize_1c_query(self, query_1c: str, context: Dict) -> Dict:
        """Оптимизация запроса на языке 1С"""
        result = await self.sql_optimizer.optimize_1c_query(query_1c, context)
        return {"status": "success", "optimization": result}

    async def _recommend_db_config(self, database_type: str, context: Dict) -> Dict:
        """Рекомендации по конфигурации БД"""
        resources = context.get(
            "resources", {"ram_gb": 16, "cpu_cores": 8, "ssd": True}
        )
        result = await self.sql_optimizer.recommend_database_config(
            database_type, resources
        )
        return {"status": "success", "config": result}

    # ===== 1C Server Optimization Tools =====

    async def _optimize_1c_server(self, current_config: Dict, context: Dict) -> Dict:
        """Оптимизация сервера 1С"""
        workload = context.get("workload", {})
        result = await self.server_optimizer.optimize_server_config(
            current_config, workload
        )
        return {"status": "success", "optimization": result}

    async def _tune_working_processes(self, users_count: int, context: Dict) -> Dict:
        """Расчет оптимального количества рабочих процессов"""
        # Formula from Infostart
        recommended = max(users_count // 10, 2)

        return {
            "status": "success",
            "current_users": users_count,
            "recommended_processes": recommended,
            "rationale": f"Formula: users / 10 = {users_count} / 10 = {recommended}",
            "source": "Infostart.ru + ITS",
        }

    # ===== Server Lifecycle =====

    async def handle_request(self, tool_name: str, args: Dict) -> Dict:
        """Обработка MCP запроса"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            handler = self.tools[tool_name]

            # Extract arguments
            main_arg = args.get("main_arg", "")
            context = args.get("context", {})

            # Call handler
            result = await handler(main_arg, context)
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
        """Запуск MCP Server для архитектора"""
        logger.info(
            "Starting Architect MCP Server",
            extra={"host": self.host, "port": self.port},
        )

        print("=" * 70)
        print("AI Architect MCP Server Started")
        print(f"Port: {self.port}")
        print(f"Tools: {len(self.tools)}")
        print("=" * 70)
        print("\nAvailable Tools (25):\n")
        print("Graph Analysis (4):")
        print("  - arch:analyze_graph")
        print("  - arch:find_cycles")
        print("  - arch:find_god_objects")
        print("  - arch:calculate_coupling")
        print("\nADR (3):")
        print("  - arch:generate_adr")
        print("  - arch:list_adrs")
        print("  - arch:get_adr")
        print("\nAnti-Patterns (3):")
        print("  - arch:detect_anti_patterns")
        print("  - arch:get_quality_score")
        print("  - arch:refactoring_roadmap")
        print("\nTechnology (2):")
        print("  - arch:recommend_tech_stack")
        print("  - arch:compare_technologies")
        print("\nPerformance (3):")
        print("  - arch:analyze_performance")
        print("  - arch:find_bottlenecks")
        print("  - arch:optimize_query")
        print("\nDesign (3):")
        print("  - arch:generate_diagram")
        print("  - arch:analyze_requirements")
        print("  - arch:assess_risks")
        print("\nSQL Optimization (5) NEW!:")
        print("  - arch:optimize_sql")
        print("  - arch:detect_sql_antipatterns")
        print("  - arch:recommend_indexes")
        print("  - arch:optimize_1c_query")
        print("  - arch:recommend_db_config")
        print("\n1C Server (2) NEW!:")
        print("  - arch:optimize_1c_server")
        print("  - arch:tune_working_processes")
        print("\n" + "=" * 70)
        print("Ready for connections!")
        print("=" * 70)


# Example usage
if __name__ == "__main__":
    server = ArchitectMCPServer()
    server.start()

    # Test request
    async def test():
        # Test graph analysis
        result = await server.handle_request(
            "arch:analyze_graph",
            {"main_arg": "ERP", "context": {"deep_analysis": True}},
        )
        print("\n=== Graph Analysis Test ===")
        print(f"Status: {result.get('status')}")

        # Test anti-pattern detection
        result = await server.handle_request(
            "arch:detect_anti_patterns", {"main_arg": "ERP", "context": {}}
        )
        print("\n=== Anti-Pattern Detection Test ===")
        print(
            f"Quality Score: {result.get('analysis', {}).get('overall_score', 'N/A')}"
        )

    asyncio.run(test())
