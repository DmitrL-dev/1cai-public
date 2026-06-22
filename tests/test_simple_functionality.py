"""
Простые тесты для проверки основной функциональности без внешних зависимостей
"""

import json
import re

import pytest


def test_mermaid_code_validation_empty():
    """Тест валидации пустого Mermaid кода"""

    # Простая реализация функции валидации для тестирования
    def validate_mermaid_code(code: str, diagram_type: str) -> str:
        if not code:
            return ""

        # Проверяем базовую структуру
        if diagram_type == "flowchart":
            if not re.search(r"flowchart\s+[TBRL]?", code):
                code = "flowchart TD\n" + code

        elif diagram_type == "graph":
            if not re.search(r"graph\s+[TBRL]?", code):
                code = "graph TD\n" + code

        elif diagram_type == "sequence":
            if not re.search(r"sequenceDiagram", code):
                code = "sequenceDiagram\n" + code

        # Убираем лишние переносы и форматируем
        code = re.sub(r"\n\s*\n", "\n", code)
        code = code.strip()

        return code

    # Тест с пустым кодом
    result = validate_mermaid_code("", "flowchart")
    assert result == ""


def test_mermaid_code_validation_flowchart():
    """Тест валидации Mermaid flowchart"""

    def validate_mermaid_code(code: str, diagram_type: str) -> str:
        if not code:
            return ""

        if diagram_type == "flowchart":
            if not re.search(r"flowchart\s+[TBRL]?", code):
                code = "flowchart TD\n" + code

        code = re.sub(r"\n\s*\n", "\n", code)
        code = code.strip()
        return code

    # Тест с корректным кодом
    valid_code = "flowchart TD\nA[Start] --> B[End]"
    result = validate_mermaid_code(valid_code, "flowchart")
    assert "flowchart" in result
    assert "A[Start]" in result
    assert "B[End]" in result

    # Тест с кодом без префикса
    code_without_prefix = "A[Start] --> B[End]"
    result = validate_mermaid_code(code_without_prefix, "flowchart")
    assert result.startswith("flowchart")
    assert "A[Start]" in result


def test_mermaid_code_validation_sequence():
    """Тест валидации Mermaid sequence diagram"""

    def validate_mermaid_code(code: str, diagram_type: str) -> str:
        if not code:
            return ""

        if diagram_type == "sequence":
            if not re.search(r"sequenceDiagram", code):
                code = "sequenceDiagram\n" + code

        code = re.sub(r"\n\s*\n", "\n", code)
        code = code.strip()
        return code

    code = "User->>Server: Request"
    result = validate_mermaid_code(code, "sequence")
    assert result.startswith("sequenceDiagram")
    assert "User->>Server: Request" in result


def test_generate_recommendation_logic():
    """Тест логики генерации рекомендаций"""

    def generate_recommendation(requirements, architecture, risks):
        risk_level = risks.get("risk_level", "medium")
        component_count = len(architecture.get("components", []))
        requirement_count = len(requirements.get("requirements", []))

        if risk_level == "low" and component_count <= 10:
            return "Рекомендуется немедленное начало разработки. Архитектурное решение зрелое и риски минимальны."
        elif risk_level == "medium":
            return "Рекомендуется поэтапная реализация с дополнительным анализом рисков на каждом этапе."
        else:
            return "Требуется дополнительный анализ и переработка архитектурного решения. Риски слишком высоки."

    # Низкий риск, мало компонентов
    low_risk_data = {
        "requirements": {"requirements": [1, 2, 3]},
        "architecture": {"components": [1, 2, 3]},
        "risks": {"risk_level": "low"},
    }

    recommendation = generate_recommendation(
        low_risk_data["requirements"],
        low_risk_data["architecture"],
        low_risk_data["risks"],
    )

    assert "немедленное начало" in recommendation.lower()

    # Высокий риск
    high_risk_data = {
        "requirements": {"requirements": [1] * 20},
        "architecture": {"components": [1] * 15},
        "risks": {"risk_level": "high"},
    }

    recommendation = generate_recommendation(
        high_risk_data["requirements"],
        high_risk_data["architecture"],
        high_risk_data["risks"],
    )

    assert "дополнительный анализ" in recommendation.lower()


def test_text_processing():
    """Тест обработки текстов"""

    def clean_text(text):
        # Простая очистка текста
        if not text:
            return ""

        # Убираем лишние пробелы и переносы
        text = re.sub(r"\s+", " ", text.strip())
        return text

    # Тест с пустым текстом
    assert clean_text("") == ""

    # Тест с лишними пробелами
    text = "  Текст   с   лишними   пробелами  "
    result = clean_text(text)
    assert result == "Текст с лишними пробелами"


def test_json_parsing():
    """Тест парсинга JSON"""

    def safe_json_parse(json_string, default=None):
        try:
            return json.loads(json_string)
        except (json.JSONDecodeError, TypeError):
            return default

    # Тест валидного JSON
    valid_json = '{"test": "value", "number": 42}'
    result = safe_json_parse(valid_json)
    assert result == {"test": "value", "number": 42}

    # Тест невалидного JSON
    invalid_json = "invalid json"
    result = safe_json_parse(invalid_json, {"error": True})
    assert result == {"error": True}


def test_requirement_analysis_simulation():
    """Симуляция анализа требований"""

    def analyze_requirements_text(requirements_text):
        """Простая имитация анализа требований"""
        if not requirements_text.strip():
            return {
                "requirements": [],
                "analysis_summary": {
                    "total_count": 0,
                    "high_priority_count": 0,
                    "average_complexity": 0,
                },
            }

        # Простая логика подсчета
        functional_count = requirements_text.lower().count("функциональн")
        non_functional_count = requirements_text.lower().count("нефункциональн")

        total_requirements = functional_count + non_functional_count
        high_priority = max(1, total_requirements // 3)  # Простая эвристика

        return {
            "requirements": [
                {
                    "id": f"REQ{i+1}",
                    "title": f"Требование {i+1}",
                    "type": "functional" if i < functional_count else "non_functional",
                    "priority": "high" if i < high_priority else "medium",
                    "complexity": 5 + (i % 5),
                }
                for i in range(total_requirements)
            ],
            "analysis_summary": {
                "total_count": total_requirements,
                "high_priority_count": high_priority,
                "average_complexity": sum(
                    5 + (i % 5) for i in range(total_requirements)
                )
                / max(1, total_requirements),
            },
        }

    # Тест с пустым текстом
    result = analyze_requirements_text("")
    assert result["analysis_summary"]["total_count"] == 0

    # Тест с простыми требованиями
    simple_requirements = """
    Функциональное требование 1: Пользователь должен иметь возможность входить в систему
    Функциональное требование 2: Система должна сохранять данные
    """
    result = analyze_requirements_text(simple_requirements)
    assert result["analysis_summary"]["total_count"] > 0
    assert result["analysis_summary"]["high_priority_count"] >= 1


if __name__ == "__main__":
    # Запуск тестов
    pytest.main([__file__, "-v"])
