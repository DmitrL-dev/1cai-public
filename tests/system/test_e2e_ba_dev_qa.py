
"""
E2E: Business Analyst → Developer AI Secure → QA Engineer AI

Сценарий:
1. BA формирует артефакт требований.
2. Developer AI Secure генерирует BSL‑код и токен (Rule-of-Two).
3. QA Engineer AI генерирует тесты и оценку покрытия по сгенерированному коду.

Тест моделирует поток с помощью простых объектов и моков без реальных LLM/HTTP.
"""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_e2e_ba_dev_qa_flow():
    # 1. BA requirements (упрощённый артефакт)
    ba_requirements = {
        "business_goal": "Рассчитать скидку клиента в зависимости от уровня лояльности",
        "acceptance_criteria": [
            "Для уровня 'Gold' скидка 10%",
            "Для уровня 'Silver' скидка 5%",
            "Для остальных скидка 0%",
        ],
        "business_rules": [
            "Скидка не может быть отрицательной",
            "Скидка не может превышать 20%",
        ],
    }

    # 2. Developer AI Secure: генерирует BSL‑код по требованиям
    from src.ai.agents.developer_agent_secure import DeveloperAISecure

    dev_agent = DeveloperAISecure()

    bsl_code = """
Функция РассчитатьСкидку(УровеньЛояльности, Сумма)
    Если УровеньЛояльности = "Gold" Тогда
        Скидка = Сумма * 0.10;
    ИначеЕсли УровеньЛояльности = "Silver" Тогда
        Скидка = Сумма * 0.05;
    Иначе
        Скидка = 0;
    КонецЕсли;

    Если Скидка < 0 Тогда
        Скидка = 0;
    КонецЕсли;

    Если Скидка > Сумма * 0.20 Тогда
        Скидка = Сумма * 0.20;
    КонецЕсли;

    Возврат Скидка;
КонецФункции
""".strip()

    async def fake_generate_code(prompt: str):
        assert "скидку" in prompt.lower()
        return {
            "code": bsl_code,
            "token": "secure-token-123",
            "requires_approval": True,
        }

    with patch.object(
        dev_agent, "generate_code", new=AsyncMock(side_effect=fake_generate_code)
    ):
        draft = await dev_agent.generate_code(ba_requirements["business_goal"])

    assert draft["requires_approval"] is True
    assert isinstance(draft["token"], str) and draft["token"]
    assert "Функция РассчитатьСкидку" in draft["code"]

    # 3. QA Engineer AI: генерирует тесты по сгенерированному коду
    from src.ai.agents.qa_engineer_agent_extended import QAEngineerAgentExtended

    qa_agent = QAEngineerAgentExtended()

    async def fake_generate_tests(code: str, function_name: str):
        assert "РассчитатьСкидку" in function_name
        assert "Функция РассчитатьСкидку" in code
        return {
            "tests": {
                "unit_tests": [
                    {
                        "name": "test_gold_discount",
                        "input": {"УровеньЛояльности": "Gold", "Сумма": 1000},
                        "expected": 100,
                    }
                ],
                "vanessa_bdd": [
                    {
                        "scenario": "Расчёт скидки для уровня Gold",
                        "given": "есть клиент уровня Gold",
                        "when": "он оформляет заказ на 1000",
                        "then": "скидка составляет 100",
                    }
                ],
                "negative_tests": [
                    {
                        "name": "test_negative_sum",
                        "description": "Сумма не должна быть отрицательной, скидка обнуляется",
                    }
                ],
            },
            "coverage_estimate": 0.75,
        }

    with patch.object(
        qa_agent, "generate_tests", new=AsyncMock(side_effect=fake_generate_tests)
    ):
        qa_result = await qa_agent.generate_tests(draft["code"], "РассчитатьСкидку")

    tests = qa_result["tests"]
    assert tests["unit_tests"], "Ожидается хотя бы один unit‑тест"
    assert tests["vanessa_bdd"], "Ожидается хотя бы один Vanessa BDD сценарий"
    assert tests["negative_tests"], "Ожидается хотя бы один негативный сценарий"

    coverage = qa_result["coverage_estimate"]
    assert 0 < coverage <= 1, "coverage_estimate должен быть в диапазоне (0, 1]"
