
"""
Universal Ollama Client
-----------------------

Универсальный клиент для работы с локальными моделями через Ollama.
Поддерживает различные модели: llama3, mistral, codellama, qwen и другие.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .exceptions import LLMCallError, LLMNotConfiguredError

logger = logging.getLogger(__name__)


@dataclass
class OllamaConfig:
    """Конфигурация Ollama клиента."""

    base_url: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name: str = os.getenv("OLLAMA_MODEL", "llama3")
    timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))
    verify_ssl: bool = os.getenv("OLLAMA_VERIFY_SSL", "true").lower() != "false"
    max_retries: int = 3


class OllamaClient:
    """
    Универсальный клиент для работы с Ollama моделями.

    Поддерживает различные модели:
    - llama3, llama3.1, llama3.2
    - mistral, mistral:7b
    - codellama, codellama:7b
    - qwen2.5-coder, qwen2.5:7b
    - и другие модели Ollama
    """

    def __init__(self, config: Optional[OllamaConfig] = None):
        """
        Инициализация Ollama клиента.

        Args:
            config: Конфигурация клиента. Если не указана, используется конфигурация из env.
        """
        self.config = config or OllamaConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=self.config.timeout)

    @property
    def is_configured(self) -> bool:
        """Проверка, настроен ли клиент."""
        return bool(self.config.base_url)

    async def close(self) -> None:
        """Закрыть HTTP сессию."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "OllamaClient":
        """Context manager вход."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Context manager выход."""
        await self.close()

    async def list_models(self) -> List[str]:
        """
        Получить список доступных моделей в Ollama.

        Returns:
            Список названий моделей.

        Raises:
            LLMNotConfiguredError: Если Ollama не настроен
            LLMCallError: Если запрос не удался
        """
        if not self.is_configured:
            raise LLMNotConfiguredError("Ollama URL is not configured")

        session = await self._get_session()
        try:
            async with session.get(
                f"{self.config.base_url}/api/tags",
                ssl=self.config.verify_ssl,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise LLMCallError(f"Ollama HTTP {response.status}: {text}")

                data = await response.json()
                models = [model.get("name", "") for model in data.get("models", [])]
                logger.debug(
                    "Listed Ollama models",
                    extra={"models_count": len(models), "models": models[:5]},
                )
                return models

        except aiohttp.ClientError as exc:
            raise LLMCallError(f"Ollama network error: {exc}") from exc

    async def check_model_available(self, model_name: Optional[str] = None) -> bool:
        """
        Проверить, доступна ли модель в Ollama.

        Args:
            model_name: Название модели. Если не указано, используется config.model_name.

        Returns:
            True, если модель доступна.
        """
        model_name = model_name or self.config.model_name
        try:
            models = await self.list_models()
            return model_name in models
        except Exception as e:
            logger.debug(
                "Failed to check model availability",
                extra={"model": model_name, "error": str(e)},
            )
            return False

    @retry(
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(LLMCallError),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Генерация текста через Ollama.

        Args:
            prompt: Пользовательский промпт
            model_name: Название модели. Если не указано, используется config.model_name
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов
            system_prompt: Системный промпт
            response_format: Формат ответа ("text" или "json")
            stream: Потоковая генерация (не поддерживается, всегда False)

        Returns:
            Словарь с ключами:
            - text: Сгенерированный текст
            - usage: Статистика использования токенов
            - raw: Полный ответ от Ollama

        Raises:
            LLMNotConfiguredError: Если Ollama не настроен
            LLMCallError: Если запрос не удался
        """
        if not self.is_configured:
            raise LLMNotConfiguredError("Ollama URL is not configured")

        model_name = model_name or self.config.model_name

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")

        # Ограничение длины промпта
        max_prompt_length = 200000  # ~256k tokens
        if len(prompt) > max_prompt_length:
            logger.warning(
                "Prompt too long, truncating",
                extra={"prompt_length": len(prompt), "max_length": max_prompt_length},
            )
            prompt = prompt[:max_prompt_length]

        # Формирование полного промпта
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        session = await self._get_session()

        # Формирование JSON payload
        payload: Dict[str, Any] = {
            "model": model_name,
            "prompt": full_prompt,
            "stream": False,  # OllamaClient не поддерживает streaming в этом интерфейсе
            "options": {
                "temperature": temperature,
            },
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        if response_format == "json":
            payload["format"] = "json"

        try:
            logger.debug(
                "Calling Ollama",
                extra={
                    "model": model_name,
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                },
            )

            async with session.post(
                f"{self.config.base_url}/api/generate",
                json=payload,
                ssl=self.config.verify_ssl,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise LLMCallError(f"Ollama HTTP {response.status}: {text}")

                data = await response.json()
                text = data.get("response", "")
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": (
                        data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
                    ),
                }

                logger.info(
                    "Ollama generation successful",
                    extra={
                        "model": model_name,
                        "prompt_length": len(prompt),
                        "response_length": len(text),
                        "tokens": usage["total_tokens"],
                    },
                )

                return {
                    "text": text,
                    "usage": usage,
                    "raw": data,
                }

        except aiohttp.ClientError as exc:
            raise LLMCallError(f"Ollama network error: {exc}") from exc

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        # Проверяем закрыта ли сессия только если она не None
        elif hasattr(self._session, "closed") and self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session
