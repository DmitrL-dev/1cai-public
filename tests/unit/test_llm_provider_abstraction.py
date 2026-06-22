"""
Tests for LLM Provider Abstraction (llm_provider_abstraction.py).
"""


from src.ai.llm_provider_abstraction import (
    LLMProviderAbstraction,
    ModelProfile,
    QueryType,
    RiskLevel,
)


def test_model_profile_to_dict() -> None:
    """Тест конвертации ModelProfile в словарь."""
    profile = ModelProfile(
        provider_id="test",
        model_name="test-model",
        capabilities={QueryType.CODE_GENERATION},
        risk_level=RiskLevel.LOW,
        cost_per_1k_tokens=0.01,
        avg_latency_ms=1000,
    )

    data = profile.to_dict()
    assert data["provider_id"] == "test"
    assert data["model_name"] == "test-model"
    assert QueryType.CODE_GENERATION.value in data["capabilities"]
    assert data["risk_level"] == "low"


def test_model_profile_from_dict() -> None:
    """Тест создания ModelProfile из словаря."""
    data = {
        "provider_id": "test",
        "model_name": "test-model",
        "capabilities": ["code_generation"],
        "risk_level": "low",
        "cost_per_1k_tokens": 0.01,
        "avg_latency_ms": 1000,
    }

    profile = ModelProfile.from_dict(data)
    assert profile.provider_id == "test"
    assert profile.model_name == "test-model"
    assert QueryType.CODE_GENERATION in profile.capabilities
    assert profile.risk_level == RiskLevel.LOW


def test_llm_provider_abstraction_init() -> None:
    """Тест инициализации LLMProviderAbstraction."""
    abstraction = LLMProviderAbstraction()
    assert len(abstraction.profiles) > 0


def test_register_profile() -> None:
    """Тест регистрации профиля."""
    abstraction = LLMProviderAbstraction()
    initial_count = len(abstraction.profiles)

    profile = ModelProfile(
        provider_id="custom",
        model_name="custom-model",
        capabilities={QueryType.GENERAL},
    )
    abstraction.register_profile(profile)

    assert len(abstraction.profiles) == initial_count + 1
    assert abstraction.get_profile("custom", "custom-model") == profile


def test_select_provider_by_query_type() -> None:
    """Тест выбора провайдера по типу запроса."""
    abstraction = LLMProviderAbstraction()

    # Выбрать провайдера для генерации кода
    profile = abstraction.select_provider(QueryType.CODE_GENERATION)
    assert profile is not None
    assert QueryType.CODE_GENERATION in profile.capabilities


def test_select_provider_with_cost_constraint() -> None:
    """Тест выбора провайдера с ограничением по стоимости."""
    abstraction = LLMProviderAbstraction()

    # Выбрать провайдера с максимальной стоимостью 0.005
    profile = abstraction.select_provider(
        QueryType.GENERAL,
        max_cost=0.005,
    )
    assert profile is not None
    assert profile.cost_per_1k_tokens <= 0.005


def test_select_provider_with_latency_constraint() -> None:
    """Тест выбора провайдера с ограничением по latency."""
    abstraction = LLMProviderAbstraction()

    # Выбрать провайдера с максимальной latency 1500ms
    profile = abstraction.select_provider(
        QueryType.GENERAL,
        max_latency_ms=1500,
    )
    assert profile is not None
    assert profile.avg_latency_ms <= 1500


def test_select_provider_with_compliance() -> None:
    """Тест выбора провайдера с требованиями compliance."""
    abstraction = LLMProviderAbstraction()

    # Выбрать провайдера с compliance 152-ФЗ
    profile = abstraction.select_provider(
        QueryType.RUSSIAN_TEXT,
        required_compliance=["152-ФЗ"],
    )
    assert profile is not None
    assert "152-ФЗ" in profile.compliance


def test_select_provider_with_risk_level() -> None:
    """Тест выбора провайдера с предпочтительным уровнем риска."""
    abstraction = LLMProviderAbstraction()

    # Выбрать провайдера с низким уровнем риска
    profile = abstraction.select_provider(
        QueryType.CODE_GENERATION,
        preferred_risk_level=RiskLevel.LOW,
    )
    assert profile is not None
    assert profile.risk_level == RiskLevel.LOW


def test_get_profiles_by_capability() -> None:
    """Тест получения профилей по capability."""
    abstraction = LLMProviderAbstraction()

    profiles = abstraction.get_profiles_by_capability(QueryType.CODE_GENERATION)
    assert len(profiles) > 0
    assert all(QueryType.CODE_GENERATION in p.capabilities for p in profiles)


def test_to_tool_registry_format() -> None:
    """Тест конвертации в формат ToolRegistry."""
    abstraction = LLMProviderAbstraction()

    tools = abstraction.to_tool_registry_format()
    assert len(tools) > 0
    assert all("id" in tool for tool in tools)
    assert all("schema" in tool for tool in tools)
    assert all("cost" in tool for tool in tools)
    assert all("risks" in tool for tool in tools)
