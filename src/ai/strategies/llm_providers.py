"""LLM provider strategies with explicit offline-not-configured contracts."""

from typing import Any, Dict

from src.ai.clients.gigachat_client import GigaChatClient, GigaChatConfig
from src.ai.clients.naparnik_client import NaparnikClient, NaparnikConfig
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig
from src.ai.clients.tabnine_client import TabnineClient, TabnineConfig
from src.ai.clients.yandexgpt_client import YandexGPTClient, YandexGPTConfig
from src.ai.strategies.base import AIStrategy
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


def _not_configured(service_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Return a bounded contract when a cloud/local provider lacks credentials."""
    return {
        "status": "llm_provider_not_configured",
        "mode": "offline_provider_contract",
        "provider": service_name,
        "coverage": "no_credentials",
        "response": "",
        "context_keys": sorted(str(key) for key in (context or {}).keys()),
        "caveats": [
            f"{service_name} credentials or endpoint are not configured; no LLM call was made."
        ],
    }


class GigaChatStrategy(AIStrategy):
    """Strategy adapter for configured GigaChat calls."""

    def __init__(self):
        """Initialize the client without failing baseline startup."""
        try:
            self.client = GigaChatClient(config=GigaChatConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """Provider identifier used by the orchestrator."""
        return "gigachat"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a GigaChat request or return an offline provider contract."""
        if not self.is_available:
            return _not_configured(self.service_name, context)

        system_prompt = context.get(
            "system_prompt", "Вы — эксперт-аналитик. Отвечайте на русском языке."
        )
        return await self.client.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=context.get("max_tokens", 4096),
        )


class YandexGPTStrategy(AIStrategy):
    """Strategy adapter for configured YandexGPT calls."""

    def __init__(self):
        """Initialize the client without failing baseline startup."""
        try:
            self.client = YandexGPTClient(config=YandexGPTConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """Provider identifier used by the orchestrator."""
        return "yandexgpt"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a YandexGPT request or return an offline provider contract."""
        if not self.is_available:
            return _not_configured(self.service_name, context)

        system_prompt = context.get(
            "system_prompt", "Вы — эксперт-аналитик. Отвечайте на русском языке."
        )
        return await self.client.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=context.get("max_tokens", 4096),
        )


class NaparnikStrategy(AIStrategy):
    """Strategy adapter for configured 1C Naparnik calls."""

    def __init__(self):
        """Initialize the client without failing baseline startup."""
        try:
            self.client = NaparnikClient(config=NaparnikConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """Provider identifier used by the orchestrator."""
        return "naparnik"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Naparnik request or return an offline provider contract."""
        if not self.is_available:
            return _not_configured(self.service_name, context)

        system_prompt = context.get(
            "system_prompt", "Вы — эксперт-помощник для разработчиков 1С:Enterprise."
        )
        return await self.client.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=context.get("max_tokens", 4096),
        )


class OllamaStrategy(AIStrategy):
    """Strategy adapter for configured local Ollama calls."""

    def __init__(self):
        """Initialize the client without failing baseline startup."""
        try:
            self.client = OllamaClient(config=OllamaConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """Provider identifier used by the orchestrator."""
        return "ollama"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an Ollama request or return an offline provider contract."""
        if not self.is_available:
            return _not_configured(self.service_name, context)

        model_name = context.get("ollama_model", "llama3")
        system_prompt = context.get("system_prompt", "You are a helpful AI assistant.")
        return await self.client.generate(
            prompt=query,
            model_name=model_name,
            system_prompt=system_prompt,
            temperature=context.get("temperature", 0.7),
            max_tokens=context.get("max_tokens", 4096),
        )


class TabnineStrategy(AIStrategy):
    """Strategy adapter for configured Tabnine calls."""

    def __init__(self):
        """Initialize the client without failing baseline startup."""
        try:
            self.client = TabnineClient(config=TabnineConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """Provider identifier used by the orchestrator."""
        return "tabnine"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Tabnine request or return an offline provider contract."""
        if not self.is_available:
            return _not_configured(self.service_name, context)

        system_prompt = context.get(
            "system_prompt",
            "You are an expert AI assistant specialized in code generation.",
        )
        return await self.client.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=context.get("temperature", 0.2),
            max_tokens=context.get("max_tokens", 2048),
            context=context.get("code_context"),
        )

