"""
MCP Server для AI Архитектора - Полный функционал
Все возможности архитектора через MCP protocol
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import re
from typing import Any, Dict, List, Optional

from src.ai.agents.architect_agent_extended import ArchitectAgentExtended
from src.ai.agents.onec_server_optimizer import OneCServerOptimizer
from src.ai.agents.performance_analyzer import PerformanceAnalyzer
from src.ai.agents.sql_optimizer import SQLOptimizer
from src.ai.agents.technology_selector import TechnologySelector
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


ARCHITECT_CONTRACT = "offline_architecture_evidence_contract"


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

    def _offline_contract(
        self,
        tool: str,
        *,
        status: str = "needs_evidence",
        coverage: str = "no_source_artifacts",
        required_evidence: Optional[List[str]] = None,
        caveats: Optional[List[str]] = None,
        **payload: Any,
    ) -> Dict[str, Any]:
        """Return a truthful local response when no external source is wired."""
        response: Dict[str, Any] = {
            "status": status,
            "mode": ARCHITECT_CONTRACT,
            "tool": tool,
            "coverage": coverage,
            "required_evidence": required_evidence or [],
            "caveats": caveats or [],
        }
        response.update(payload)
        return response

    def _context_list(self, context: Dict, *keys: str) -> List[Dict[str, Any]]:
        for key in keys:
            value = context.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                nested = value.get("items") or value.get("records") or value.get("adrs")
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]
        return []

    def _normalize_adrs(self, adrs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for index, adr in enumerate(adrs, 1):
            adr_id = adr.get("adr_id") or adr.get("id") or adr.get("number")
            normalized.append(
                {
                    "adr_id": str(adr_id or f"ADR-{index:03d}"),
                    "title": str(adr.get("title") or adr.get("name") or "Untitled ADR"),
                    "status": str(adr.get("status") or "unknown"),
                    "date": adr.get("date") or adr.get("created_at"),
                    "decision": adr.get("decision"),
                    "source": adr.get("source") or adr.get("path"),
                }
            )
        return normalized

    def _filter_adrs(
        self, adrs: List[Dict[str, Any]], filter_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if not filter_params:
            return adrs

        status = str(filter_params.get("status") or "").lower()
        query = str(
            filter_params.get("query") or filter_params.get("title") or ""
        ).lower()

        filtered = adrs
        if status:
            filtered = [
                adr
                for adr in filtered
                if str(adr.get("status") or "").lower() == status
            ]
        if query:
            filtered = [
                adr
                for adr in filtered
                if query in str(adr.get("title") or "").lower()
                or query in str(adr.get("decision") or "").lower()
            ]
        return filtered

    def _sanitize_mermaid_id(self, value: Any, fallback: str) -> str:
        candidate = re.sub(r"[^A-Za-z0-9_]", "_", str(value or fallback)).strip("_")
        return candidate or fallback

    def _extract_architecture_components(
        self, architecture: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        raw_components: Any = (
            architecture.get("components")
            or architecture.get("services")
            or architecture.get("systems")
            or architecture.get("nodes")
            or []
        )
        if isinstance(raw_components, dict):
            raw_components = [
                {"id": key, **value}
                if isinstance(value, dict)
                else {"id": key, "name": value}
                for key, value in raw_components.items()
            ]
        if not isinstance(raw_components, list):
            return []

        components = []
        for index, component in enumerate(raw_components, 1):
            if isinstance(component, dict):
                name = (
                    component.get("name")
                    or component.get("id")
                    or component.get("title")
                )
                component_id = component.get("id") or name or f"component_{index}"
                components.append(
                    {
                        **component,
                        "id": str(component_id),
                        "name": str(name or component_id),
                    }
                )
            elif component:
                components.append({"id": str(component), "name": str(component)})
        return components

    def _extract_architecture_flows(
        self, architecture: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        raw_flows: Any = (
            architecture.get("flows")
            or architecture.get("edges")
            or architecture.get("dependencies")
            or architecture.get("integrations")
            or []
        )
        if not isinstance(raw_flows, list):
            return []

        flows = []
        for flow in raw_flows:
            if not isinstance(flow, dict):
                continue
            source = flow.get("source") or flow.get("from") or flow.get("producer")
            target = flow.get("target") or flow.get("to") or flow.get("consumer")
            if not source or not target:
                continue
            flows.append(
                {
                    **flow,
                    "source": str(source),
                    "target": str(target),
                    "label": flow.get("label")
                    or flow.get("type")
                    or flow.get("protocol"),
                }
            )
        return flows

    def _build_mermaid_diagram(
        self, components: List[Dict[str, Any]], flows: List[Dict[str, Any]]
    ) -> str:
        lines = ["graph TD"]
        known_ids = set()

        for index, component in enumerate(components, 1):
            node_id = self._sanitize_mermaid_id(component.get("id"), f"C{index}")
            known_ids.add(str(component.get("id")))
            label = str(
                component.get("name") or component.get("id") or node_id
            ).replace('"', "'")
            lines.append(f'  {node_id}["{label}"]')

        for index, flow in enumerate(flows, 1):
            source = self._sanitize_mermaid_id(flow.get("source"), f"S{index}")
            target = self._sanitize_mermaid_id(flow.get("target"), f"T{index}")
            label = str(flow.get("label") or "").replace('"', "'")
            edge = f"  {source} -->"
            if label:
                edge += f'|"{label}"|'
            edge += f" {target}"
            lines.append(edge)

        return "\n".join(lines)

    def _split_requirement_candidates(self, requirements_text: str) -> List[str]:
        lines = []
        for raw_line in requirements_text.replace(";", "\n").splitlines():
            line = raw_line.strip(" -*\t")
            if line:
                lines.extend(
                    part.strip()
                    for part in re.split(r"(?<=[.!?])\s+", line)
                    if part.strip()
                )
        return [line for line in lines if len(line) >= 8]

    def _classify_requirement(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ["sla", "доступн", "отказ", "резерв"]):
            return "availability"
        if any(
            word in lowered for word in ["быстр", "мс", "сек", "производ", "нагруз"]
        ):
            return "performance"
        if any(
            word in lowered
            for word in ["роль", "прав", "152", "персон", "шифр", "security"]
        ):
            return "security"
        if any(
            word in lowered
            for word in ["интеграц", "api", "обмен", "шина", "kafka", "rabbit"]
        ):
            return "integration"
        if any(
            word in lowered
            for word in ["как пользователь", "должен", "нужно", "требуется"]
        ):
            return "functional"
        return "business"

    def _risk(
        self,
        risk_id: str,
        title: str,
        severity: str,
        evidence: str,
        mitigation: str,
    ) -> Dict[str, Any]:
        return {
            "id": risk_id,
            "title": title,
            "severity": severity,
            "evidence": evidence,
            "mitigation": mitigation,
            "confidence": "heuristic",
        }

    def _system_name(self, system: Dict[str, Any], index: int) -> str:
        return str(system.get("name") or system.get("id") or f"system_{index}")

    def _normalize_endpoint(
        self, endpoint: Dict[str, Any], index: int
    ) -> Dict[str, Any]:
        method = str(endpoint.get("method") or "get").lower()
        path = str(endpoint.get("path") or endpoint.get("url") or f"/operation-{index}")
        summary = str(endpoint.get("summary") or endpoint.get("name") or path)
        return {
            "method": method,
            "path": path if path.startswith("/") else f"/{path}",
            "summary": summary,
            "description": endpoint.get("description") or "",
            "request_schema": endpoint.get("request_schema")
            or endpoint.get("requestBody"),
            "response_schema": endpoint.get("response_schema")
            or endpoint.get("responses"),
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
        source_adrs = self._context_list(context, "adrs", "adr_repository", "decisions")
        if not source_adrs:
            return self._offline_contract(
                "arch:list_adrs",
                adrs=[],
                total=0,
                required_evidence=[
                    "ADR repository export",
                    "docs/architecture ADR files",
                    "database connection with ADR table",
                ],
                caveats=["ADR storage is not configured for this MCP server."],
            )

        normalized = self._normalize_adrs(source_adrs)
        filtered = self._filter_adrs(normalized, filter_params or {})
        return self._offline_contract(
            "arch:list_adrs",
            status="success",
            coverage="context_adrs_only",
            adrs=filtered,
            total=len(filtered),
            caveats=["Only ADR records supplied in request context were analyzed."],
        )

    async def _get_adr(self, adr_id: str, context: Dict) -> Dict:
        """Получить конкретный ADR"""
        source_adrs = self._context_list(context, "adrs", "adr_repository", "decisions")
        normalized = self._normalize_adrs(source_adrs)
        for adr in normalized:
            if adr["adr_id"].lower() == str(adr_id).lower():
                return self._offline_contract(
                    "arch:get_adr",
                    status="success",
                    coverage="context_adrs_only",
                    adr=adr,
                    caveats=[
                        "ADR body is limited to fields supplied in request context."
                    ],
                )

        return self._offline_contract(
            "arch:get_adr",
            status="not_found",
            coverage="context_adrs_only" if normalized else "no_source_artifacts",
            adr=None,
            required_evidence=[
                f"ADR record with id {adr_id}",
                "ADR repository export or database connection",
            ],
            caveats=["No fabricated ADR is returned when the source record is absent."],
        )

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
        if isinstance(tech_list, str):
            technologies = [
                item.strip() for item in re.split(r"[,;\n]", tech_list) if item.strip()
            ]
        else:
            technologies = [
                str(item).strip() for item in tech_list if str(item).strip()
            ]

        if not technologies:
            return self._offline_contract(
                "arch:compare_technologies",
                comparison={"technologies": [], "matrix": []},
                required_evidence=["List of technologies to compare"],
                caveats=["Comparison cannot be built without candidate technologies."],
            )

        catalog_by_name = {
            option.name.lower(): option
            for option in self.tech_selector.tech_catalog.values()
        }
        catalog_by_key = {
            key.lower(): option
            for key, option in self.tech_selector.tech_catalog.items()
        }
        matrix = []
        unknown = []
        for tech in technologies:
            option = catalog_by_name.get(tech.lower()) or catalog_by_key.get(
                tech.lower().replace(" ", "_")
            )
            if not option:
                unknown.append(tech)
                matrix.append(
                    {
                        "technology": tech,
                        "catalog_status": "unknown",
                        "evidence_needed": "Provide catalog attributes: category, maturity, cost, complexity, lock-in.",
                    }
                )
                continue

            matrix.append(
                {
                    "technology": option.name,
                    "catalog_status": "known",
                    "category": option.category,
                    "best_for": option.best_for,
                    "complexity": option.complexity,
                    "cost": option.cost,
                    "maturity": option.maturity,
                    "vendor_lock_in": option.vendor_lock_in,
                    "community_support": option.community_support,
                }
            )

        return self._offline_contract(
            "arch:compare_technologies",
            status="success",
            coverage="local_catalog_only",
            comparison={
                "technologies": technologies,
                "matrix": matrix,
                "unknown_technologies": unknown,
            },
            required_evidence=["Validated cost/licensing and team capability data"]
            if unknown
            else ["Validated cost/licensing and team capability data"],
            caveats=[
                "Scores are based on the local architecture catalog, not a live vendor benchmark.",
                "Unknown technologies are not inferred.",
            ],
        )

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
        if not isinstance(architecture, dict) or not architecture:
            return self._offline_contract(
                "arch:generate_diagram",
                diagram="",
                nodes=[],
                edges=[],
                required_evidence=[
                    "Architecture components",
                    "Dependencies or integration flows",
                ],
                caveats=[
                    "Mermaid diagram is not generated without architecture facts."
                ],
            )

        components = self._extract_architecture_components(architecture)
        flows = self._extract_architecture_flows(architecture)
        if not components and not flows:
            return self._offline_contract(
                "arch:generate_diagram",
                diagram="",
                nodes=[],
                edges=[],
                required_evidence=[
                    "components/services/systems list",
                    "flows/dependencies/integrations list",
                ],
                caveats=["Input does not contain recognizable architecture entities."],
            )

        diagram = self._build_mermaid_diagram(components, flows)
        return self._offline_contract(
            "arch:generate_diagram",
            status="success",
            coverage="declared_components_and_flows",
            diagram=diagram,
            nodes=components,
            edges=flows,
            caveats=["Diagram reflects only facts declared in the request payload."],
        )

    async def _analyze_requirements(
        self, requirements_text: str, context: Dict
    ) -> Dict:
        """Анализ требований"""
        if not requirements_text or not requirements_text.strip():
            return self._offline_contract(
                "arch:analyze_requirements",
                requirements=[],
                summary={"total": 0},
                required_evidence=[
                    "Requirements text, backlog export or stakeholder notes"
                ],
                caveats=["No requirements were supplied for analysis."],
            )

        candidates = self._split_requirement_candidates(requirements_text)
        requirements = [
            {
                "id": f"REQ-{index:03d}",
                "text": candidate,
                "category": self._classify_requirement(candidate),
                "evidence": candidate,
            }
            for index, candidate in enumerate(candidates, 1)
        ]
        by_category: Dict[str, int] = {}
        for requirement in requirements:
            category = requirement["category"]
            by_category[category] = by_category.get(category, 0) + 1

        missing_views = [
            category
            for category in ["availability", "performance", "security", "integration"]
            if category not in by_category
        ]
        return self._offline_contract(
            "arch:analyze_requirements",
            status="success",
            coverage="source_text_extraction",
            requirements=requirements,
            summary={"total": len(requirements), "by_category": by_category},
            required_evidence=[
                f"Clarify {category} requirements" for category in missing_views
            ],
            caveats=[
                "This is deterministic extraction from supplied text; stakeholder intent is not inferred."
            ],
        )

    async def _assess_risks(self, architecture: Dict, context: Dict) -> Dict:
        """Оценка рисков"""
        if not isinstance(architecture, dict) or not architecture:
            return self._offline_contract(
                "arch:assess_risks",
                risks=[],
                summary={"total": 0},
                required_evidence=[
                    "Architecture components",
                    "Integration flows",
                    "NFR/SLA/security constraints",
                ],
                caveats=["Risk assessment requires architecture facts."],
            )

        components = self._extract_architecture_components(architecture)
        flows = self._extract_architecture_flows(architecture)
        risks = []

        if not components:
            risks.append(
                self._risk(
                    "ARCH-RISK-001",
                    "Component boundaries are not declared",
                    "high",
                    "No components/services/systems were found in the input.",
                    "Add ownership, runtime and responsibility for every component.",
                )
            )
        else:
            missing_owner = [
                component["name"]
                for component in components
                if not component.get("owner") and not component.get("team")
            ]
            if missing_owner:
                risks.append(
                    self._risk(
                        "ARCH-RISK-002",
                        "Components without explicit ownership",
                        "medium",
                        ", ".join(missing_owner[:5]),
                        "Assign owner/team and escalation path for each runtime component.",
                    )
                )

        if len(components) > 1 and not flows:
            risks.append(
                self._risk(
                    "ARCH-RISK-003",
                    "Dependencies are not declared",
                    "high",
                    "Multiple components exist but no flows/dependencies are supplied.",
                    "Document sync/async calls, data contracts, retries and failure modes.",
                )
            )

        sync_external = [
            flow
            for flow in flows
            if str(flow.get("mode") or flow.get("type") or "").lower()
            in {"sync", "http", "rest"}
            and str(flow.get("target") or "").lower() not in {"", "internal"}
        ]
        if sync_external:
            risks.append(
                self._risk(
                    "ARCH-RISK-004",
                    "Synchronous external dependencies need resilience proof",
                    "medium",
                    f"{len(sync_external)} declared synchronous/external flows",
                    "Add timeout, retry, circuit breaker, idempotency and fallback policy.",
                )
            )

        nfr = context.get("nfr") or architecture.get("nfr") or {}
        if not nfr:
            risks.append(
                self._risk(
                    "ARCH-RISK-005",
                    "NFR evidence is missing",
                    "medium",
                    "No SLA/performance/security constraints were supplied.",
                    "Collect SLA, RTO/RPO, load profile, data classes and security constraints.",
                )
            )

        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        risks = sorted(
            risks,
            key=lambda item: severity_order.get(item["severity"], 0),
            reverse=True,
        )
        return self._offline_contract(
            "arch:assess_risks",
            status="success",
            coverage="heuristic_from_declared_architecture",
            risks=risks,
            summary={"total": len(risks)},
            required_evidence=[
                "Runtime topology",
                "Load profile",
                "Security classification",
                "Failure-mode test results",
            ],
            caveats=[
                "Risk confidence is heuristic until validated by runtime evidence."
            ],
        )

    # ===== Integration Architecture Tools =====

    async def _design_integration(self, systems: List[Dict], context: Dict) -> Dict:
        """Проектирование интеграционной архитектуры"""
        if not isinstance(systems, list):
            systems = self._context_list(context, "systems", "participants")

        clean_systems = [
            system
            for system in systems
            if isinstance(system, dict) and self._system_name(system, 0)
        ]
        if len(clean_systems) < 2:
            return self._offline_contract(
                "arch:design_integration",
                integration_architecture={
                    "systems": clean_systems,
                    "flows": [],
                    "diagram": "",
                },
                required_evidence=[
                    "At least two participating systems",
                    "Data objects/messages",
                    "Exchange frequency and consistency requirements",
                ],
                caveats=[
                    "Integration architecture cannot be designed from fewer than two systems."
                ],
            )

        declared_flows = self._context_list(context, "flows", "integrations")
        flows = []
        if declared_flows:
            flows = self._extract_architecture_flows({"flows": declared_flows})
        else:
            for index in range(len(clean_systems) - 1):
                flows.append(
                    {
                        "source": self._system_name(clean_systems[index], index + 1),
                        "target": self._system_name(
                            clean_systems[index + 1], index + 2
                        ),
                        "label": "contract_to_define",
                        "status": "candidate",
                    }
                )

        components = [
            {
                "id": self._system_name(system, index),
                "name": self._system_name(system, index),
            }
            for index, system in enumerate(clean_systems, 1)
        ]
        diagram = self._build_mermaid_diagram(components, flows)
        return self._offline_contract(
            "arch:design_integration",
            status="success",
            coverage="declared_systems_with_candidate_flows"
            if not declared_flows
            else "declared_systems_and_flows",
            integration_architecture={
                "systems": clean_systems,
                "flows": flows,
                "diagram": diagram,
                "decisions": [
                    "Define canonical message contracts before implementation.",
                    "Specify retry/idempotency/dead-letter behavior for each async flow.",
                    "Record ownership and support boundaries per system.",
                ],
            },
            required_evidence=[
                "Message schemas",
                "Throughput and latency targets",
                "Security/data classification",
                "Operational ownership",
            ],
            caveats=[
                "Candidate flows are marked explicitly when no declared flows were provided."
            ],
        )

    async def _generate_api_spec(self, api_info: Dict, context: Dict) -> Dict:
        """Генерация OpenAPI спецификации"""
        if not isinstance(api_info, dict) or not api_info:
            return self._offline_contract(
                "arch:generate_api_spec",
                openapi_spec={},
                required_evidence=[
                    "API title/version",
                    "Endpoint list",
                    "Request/response schemas",
                ],
                caveats=["OpenAPI spec is not generated without API facts."],
            )

        endpoints = api_info.get("endpoints") or api_info.get("paths") or []
        if isinstance(endpoints, dict):
            endpoint_list = []
            for path, methods in endpoints.items():
                if isinstance(methods, dict):
                    for method, details in methods.items():
                        details = details if isinstance(details, dict) else {}
                        endpoint_list.append(
                            {"path": path, "method": method, **details}
                        )
                else:
                    endpoint_list.append({"path": path, "method": "get"})
            endpoints = endpoint_list

        if not isinstance(endpoints, list) or not endpoints:
            return self._offline_contract(
                "arch:generate_api_spec",
                openapi_spec={},
                required_evidence=["Endpoint list with HTTP methods and paths"],
                caveats=[
                    "No endpoint facts were supplied; empty OpenAPI would be misleading."
                ],
            )

        paths: Dict[str, Dict[str, Any]] = {}
        for index, endpoint in enumerate(endpoints, 1):
            if not isinstance(endpoint, dict):
                continue
            normalized = self._normalize_endpoint(endpoint, index)
            response_schema = normalized["response_schema"] or {
                "200": {"description": "Successful response"}
            }
            if "200" not in response_schema and isinstance(response_schema, dict):
                response_schema = {"200": {"description": "Successful response"}}
            operation = {
                "summary": normalized["summary"],
                "description": normalized["description"],
                "responses": response_schema,
            }
            if normalized["request_schema"]:
                operation["requestBody"] = normalized["request_schema"]
            paths.setdefault(normalized["path"], {})[normalized["method"]] = operation

        spec = {
            "openapi": "3.0.3",
            "info": {
                "title": str(
                    api_info.get("title") or api_info.get("name") or "Declared API"
                ),
                "version": str(api_info.get("version") or "0.1.0"),
            },
            "paths": paths,
        }
        return self._offline_contract(
            "arch:generate_api_spec",
            status="success",
            coverage="declared_endpoints_only",
            openapi_spec=spec,
            required_evidence=[
                "Validated request/response JSON schemas",
                "Auth scheme",
                "Error model",
            ],
            caveats=[
                "Generated OpenAPI contains only endpoints declared in the request."
            ],
        )

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
        resources = context.get("resources", {})
        result = await self.sql_optimizer.recommend_database_config(
            database_type, resources
        )
        if result.get("status") == "needs_evidence":
            return result
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
