import pytest

from src.ai.role_based_router import RoleBasedRouter, UserRole


class DummyAgent:
    def __init__(self):
        self.calls = []

    async def generate_tests(self, code: str, function_name: str):
        self.calls.append(("tests", code, function_name))
        return {"tests": {"unit_tests": []}}

    async def analyze_coverage(self, config_name: str):
        self.calls.append(("coverage", config_name))
        return {"coverage": 80}

    async def generate_code(self, prompt: str, context=None):
        self.calls.append(("developer", prompt))
        return {
            "success": True,
            "suggestion": "pass",
            "requires_approval": True,
            "token": "tok",
        }


@pytest.mark.asyncio
async def test_router_routes_qa(monkeypatch):
    router = RoleBasedRouter()
    dummy = DummyAgent()
    monkeypatch.setattr(router, "qa_agent", dummy)
    monkeypatch.setattr(router, "qwen_client", None, raising=False)

    await router.route_query("Прошу покрытие и тесты для функции возврата", context={})

    assert dummy.calls and dummy.calls[0][0] in {"tests", "coverage"}


@pytest.mark.asyncio
async def test_router_routes_developer(monkeypatch):
    router = RoleBasedRouter()
    dummy = DummyAgent()
    monkeypatch.setattr(router, "qwen_client", dummy, raising=False)

    response = await router.route_query(
        "Напиши функцию расчёта налогов", context={"current_file": "module.bsl"}
    )

    assert dummy.calls and dummy.calls[0][0] == "developer"
    assert response["role"] == UserRole.DEVELOPER.value
    assert response["response"]["token"] == "tok"
