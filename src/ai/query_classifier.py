import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.ai.scenario_hub import ScenarioRiskLevel
from src.micro_swarm.domains import (
    QUERY_INTENT_DOMAIN,
    extract_query_features,
)
from src.micro_swarm.model import MicroModel, MicroModelConfig
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class QueryType(Enum):
    """Types of queries"""

    STANDARD_1C = "standard_1c"
    GRAPH_QUERY = "graph_query"
    CODE_GENERATION = "code_generation"
    SEMANTIC_SEARCH = "semantic_search"
    ARCHITECTURE = "architecture"
    OPTIMIZATION = "optimization"
    UNKNOWN = "unknown"


class AIService(Enum):
    """Available AI services"""

    EXTERNAL_AI = "external_ai"
    QWEN_CODER = "qwen_coder"
    NEO4J = "neo4j"
    QDRANT = "qdrant"
    GIGACHAT = "gigachat"
    OPENAI = "openai"
    NAPARNIK = "naparnik"
    KIMI_K2 = "kimi_k2"
    TABNINE = "tabnine"


@dataclass
class QueryIntent:
    """Query intent analysis result"""

    query_type: QueryType
    confidence: float
    keywords: List[str]
    context_type: Optional[str]
    preferred_services: List[AIService]
    suggested_tools: List[str]


class QueryClassifier:
    """Classifies user queries to determine routing"""

    def __init__(self):
        """Инициализация QueryClassifier с MicroModel + regex fallback."""
        self.llm_abstraction = None
        self._micro_model = None

        # Initialize Micro-Swarm model (zero deps, ~2KB RAM)
        try:
            config = MicroModelConfig(
                n_features=QUERY_INTENT_DOMAIN.n_features,
                n_embd=16,
                n_head=4,
                n_layer=1,
            )
            self._micro_model = MicroModel(config)
            logger.info(
                "QueryClassifier: MicroModel initialized "
                f"({self._micro_model.param_count} params, "
                f"{self._micro_model.memory_bytes} bytes)"
            )
        except Exception as e:
            logger.warning(
                "MicroModel init failed, using regex fallback: %s", e)

        try:
            from src.ai.llm_provider_abstraction import LLMProviderAbstraction

            self.llm_abstraction = LLMProviderAbstraction()
            logger.info("LLM Provider Abstraction initialized")
        except Exception as e:
            logger.debug("LLM Provider Abstraction not available: %s", e)

    # Classification rules
    RULES = {
        QueryType.STANDARD_1C: {
            "keywords": [
                "типовая",
                "типовой",
                "стандартн",
                "в УТ",
                "в ERP",
                "в ЗУП",
                "в БУХ",
                "как сделано",
                "как реализовано",
            ],
            "patterns": [
                r"как\s+(сделано|реализовано)\s+в\s+(УТ|ERP|ЗУП|БУХ)",
                r"типов(ая|ой|ое|ые)\s+",
                r"стандартн(ый|ая|ое|ые)\s+",
            ],
            "services": [
                AIService.NAPARNIK,
                AIService.EXTERNAL_AI,
                AIService.QWEN_CODER,
            ],
        },
        QueryType.UNKNOWN: {
            "keywords": [],
            "patterns": [],
            "services": [AIService.NAPARNIK],
        },
        QueryType.GRAPH_QUERY: {
            "keywords": [
                "зависимости",
                "связи",
                "где используется",
                "кто вызывает",
                "граф",
                "иерархия",
                "найди все связи",
            ],
            "patterns": [
                r"где\s+использу(ется|ют|ется)",
                r"кто\s+вызывает",
                r"найди\s+(все\s+)?(связи|зависимости)",
                r"граф\s+вызовов",
            ],
            "services": [AIService.NEO4J],
        },
        QueryType.CODE_GENERATION: {
            "keywords": [
                "создай",
                "напиши",
                "сгенерируй",
                "добавь",
                "реализуй",
                "функция",
                "процедура",
                "метод",
            ],
            "patterns": [
                r"(создай|напиши|сгенерируй)\s+(функци|процедур)",
                r"реализуй\s+",
                r"добавь\s+(функци|процедур|метод)",
            ],
            "services": [
                AIService.QWEN_CODER,
                AIService.TABNINE,
                AIService.EXTERNAL_AI,
            ],
        },
        QueryType.SEMANTIC_SEARCH: {
            "keywords": [
                "похожий",
                "похожая",
                "подобн",
                "аналогичный",
                "есть ли",
                "найди код",
            ],
            "patterns": [
                r"найди\s+похож",
                r"есть\s+ли\s+(похож|аналог)",
                r"покажи\s+(похож|аналог)",
            ],
            "services": [AIService.QDRANT, AIService.NEO4J],
        },
        QueryType.OPTIMIZATION: {
            "keywords": [
                "оптимизируй",
                "ускорь",
                "улучш",
                "рефакторинг",
                "производительность",
            ],
            "patterns": [
                r"(оптимизируй|улучш|ускор)",
                r"рефакторинг",
                r"как\s+улучшить",
            ],
            "services": [AIService.QWEN_CODER, AIService.NEO4J],
        },
    }

    def classify(self, query: str, context: Dict[str, Any] = None) -> QueryIntent:
        """Classify query with input validation"""
        if not query or not isinstance(query, str):
            logger.warning("Invalid query in classify")
            return QueryIntent(
                query_type=QueryType.UNKNOWN,
                confidence=0.0,
                keywords=[],
                context_type=None,
                preferred_services=[AIService.NAPARNIK],
                suggested_tools=[],
            )

        max_query_length = 10000
        if len(query) > max_query_length:
            query = query[:max_query_length]

        if context is None:
            context = {}

        query_lower = query.lower()
        scores: Dict[QueryType, float] = {}
        matched_keywords: List[str] = []

        # Robust rule matching
        for query_type, rules in self.RULES.items():
            score = 0.0

            # Check keywords
            if "keywords" in rules:
                for keyword in rules["keywords"]:
                    if keyword.lower() in query_lower:
                        score += 1.0
                        matched_keywords.append(keyword)

            # Check patterns
            if "patterns" in rules:
                for pattern in rules["patterns"]:
                    try:
                        if re.search(pattern, query_lower, re.IGNORECASE):
                            score += 2.0
                    except re.error:
                        logger.warning(
                            f"Invalid regex pattern for {query_type}: {pattern}"
                        )

            scores[query_type] = score

        if scores:
            best_type = max(scores, key=scores.get)
            # Normalize confidence
            confidence = (
                min(scores[best_type] / 5.0,
                    1.0) if scores[best_type] > 0 else 0.0
            )

            # Micro-Swarm enhancement: blend model score with regex confidence
            if self._micro_model is not None:
                try:
                    raw_features = extract_query_features(query)
                    features = QUERY_INTENT_DOMAIN.extract(raw_features)
                    model_score, _ = self._micro_model.forward(features)
                    # Blend: model boosts confidence on ambiguous queries
                    if 0.3 < confidence < 0.7:
                        confidence = 0.4 * confidence + 0.6 * model_score
                except Exception as e:
                    logger.debug("MicroModel scoring failed: %s", e)

            if confidence == 0.0:
                best_type = QueryType.UNKNOWN
        else:
            best_type = QueryType.UNKNOWN
            confidence = 0.0

        preferred_services = []
        if best_type != QueryType.UNKNOWN:
            preferred_services = self.RULES[best_type].get("services", [])
        else:
            preferred_services = self.RULES.get(QueryType.UNKNOWN, {}).get(
                "services", []
            )

        suggested_tools: List[str] = []
        try:
            # Robust tool registry loading
            from src.ai.tool_registry_examples import build_example_tool_registry

            registry = build_example_tool_registry()

            if best_type in [QueryType.STANDARD_1C, QueryType.ARCHITECTURE]:
                suggested_tools.append("ba_requirements_extract")
            elif best_type == QueryType.CODE_GENERATION:
                tools = registry.list_tools(
                    risk=ScenarioRiskLevel.NON_PROD_CHANGE)
                suggested_tools.extend([t.id for t in tools])
            elif best_type == QueryType.OPTIMIZATION:
                suggested_tools.append("security_audit")
            elif best_type == QueryType.GRAPH_QUERY:
                suggested_tools.append("scenario_ba_dev_qa")

            if self.llm_abstraction:
                try:
                    llm_tools = self.llm_abstraction.to_tool_registry_format()
                    suggested_tools.extend([tool["id"] for tool in llm_tools])
                except Exception as e:
                    logger.debug(
                        "Failed to add LLM tools to suggestions: %s", e)
        except ImportError:
            logger.debug("Tool registry examples not available")
        except Exception as e:
            logger.warning("Tool suggestions failed", extra={"error": str(e)})

        return QueryIntent(
            query_type=best_type,
            confidence=confidence,
            keywords=matched_keywords,
            context_type=context.get("type") if context else None,
            preferred_services=preferred_services,
            suggested_tools=list(set(suggested_tools)),  # Deduplicate
        )
