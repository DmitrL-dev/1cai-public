import pytest

from src.ai.role_based_router import RoleBasedRouter, UserRole


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("role", "query"),
    [
        (UserRole.DEVELOPER, "Проверь запрос и предложи безопасный fix"),
        (UserRole.BUSINESS_ANALYST, "Разложи требования и acceptance criteria"),
        (UserRole.QA_ENGINEER, "Собери план регрессионных тестов"),
        (UserRole.ARCHITECT, "Оцени архитектурные зависимости конфигурации"),
        (UserRole.DEVOPS, "Разбери логи и pipeline релиза"),
        (UserRole.TECHNICAL_WRITER, "Подготовь документацию для релиза"),
    ],
)
async def test_router_offline_contract_is_honest_for_every_role(
    monkeypatch, role, query
):
    router = RoleBasedRouter()
    for attr in ("qwen_client", "ba_agent", "qa_agent", "devops_agent", "tw_agent"):
        monkeypatch.setattr(router, attr, None, raising=False)

    result = await router.route_query(query, context={"role": role.value})
    serialized = str(result).lower()

    assert result["role"] == role.value
    assert result["agent"] == "local-role-router"
    assert result["mode"] == "offline_role_router"
    assert result["coverage"] == "local_router_with_context"
    assert result["recommended_actions"]
    assert result["required_evidence"]
    assert "placeholder" not in serialized
    assert "integration pending" not in serialized


class BrokenQwenClient:
    async def generate_code(self, query, context):
        raise RuntimeError("backend unavailable")


@pytest.mark.asyncio
async def test_router_falls_back_to_local_contract_when_primary_agent_fails(
    monkeypatch,
):
    router = RoleBasedRouter()
    monkeypatch.setattr(router, "qwen_client", BrokenQwenClient(), raising=False)

    result = await router.route_query(
        "Напиши функцию расчёта скидки",
        context={"role": UserRole.DEVELOPER.value, "current_file": "module.bsl"},
    )

    assert result["agent"] == "local-role-router"
    assert result["mode"] == "offline_role_router"
    assert "qwen3-coder" in result["unavailable_integrations"]
    assert result["context_keys"] == ["current_file", "role"]
