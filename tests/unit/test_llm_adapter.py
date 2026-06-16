"""Tests for src.ai.llm_adapter — BSL ↔ rlm-toolkit bridge."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


# ── Fake rlm-toolkit stubs (injected before import) ──────────────


@dataclass
class FakeLLMResponse:
    content: str = ""
    model: str = "test-model"


class FakeResilientProvider:
    """Minimal stand-in for rlm_toolkit.providers.base.ResilientProvider."""

    def __init__(self, **kwargs):
        self.model = kwargs.get("model", "fake-model")
        self._last_cost = kwargs.get("cost", 0.001)

    def generate(self, prompt, system_prompt=None, max_tokens=None, temperature=0.0):
        return FakeLLMResponse(content="Найдены проблемы", model=self.model)

    def get_cost(self, response):
        return self._last_cost


class FakeOllamaProvider(FakeResilientProvider):
    def __init__(self, model="qwen3:4b", base_url="http://localhost:11434", **kw):
        super().__init__(model=model, **kw)
        self.base_url = base_url


class FakeOpenAIProvider(FakeResilientProvider):
    def __init__(self, model="gpt-4o-mini", api_key=None, **kw):
        super().__init__(model=model, **kw)
        self.api_key = api_key


class FakeAnthropicProvider(FakeResilientProvider):
    def __init__(self, model="claude-3.5-sonnet", api_key=None, **kw):
        super().__init__(model=model, **kw)
        self.api_key = api_key


@pytest.fixture(autouse=True)
def _inject_rlm_toolkit():
    """Inject fake rlm_toolkit modules into sys.modules before each test."""
    base_mod = types.ModuleType("rlm_toolkit.providers.base")
    base_mod.ResilientProvider = FakeResilientProvider
    base_mod.LLMResponse = FakeLLMResponse

    providers_mod = types.ModuleType("rlm_toolkit.providers")
    providers_mod.OllamaProvider = FakeOllamaProvider
    providers_mod.OpenAIProvider = FakeOpenAIProvider
    providers_mod.AnthropicProvider = FakeAnthropicProvider

    rlm_mod = types.ModuleType("rlm_toolkit")

    saved = {}
    mod_names = ["rlm_toolkit", "rlm_toolkit.providers", "rlm_toolkit.providers.base"]
    mods = [rlm_mod, providers_mod, base_mod]

    for name, mod in zip(mod_names, mods):
        saved[name] = sys.modules.get(name)
        sys.modules[name] = mod

    # Also clear cached import of llm_adapter so it re-imports with fakes
    adapter_key = "src.ai.llm_adapter"
    saved[adapter_key] = sys.modules.pop(adapter_key, None)

    yield

    # Restore original state
    for name in mod_names + [adapter_key]:
        prev = saved.get(name)
        if prev is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = prev


def _import_adapter():
    """Import (or re-import) llm_adapter with fake rlm_toolkit in place."""
    import importlib

    mod = importlib.import_module("src.ai.llm_adapter")
    importlib.reload(mod)  # ensure fresh with current sys.modules
    return mod


# ── Tests ─────────────────────────────────────────────────────────


class TestBSLReviewProvider:
    """Tests for BSLReviewProvider core behaviour."""

    def test_review_returns_string(self):
        adapter = _import_adapter()
        provider = FakeResilientProvider(model="test-model")
        reviewer = adapter.BSLReviewProvider(provider)

        result = reviewer.review("Процедура Тест() КонецПроцедуры", {"complexity": 0.8})

        assert isinstance(result, str)
        assert len(result) > 0

    def test_review_calls_generate_with_prompts(self):
        adapter = _import_adapter()
        provider = FakeResilientProvider(model="test-model")
        provider.generate = MagicMock(
            return_value=FakeLLMResponse(content="ok", model="test-model")
        )
        reviewer = adapter.BSLReviewProvider(provider)

        reviewer.review("Функция Ф() КонецФункции", {"n_plus_one": 0.9})

        provider.generate.assert_called_once()
        call_kwargs = provider.generate.call_args
        # system_prompt should be the Russian BSL review prompt
        assert call_kwargs.kwargs.get("system_prompt") or call_kwargs[1].get(
            "system_prompt"
        )
        # prompt (positional or kwarg) should contain the code
        prompt_arg = call_kwargs.kwargs.get("prompt") or call_kwargs[0][0]
        assert "Функция Ф()" in prompt_arg
        assert "n_plus_one" in prompt_arg

    def test_model_name_property(self):
        adapter = _import_adapter()
        provider = FakeResilientProvider(model="qwen3:4b")
        reviewer = adapter.BSLReviewProvider(provider)

        assert reviewer.model_name == "qwen3:4b"

    def test_cost_tracking(self):
        adapter = _import_adapter()
        provider = FakeResilientProvider(model="gpt-4o", cost=0.005)
        reviewer = adapter.BSLReviewProvider(provider)

        assert reviewer.total_cost == 0.0

        reviewer.review("Процедура А() КонецПроцедуры", {"quality": 0.5})
        assert reviewer.total_cost == pytest.approx(0.005)

        reviewer.review("Процедура Б() КонецПроцедуры", {"quality": 0.3})
        assert reviewer.total_cost == pytest.approx(0.010)

    def test_cost_tracking_graceful_when_unsupported(self):
        """Provider without get_cost should not crash."""
        adapter = _import_adapter()

        class NoCostProvider:
            """Provider that lacks get_cost entirely."""

            def __init__(self):
                self.model = "no-cost"

            def generate(
                self, prompt, system_prompt=None, max_tokens=None, temperature=0.0
            ):
                return FakeLLMResponse(content="Найдены проблемы", model=self.model)

        provider = NoCostProvider()
        reviewer = adapter.BSLReviewProvider(provider)

        result = reviewer.review("Код()", {"score": 1.0})
        assert result == "Найдены проблемы"
        assert reviewer.total_cost == 0.0


class TestSystemPrompt:
    """Verify the system prompt contains expected Russian keywords."""

    def test_prompt_contains_russian_terms(self):
        adapter = _import_adapter()
        prompt = adapter.BSL_REVIEW_SYSTEM_PROMPT

        assert "1С" in prompt
        assert "BSL" in prompt
        assert "N+1" in prompt
        assert "Попытка" in prompt or "Исключение" in prompt
        assert "магические" in prompt.lower() or "магических" in prompt.lower()
        assert "вложенность" in prompt.lower() or "вложенности" in prompt.lower()
        assert "русском" in prompt.lower()


class TestFactoryFunctions:
    """Tests for from_ollama / from_openai / from_anthropic."""

    def test_from_ollama_default(self):
        adapter = _import_adapter()
        reviewer = adapter.from_ollama()

        assert reviewer.model_name == "qwen3:4b"
        assert isinstance(reviewer, adapter.BSLReviewProvider)

    def test_from_ollama_custom(self):
        adapter = _import_adapter()
        reviewer = adapter.from_ollama(model="llama3:8b", base_url="http://gpu:11434")

        assert reviewer.model_name == "llama3:8b"
        assert reviewer._provider.base_url == "http://gpu:11434"

    def test_from_openai(self):
        adapter = _import_adapter()
        reviewer = adapter.from_openai(model="gpt-4o", api_key="sk-test")

        assert reviewer.model_name == "gpt-4o"
        assert reviewer._provider.api_key == "sk-test"

    def test_from_anthropic(self):
        adapter = _import_adapter()
        reviewer = adapter.from_anthropic(model="claude-3.5-sonnet", api_key="ant-key")

        assert reviewer.model_name == "claude-3.5-sonnet"
        assert reviewer._provider.api_key == "ant-key"
