"""Модуль llm_providers.

TODO: Добавить подробное описание модуля.

Этот docstring был автоматически сгенерирован.
Пожалуйста, обновите его с правильным описанием.
"""

from typing import Any, Dict

from src.ai.clients.gigachat_client import GigaChatClient, GigaChatConfig
from src.ai.clients.naparnik_client import NaparnikClient, NaparnikConfig
from src.ai.clients.ollama_client import OllamaClient, OllamaConfig
from src.ai.clients.tabnine_client import TabnineClient, TabnineConfig
from src.ai.clients.yandexgpt_client import YandexGPTClient, YandexGPTConfig
from src.ai.strategies.base import AIStrategy
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class GigaChatStrategy(AIStrategy):
    """Класс GigaChatStrategy.
    
    TODO: Добавить описание класса.
    
    Attributes:
        TODO: Описать атрибуты класса.
    """
    def __init__(self):
        """TODO: Описать функцию __init__."""
        try:
            self.client = GigaChatClient(config=GigaChatConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """TODO: Описать функцию service_name.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return "gigachat"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: Описать функцию execute.
        
        Args:
            query: TODO: Описать параметр.
            context: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if not self.is_available:
            return {"status": "skipped", "message": "GigaChat not configured"}

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
    """Класс YandexGPTStrategy.
    
    TODO: Добавить описание класса.
    
    Attributes:
        TODO: Описать атрибуты класса.
    """
    def __init__(self):
        """TODO: Описать функцию __init__."""
        try:
            self.client = YandexGPTClient(config=YandexGPTConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """TODO: Описать функцию service_name.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return "yandexgpt"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: Описать функцию execute.
        
        Args:
            query: TODO: Описать параметр.
            context: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if not self.is_available:
            return {"status": "skipped", "message": "YandexGPT not configured"}

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
    """Класс NaparnikStrategy.
    
    TODO: Добавить описание класса.
    
    Attributes:
        TODO: Описать атрибуты класса.
    """
    def __init__(self):
        """TODO: Описать функцию __init__."""
        try:
            self.client = NaparnikClient(config=NaparnikConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """TODO: Описать функцию service_name.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return "naparnik"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: Описать функцию execute.
        
        Args:
            query: TODO: Описать параметр.
            context: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if not self.is_available:
            return {"status": "skipped", "message": "Naparnik not configured"}

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
    """Класс OllamaStrategy.
    
    TODO: Добавить описание класса.
    
    Attributes:
        TODO: Описать атрибуты класса.
    """
    def __init__(self):
        """TODO: Описать функцию __init__."""
        try:
            self.client = OllamaClient(config=OllamaConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """TODO: Описать функцию service_name.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return "ollama"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: Описать функцию execute.
        
        Args:
            query: TODO: Описать параметр.
            context: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if not self.is_available:
            return {"status": "skipped", "message": "Ollama not configured"}

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
    """Класс TabnineStrategy.
    
    TODO: Добавить описание класса.
    
    Attributes:
        TODO: Описать атрибуты класса.
    """
    def __init__(self):
        """TODO: Описать функцию __init__."""
        try:
            self.client = TabnineClient(config=TabnineConfig())
            self.is_available = self.client.is_configured
        except Exception:
            self.is_available = False

    @property
    def service_name(self) -> str:
        """TODO: Описать функцию service_name.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        return "tabnine"

    async def execute(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """TODO: Описать функцию execute.
        
        Args:
            query: TODO: Описать параметр.
            context: TODO: Описать параметр.
        
        Returns:
            TODO: Описать возвращаемое значение.
        """
        if not self.is_available:
            return {"status": "skipped", "message": "Tabnine not configured"}

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

