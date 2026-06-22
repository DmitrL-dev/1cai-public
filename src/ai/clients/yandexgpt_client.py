"""
Async client for YandexGPT API.

The client supports production usage when credentials are provided and gracefully
falls back when configuration is missing, allowing developers to rely on
heuristics locally.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

from .exceptions import LLMCallError, LLMNotConfiguredError

logger = logging.getLogger(__name__)


@dataclass
class YandexGPTConfig:
    base_url: str = os.getenv(
        "YANDEXGPT_API_URL", "https://llm.api.cloud.yandex.net/llm/v1alpha"
    )
    folder_id: Optional[str] = os.getenv("YANDEXGPT_FOLDER_ID")
    api_key: Optional[str] = os.getenv("YANDEXGPT_API_KEY")
    model_name: str = os.getenv("YANDEXGPT_MODEL", "yandexgpt/latest")
    verify_ssl: bool = os.getenv("YANDEXGPT_VERIFY_SSL", "true").lower() != "false"


class YandexGPTClient:
    def __init__(self, config: Optional[YandexGPTConfig] = None):
        self.config = config or YandexGPTConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=60)

    @property
    def is_configured(self) -> bool:
        return bool(self.config.api_key and self.config.folder_id)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "YandexGPTClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
    ) -> Dict[str, Any]:
        if not self.is_configured:
            raise LLMNotConfiguredError("YandexGPT credentials are not configured")

        session = await self._get_session()

        headers = {
            "Authorization": f"Api-Key {self.config.api_key}",
            "Content-Type": "application/json",
            "x-folder-id": self.config.folder_id,
        }

        messages = [
            {
                "role": "system",
                "text": system_prompt or "Assistant for business analyst tasks.",
            },
            {"role": "user", "text": prompt},
        ]

        json_payload: Dict[str, Any] = {
            "modelUri": f"gpt://{self.config.folder_id}/{self.config.model_name}",
            "completionOptions": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": messages,
        }

        if response_format == "json":
            json_payload["completionOptions"]["stream"] = False
            json_payload["messages"][0]["text"] += "\nОтвет возвращай в формате JSON."

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=json_payload,
                ssl=self.config.verify_ssl,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise LLMCallError(f"YandexGPT HTTP {response.status}: {text}")

                data = await response.json()
                alternatives = data.get("result", {}).get("alternatives", [])
                if not alternatives:
                    return {"text": "", "usage": {}, "raw": data}

                message = alternatives[0]["message"]["text"]
                usage = data.get("result", {}).get("usage", {})
                return {"text": message, "usage": usage, "raw": data}

        except aiohttp.ClientError as exc:
            raise LLMCallError(f"YandexGPT network error: {exc}") from exc

    async def _get_session(self, use_pool: bool = True) -> aiohttp.ClientSession:
        """
        Получить HTTP сессию, используя ConnectionPool если доступен.

        Args:
            use_pool: Использовать ConnectionPool если доступен (по умолчанию True)

        Returns:
            aiohttp.ClientSession
        """
        if use_pool:
            try:
                from src.ai.connection_pool import get_global_pool

                pool = get_global_pool()
                return await pool.get_session(self.config.base_url)
            except ImportError:
                # ConnectionPool не доступен, используем обычную сессию
                pass

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self._session
