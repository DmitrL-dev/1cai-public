import os
from pathlib import Path
from typing import Any

import pytest

os.environ.setdefault("JWT_SECRET", "test-secret-for-local-checks-only-1234567890")

from src.modules.copilot.services.completion_service import CompletionService
from src.modules.copilot.services.copilot_service import CopilotService
from src.modules.copilot.services.generation_service import GenerationService
from src.modules.test_generation.services.generators.js_generator import JSTestGenerator
from src.modules.test_generation.services.generators.python_generator import (
    PythonTestGenerator,
)

IF_LINE = "\u0415\u0441\u043b\u0438 \u0424\u043b\u0430\u0433"
FOR_EACH_LINE = "\u0414\u043b\u044f \u041a\u0430\u0436\u0434\u043e\u0433\u043e"
QUERY_LINE = "\u0417\u0430\u043f\u0440\u043e\u0441"
RESULT_LINE = "\u0420\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442"
END_IF = "\u041a\u043e\u043d\u0435\u0446\u0415\u0441\u043b\u0438"


class _NoModel:
    def is_loaded(self) -> bool:
        return False


def _all_texts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _all_texts(item)]
    if isinstance(value, list):
        return [text for item in value for text in _all_texts(item)]
    return []


@pytest.mark.asyncio
async def test_rule_based_copilot_fallbacks_return_guarded_utf8_snippets():
    completion_service = CompletionService(_NoModel())
    legacy_service = CopilotService()

    suggestions = []
    for line in (IF_LINE, FOR_EACH_LINE, QUERY_LINE, RESULT_LINE):
        suggestions.extend(await completion_service.get_completions("", line, 5))
    for line in (FOR_EACH_LINE, QUERY_LINE, RESULT_LINE):
        suggestions.extend(await legacy_service.get_completions("", line, 5))

    texts = _all_texts(suggestions)

    assert suggestions
    assert any(END_IF in text for text in texts)
    assert any("RENTGEN-GUARD" in text for text in texts)
    assert all("TODO" not in text for text in texts)


@pytest.mark.asyncio
async def test_python_and_js_test_generators_do_not_emit_todo_assertions():
    python_tests = await PythonTestGenerator().generate(
        "def build_total(value):\n    return value\n",
        include_edge_cases=True,
    )
    js_tests = await JSTestGenerator().generate(
        "function buildTotal(input) { return input }\n",
        include_edge_cases=True,
    )

    texts = _all_texts(python_tests + js_tests)

    assert python_tests
    assert js_tests
    assert all("TODO" not in text for text in texts)
    assert any('assert type(result).__name__ != "NoneType"' in text for text in texts)
    assert any("expect(result).not.toBeNull();" in text for text in texts)


@pytest.mark.asyncio
async def test_copilot_unknown_generation_type_returns_guarded_contract():
    generation_service = GenerationService(_NoModel())

    code = await generation_service.generate_code("Сделай обработчик", "unknown")

    assert "RENTGEN-GUARD" in code
    assert "Generated code for" not in code
    assert "Implementation needed" not in code
    assert "TODO" not in code


def test_bsl_editor_default_sample_does_not_show_todo_placeholder():
    root = Path(__file__).resolve().parents[2]
    source = (root / "portal/src/components/BslEditor.tsx").read_text(encoding="utf-8")

    assert "// TODO" not in source
    assert "RENTGEN-GUARD" in source
