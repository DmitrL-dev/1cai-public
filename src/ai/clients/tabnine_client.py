"""
Async client for Tabnine API.

Tabnine is an AI-powered code completion service that provides intelligent
code suggestions and completions. This client supports authentication using
JWT tokens obtained from Tabnine's authentication service.

The client is designed to work with Tabnine's API but falls back gracefully
when credentials are not provided, allowing local development without network access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.structured_logging import StructuredLogger

from .exceptions import LLMCallError, LLMNotConfiguredError

logger = StructuredLogger(__name__).logger


@dataclass
class TabnineConfig:
    """Configuration holder for Tabnine client."""

    # API endpoint (default Tabnine API)
    base_url: str = os.getenv("TABNINE_API_URL", "https://api.tabnine.com/v1")

    # JWT authentication token
    auth_token: Optional[str] = os.getenv("TABNINE_AUTH_TOKEN")

    # Model settings
    model_name: str = os.getenv("TABNINE_MODEL", "tabnine-pro")

    # Request settings
    verify_ssl: bool = os.getenv("TABNINE_VERIFY_SSL", "true").lower() != "false"
    timeout_seconds: float = float(os.getenv("TABNINE_TIMEOUT_SECONDS", "30.0"))

    # Generation settings
    max_tokens: int = int(os.getenv("TABNINE_MAX_TOKENS", "2048"))
    temperature: float = float(os.getenv("TABNINE_TEMPERATURE", "0.2"))


class TabnineClient:
    """
    Async client for interacting with the Tabnine API.

    Supports JWT token authentication and provides code completion
    and generation capabilities.
    """

    def __init__(self, config: Optional[TabnineConfig] = None):
        self.config = config or TabnineConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = httpx.Timeout(self.config.timeout_seconds, connect=10.0)

    @property
    def is_configured(self) -> bool:
        """Returns True when we have enough data to perform API calls."""
        return bool(self.config.auth_token)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout, verify=self.config.verify_ssl
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "TabnineClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def generate(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generates code completion or text from the Tabnine model.

        Args:
            prompt: User prompt or code context
            temperature: Temperature for generation (default: from config)
            max_tokens: Maximum tokens to generate (default: from config)
            system_prompt: Optional system prompt
            response_format: Response format ("text" or "json")
            context: Optional context dictionary (e.g., file path, language)

        Returns:
            Dictionary with keys `text` and `usage`. When the client is
            not configured, a LLMNotConfiguredError is raised.

        Raises:
            LLMNotConfiguredError: If client is not configured
            LLMCallError: If API call fails
        """
        if not self.is_configured:
            raise LLMNotConfiguredError(
                "Tabnine credentials are not configured. Set TABNINE_AUTH_TOKEN environment variable."
            )

        client = await self._get_client()

        headers = {
            "Authorization": f"Bearer {self.config.auth_token}",
            "Content-Type": "application/json",
        }

        # Default system prompt for code generation
        default_system_prompt = (
            system_prompt
            or "You are an expert AI assistant specialized in code generation and completion. "
            "Provide accurate, efficient, and well-structured code solutions."
        )

        # Use config defaults if not specified
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        # Build messages
        messages = [
            {"role": "system", "content": default_system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Build payload
        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Add context if provided
        if context:
            payload["context"] = context

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            logger.debug(
                "Calling Tabnine API",
                extra={
                    "model": self.config.model_name,
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                    "base_url": self.config.base_url,
                },
            )

            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            if response.status_code == 401:
                raise LLMNotConfiguredError(
                    "Tabnine authentication token is invalid or expired. "
                    "Please check your TABNINE_AUTH_TOKEN."
                )

            response.raise_for_status()
            data = response.json()

            # Handle different possible response formats
            # Format 1: OpenAI-like format
            if "choices" in data:
                choices = data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    return {
                        "text": message,
                        "usage": usage,
                        "raw": data,
                        "finish_reason": choices[0].get("finish_reason"),
                    }

            # Format 2: Direct response format
            if "result" in data:
                result = data.get("result", {})
                message = result.get("text", result.get("message", ""))
                usage = result.get("usage", {})
                return {
                    "text": message,
                    "usage": usage,
                    "raw": data,
                }

            # Format 3: Plain text response
            if "text" in data:
                return {
                    "text": data.get("text", ""),
                    "usage": data.get("usage", {}),
                    "raw": data,
                }

            # Fallback: return raw data
            logger.warning(
                "Unexpected Tabnine response format",
                extra={"response_keys": list(data.keys())},
            )
            return {
                "text": str(data),
                "usage": {},
                "raw": data,
            }

        except httpx.HTTPStatusError as e:
            error_text = ""
            try:
                error_data = e.response.json()
                error_text = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_text = e.response.text or str(e)

            logger.error(
                "Tabnine API HTTP error",
                extra={
                    "status_code": e.response.status_code,
                    "error": error_text,
                    "prompt_length": len(prompt),
                },
                exc_info=True,
            )
            raise LLMCallError(f"Tabnine API error: {error_text}") from e

        except httpx.TimeoutException as e:
            logger.error(
                "Tabnine API timeout",
                extra={
                    "timeout": self.config.timeout_seconds,
                    "prompt_length": len(prompt),
                },
            )
            raise LLMCallError(
                f"Tabnine API timeout after {self.config.timeout_seconds}s"
            ) from e

        except httpx.RequestError as e:
            logger.error(
                "Tabnine API request error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise LLMCallError(f"Tabnine API request failed: {str(e)}") from e

        except Exception as e:
            logger.error(
                "Unexpected error in Tabnine API call",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise LLMCallError(f"Unexpected error: {str(e)}") from e

    async def complete_code(
        self,
        prefix: str,
        suffix: Optional[str] = None,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get code completion suggestions.

        Args:
            prefix: Code before cursor
            suffix: Optional code after cursor
            language: Programming language (e.g., "python", "javascript")
            file_path: Optional file path for context

        Returns:
            Dictionary with completion suggestions
        """
        context = {}
        if language:
            context["language"] = language
        if file_path:
            context["file_path"] = file_path

        prompt = prefix
        if suffix:
            prompt = f"{prefix}\n<CURSOR>\n{suffix}"

        return await self.generate(
            prompt=prompt,
            context=context,
            temperature=0.1,  # Lower temperature for code completion
        )
