"""
Asynchronous client for GigaChat (Sber Devices) LLM.

The implementation is designed to work with the official REST API but falls back
gracefully when credentials are not provided. This allows local development
without network access while keeping the integration ready for production.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .exceptions import LLMCallError, LLMNotConfiguredError

logger = logging.getLogger(__name__)


@dataclass
class GigaChatConfig:
    """Configuration holder for GigaChat client."""

    base_url: str = os.getenv(
        "GIGACHAT_API_URL", "https://gigachat.devices.sberbank.ru/api/v1"
    )
    token_url: str = os.getenv(
        "GIGACHAT_TOKEN_URL", "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    )
    scope: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    client_id: Optional[str] = os.getenv("GIGACHAT_CLIENT_ID")
    client_secret: Optional[str] = os.getenv("GIGACHAT_CLIENT_SECRET")
    access_token: Optional[str] = os.getenv("GIGACHAT_ACCESS_TOKEN")
    verify_ssl: bool = os.getenv("GIGACHAT_VERIFY_SSL", "true").lower() != "false"


class GigaChatClient:
    """Async client for interacting with the GigaChat API."""

    def __init__(self, config: Optional[GigaChatConfig] = None):
        self.config = config or GigaChatConfig()
        self._access_token: Optional[str] = self.config.access_token
        self._token_expires_at: float = 0.0
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=60)

    @property
    def is_configured(self) -> bool:
        """Returns True when we have enough data to perform API calls."""
        return bool(
            self._access_token
            or (
                self.config.client_id
                and self.config.client_secret
                and self.config.token_url
            )
        )

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "GigaChatClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def generate(
        self,
        prompt: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
    ) -> Dict[str, Any]:
        """
        Generates a completion from the GigaChat model.

        Returns a dictionary with keys `text` and `usage`. When the client is
        not configured, a LLMNotConfiguredError is raised so callers can fall
        back to heuristic pipelines.
        """
        if not self.is_configured:
            raise LLMNotConfiguredError("GigaChat credentials are not configured")

        await self._ensure_token()

        payload = {
            "model": "GigaChat",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or "Ты помогатель аналитика.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        params = {}
        if response_format == "json":
            params["response_format"] = {"type": "json_object"}

        json_payload = {**payload, **params}

        session = await self._get_session()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=json_payload,
                ssl=self.config.verify_ssl,
            ) as response:
                if response.status == 401:
                    # Token might be expired, refresh once
                    logger.info("GigaChat token expired, refreshing…")
                    self._access_token = None
                    await self._ensure_token(force=True)
                    return await self.generate(
                        prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=system_prompt,
                        response_format=response_format,
                    )

                if response.status != 200:
                    text = await response.text()
                    raise LLMCallError(f"GigaChat HTTP {response.status}: {text}")

                data = await response.json()
                choices = data.get("choices", [])
                message = choices[0]["message"]["content"] if choices else ""
                usage = data.get("usage", {})
                return {"text": message, "usage": usage, "raw": data}

        except aiohttp.ClientError as exc:
            raise LLMCallError(f"GigaChat network error: {exc}") from exc

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

    async def _ensure_token(self, force: bool = False) -> None:
        if (
            self._access_token
            and not force
            and time.time() < self._token_expires_at - 60
        ):
            return

        if self.config.access_token and not force:
            # Static token from environment
            self._access_token = self.config.access_token
            self._token_expires_at = time.time() + 3600
            return

        if not (self.config.client_id and self.config.client_secret):
            raise LLMNotConfiguredError("GigaChat client credentials are missing")

        await self._request_token()

    @retry(
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(LLMCallError),
        reraise=True,
    )
    async def _request_token(self) -> None:
        session = await self._get_session()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "scope": self.config.scope,
        }

        auth = aiohttp.BasicAuth(self.config.client_id, self.config.client_secret)

        try:
            async with session.post(
                self.config.token_url,
                headers=headers,
                data=data,
                auth=auth,
                ssl=self.config.verify_ssl,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise LLMCallError(
                        f"GigaChat token request failed: HTTP {response.status} {text}"
                    )

                payload = await response.json()
                self._access_token = payload.get("access_token")
                expires_in = payload.get("expires_in", 3600)
                if not self._access_token:
                    raise LLMCallError(
                        f"GigaChat token response invalid: {json.dumps(payload)}"
                    )
                self._token_expires_at = time.time() + int(expires_in)

        except aiohttp.ClientError as exc:
            raise LLMCallError(f"GigaChat token network error: {exc}") from exc
