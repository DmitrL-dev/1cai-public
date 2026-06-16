
"""
Async client for Kimi-K2-Thinking API (Moonshot AI).

Kimi-K2-Thinking is a state-of-the-art thinking model with:
- 1T parameters (MoE), 32B activated
- 256k context window
- Native INT4 quantization
- Deep thinking & tool orchestration
- Stable long-horizon agency (200-300 tool calls)

API: https://platform.moonshot.ai (OpenAI-compatible)

Best practices:
- Use temperature=1.0 (recommended)
- Supports tool calling (same as Kimi-K2-Instruct)
- Returns reasoning_content for thinking steps
- Graceful fallback when not configured
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.utils.structured_logging import StructuredLogger

from .exceptions import LLMCallError, LLMNotConfiguredError

try:  # Optional dependency for local mode
    import aiohttp
except ImportError:  # pragma: no cover - handled gracefully when not installed
    aiohttp = None

logger = StructuredLogger(__name__).logger

DEFAULT_OLLAMA_URL = "http://localhost:11434"


@dataclass
class KimiConfig:
    """Configuration for Kimi-K2-Thinking client"""

    # Mode: "api" (Moonshot API) or "local" (Ollama/vLLM/SGLang)
    mode: str = field(
        default_factory=lambda: os.getenv(
            "KIMI_MODE", os.getenv("KIMI_DEFAULT_MODE", "auto")
        )
    )

    # API mode settings
    base_url: str = field(
        default_factory=lambda: os.getenv("KIMI_API_URL", "https://api.moonshot.cn/v1")
    )
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("KIMI_API_KEY"))

    # Local mode settings (Ollama)
    ollama_url: str = field(
        default_factory=lambda: os.getenv(
            "KIMI_OLLAMA_URL", os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_URL)
        )
    )

    # Model settings
    model_name: str = field(
        default_factory=lambda: os.getenv("KIMI_MODEL", "moonshotai/Kimi-K2-Thinking")
    )
    local_model: str = field(
        default_factory=lambda: os.getenv("KIMI_LOCAL_MODEL", "kimi-k2-thinking:cloud")
    )

    # Generation settings
    temperature: float = field(
        default_factory=lambda: float(os.getenv("KIMI_TEMPERATURE", "1.0"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("KIMI_MAX_TOKENS", "4096"))
    )
    timeout: float = field(
        default_factory=lambda: float(os.getenv("KIMI_TIMEOUT", "300.0"))
    )
    verify_ssl: bool = field(
        default_factory=lambda: os.getenv("KIMI_VERIFY_SSL", "true").lower() != "false"
    )


class KimiClient:
    """
    Async client for Kimi-K2-Thinking

    Supports both API mode (Moonshot AI) and local mode (Ollama/vLLM/SGLang)

    Features:
    - OpenAI-compatible API (API mode)
    - Ollama integration (local mode)
    - Tool calling support
    - Reasoning content extraction
    - Structured logging
    - Retry logic with exponential backoff
    - Timeout handling
    """

    def __init__(self, config: Optional[KimiConfig] = None):
        self.config = config or KimiConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = httpx.Timeout(self.config.timeout, connect=10.0)
        self._ollama_session: Optional["aiohttp.ClientSession"] = None
        self._ollama_timeout = None
        if aiohttp:
            self._ollama_timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        raw_mode = (self.config.mode or "auto").lower()
        if raw_mode not in ("api", "local", "auto"):
            logger.warning(
                "Invalid KIMI_MODE, falling back to 'api'", extra={"mode": raw_mode}
            )
            raw_mode = "api"

        if raw_mode == "auto":
            self._mode = self._auto_detect_mode()
        else:
            self._mode = raw_mode

        # Validate mode
        if self._mode not in ("api", "local"):
            logger.warning(
                "Invalid KIMI_MODE after detection, defaulting to 'api'",
                extra={"mode": self._mode},
            )
            self._mode = "api"

    def _auto_detect_mode(self) -> str:
        """Automatically select mode based on available configuration"""
        if self.config.api_key:
            logger.debug("Kimi auto mode: API key detected, using 'api'")
            return "api"

        env_local_url = os.getenv("KIMI_OLLAMA_URL") or os.getenv("OLLAMA_HOST")
        if env_local_url:
            logger.debug(
                "Kimi auto mode: Ollama env detected, using 'local'",
                extra={"ollama_url": env_local_url},
            )
            if not self.config.ollama_url:
                self.config.ollama_url = env_local_url
            return "local"

        has_custom_local = (
            bool(self.config.ollama_url)
            and self.config.ollama_url != DEFAULT_OLLAMA_URL
        )
        if has_custom_local:
            logger.debug(
                "Kimi auto mode: custom Ollama URL detected, using 'local'",
                extra={"ollama_url": self.config.ollama_url},
            )
            return "local"

        fallback = os.getenv("KIMI_DEFAULT_MODE", "api").lower()
        if fallback not in ("api", "local"):
            fallback = "api"
        logger.debug(
            "Kimi auto mode: falling back to configured default",
            extra={"fallback_mode": fallback},
        )
        return fallback

    @property
    def is_configured(self) -> bool:
        """Returns True when configured (API key for API mode, Ollama URL for local mode)"""
        if self._mode == "api":
            return bool(self.config.api_key)
        else:  # local mode
            return bool(self.config.ollama_url)

    @property
    def is_local(self) -> bool:
        """Returns True if using local mode"""
        return self._mode == "local"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client (for API mode only)"""
        if self._mode != "api":
            raise RuntimeError("_get_client() should only be called in API mode")
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout, verify=self.config.verify_ssl
            )
        return self._client

    async def _get_ollama_session(self) -> "aiohttp.ClientSession":
        """Get or create aiohttp session for local mode"""
        if aiohttp is None:  # pragma: no cover - depends on optional dependency
            raise RuntimeError(
                "aiohttp is required for Kimi local mode. Install aiohttp to continue."
            )

        if self._ollama_session is None or self._ollama_session.closed:
            timeout = self._ollama_timeout or aiohttp.ClientTimeout(
                total=self.config.timeout
            )
            self._ollama_session = aiohttp.ClientSession(timeout=timeout)
        return self._ollama_session

    async def check_model_loaded(self) -> bool:
        """Check if model is loaded in Ollama (local mode only)"""
        if self._mode != "local":
            return True  # API mode doesn't need this check

        ollama_url = self.config.ollama_url.rstrip("/")
        if not ollama_url.startswith(("http://", "https://")):
            ollama_url = f"http://{ollama_url}"

        try:
            session = await self._get_ollama_session()
            async with session.get(f"{ollama_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m["name"] for m in data.get("models", [])]
                    return self.config.local_model in models
        except Exception as e:
            logger.error(
                "Error checking Kimi model in Ollama",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "model": self.config.local_model,
                },
            )
        return False

    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._ollama_session:
            await self._ollama_session.close()
            self._ollama_session = None

    async def __aenter__(self) -> "KimiClient":
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
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate completion using Kimi-K2-Thinking

        Supports both API mode (Moonshot AI) and local mode (Ollama)

        Args:
            prompt: User prompt
            temperature: Temperature (default: 1.0, recommended for thinking)
            max_tokens: Maximum tokens (default: 4096)
            system_prompt: System prompt (default: Kimi assistant)
            response_format: Response format ("text" or "json")
            tools: List of tool definitions for tool calling (API mode only)
            tool_choice: Tool choice mode ("auto", "none", or tool name) (API mode only)
            stream: Whether to stream response

        Returns:
            Dictionary with keys:
            - text: Generated text
            - reasoning_content: Thinking/reasoning steps (if available, API mode only)
            - tool_calls: Tool calls made (if any, API mode only)
            - usage: Token usage statistics

        Raises:
            LLMNotConfiguredError: If not configured
            LLMCallError: If API call fails
        """
        if not self.is_configured:
            if self._mode == "api":
                raise LLMNotConfiguredError(
                    "Kimi API key is not configured. Set KIMI_API_KEY or use KIMI_MODE=local"
                )
            else:
                raise LLMNotConfiguredError(
                    "Kimi Ollama URL is not configured. Set KIMI_OLLAMA_URL or OLLAMA_HOST"
                )

        # Input validation
        if not isinstance(prompt, str) or not prompt.strip():
            logger.warning(
                "Invalid prompt in KimiClient.generate",
                extra={"prompt_type": type(prompt).__name__ if prompt else None},
            )
            raise ValueError("Prompt must be a non-empty string")

        # Limit prompt length (prevent DoS)
        max_prompt_length = 200000  # ~256k tokens
        if len(prompt) > max_prompt_length:
            logger.warning(
                "Prompt too long in KimiClient.generate",
                extra={"prompt_length": len(prompt), "max_length": max_prompt_length},
            )
            prompt = prompt[:max_prompt_length]

        # Route to appropriate implementation
        if self._mode == "local":
            # Warn if tools are requested in local mode
            if tools:
                logger.warning(
                    "Tool calling not supported in local mode",
                    extra={"tools_count": len(tools)},
                )
            return await self._generate_local(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                response_format=response_format,
            )
        else:
            return await self._generate_api(
                prompt=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                response_format=response_format,
                tools=tools,
                tool_choice=tool_choice,
                stream=stream,
            )

    async def _generate_local(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
    ) -> Dict[str, Any]:
        """
        Generate using local Ollama instance

        Note: Tool calling not supported in local mode yet
        """
        # Use recommended temperature if not specified
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        # Build full prompt with system prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        else:
            full_prompt = prompt

        # Ollama API endpoint
        ollama_url = self.config.ollama_url.rstrip("/")
        if not ollama_url.startswith(("http://", "https://")):
            ollama_url = f"http://{ollama_url}"

        try:
            logger.debug(
                "Calling Kimi-K2-Thinking via Ollama",
                extra={
                    "model": self.config.local_model,
                    "prompt_length": len(prompt),
                    "temperature": temperature,
                    "ollama_url": ollama_url,
                },
            )

            session = await self._get_ollama_session()
            async with session.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": self.config.local_model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        "Ollama API error",
                        extra={
                            "status_code": response.status,
                            "error": error_text,
                            "model": self.config.local_model,
                        },
                    )
                    raise LLMCallError(
                        f"Ollama API error: HTTP {response.status}: {error_text}"
                    )

                data = await response.json()
                text = data.get("response", "")

                logger.info(
                    "Kimi-K2-Thinking (local) API call successful",
                    extra={
                        "prompt_length": len(prompt),
                        "response_length": len(text),
                        "tokens_used": data.get("eval_count", 0),
                        "model": self.config.local_model,
                    },
                )

                return {
                    "text": text,
                    "reasoning_content": "",  # Ollama doesn't return reasoning content
                    "tool_calls": [],
                    "usage": {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": data.get("prompt_eval_count", 0)
                        + data.get("eval_count", 0),
                    },
                    "finish_reason": "stop",
                }

        except aiohttp.ClientError as e:
            logger.error(
                "Ollama network error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "ollama_url": ollama_url,
                },
                exc_info=True,
            )
            raise LLMCallError(f"Ollama network error: {str(e)}") from e

        except Exception as e:
            logger.error(
                "Unexpected error in Kimi local generation",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise LLMCallError(f"Unexpected error: {str(e)}") from e

    async def _generate_api(
        self,
        prompt: str,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate using Moonshot AI API (original implementation)
        """
        # Use recommended temperature if not specified
        temperature = (
            temperature if temperature is not None else self.config.temperature
        )
        max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        # Default system prompt
        if system_prompt is None:
            system_prompt = "You are Kimi, an AI assistant created by Moonshot AI."

        client = await self._get_client()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        # Format messages (OpenAI-compatible format)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},  # Simple string format
        ]

        payload: Dict[str, Any] = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Add tool calling support
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        # Add response format
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            logger.debug(
                "Calling Kimi-K2-Thinking API",
                extra={
                    "model": self.config.model_name,
                    "prompt_length": len(prompt),
                    "has_tools": bool(tools),
                    "temperature": temperature,
                },
            )

            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

            response.raise_for_status()
            result = response.json()

            # Extract response content
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})

            text = message.get("content", "")
            reasoning_content = message.get("reasoning_content", "")  # Kimi-specific
            tool_calls = message.get("tool_calls", [])

            usage = result.get("usage", {})

            logger.info(
                "Kimi-K2-Thinking API call successful",
                extra={
                    "prompt_length": len(prompt),
                    "response_length": len(text),
                    "has_reasoning": bool(reasoning_content),
                    "tool_calls_count": len(tool_calls),
                    "tokens_used": usage.get("total_tokens", 0),
                },
            )

            return {
                "text": text,
                "reasoning_content": reasoning_content,
                "tool_calls": tool_calls,
                "usage": usage,
                "finish_reason": choice.get("finish_reason"),
            }

        except httpx.HTTPStatusError as e:
            error_text = ""
            try:
                error_data = e.response.json()
                error_text = error_data.get("error", {}).get("message", str(e))
            except Exception:
                error_text = e.response.text or str(e)

            logger.error(
                "Kimi API HTTP error",
                extra={
                    "status_code": e.response.status_code,
                    "error": error_text,
                    "prompt_length": len(prompt),
                },
                exc_info=True,
            )
            raise LLMCallError(f"Kimi API error: {error_text}") from e

        except httpx.TimeoutException as e:
            logger.error(
                "Kimi API timeout",
                extra={"timeout": self.config.timeout, "prompt_length": len(prompt)},
                exc_info=True,
            )
            raise LLMCallError(f"Kimi API timeout after {self.config.timeout}s") from e

        except httpx.RequestError as e:
            logger.error(
                "Kimi API request error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise LLMCallError(f"Kimi API request failed: {str(e)}") from e

        except Exception as e:
            logger.error(
                "Unexpected error in Kimi API call",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            raise LLMCallError(f"Unexpected error: {str(e)}") from e

    async def chat_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        tool_map: Dict[str, callable],
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        Chat with tool calling support (multi-turn)

        Implements the tool calling pipeline:
        1. Send messages with tools
        2. If tool_calls in response, execute tools
        3. Add tool results to messages
        4. Continue until finish_reason != "tool_calls"

        Args:
            messages: Conversation messages
            tools: Tool definitions
            tool_map: Map of tool names to functions
            max_iterations: Maximum tool calling iterations

        Returns:
            Final response with all tool results
        """
        if not self.is_configured:
            if self._mode == "api":
                raise LLMNotConfiguredError("Kimi API key is not configured")
            else:
                raise LLMNotConfiguredError("Kimi Ollama URL is not configured")

        # Tool calling only supported in API mode
        if self._mode == "local":
            logger.warning(
                "Tool calling not supported in local mode, using simple generation",
                extra={"tools_count": len(tools)},
            )
            # Extract last user message
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break

            if last_user_msg:
                result = await self.generate(prompt=last_user_msg)
                return {
                    "text": result["text"],
                    "reasoning_content": "",
                    "tool_calls": [],
                    "usage": result.get("usage", {}),
                    "iterations": 1,
                }
            else:
                raise ValueError("No user message found in messages")

        iteration = 0
        finish_reason = None

        while iteration < max_iterations and (
            finish_reason is None or finish_reason == "tool_calls"
        ):
            # Extract last user message for API mode
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break

            if not last_user_msg:
                raise ValueError("No user message found in messages")

            result = await self.generate(
                prompt=last_user_msg,
                system_prompt=(
                    messages[0].get("content", "")
                    if messages and messages[0].get("role") == "system"
                    else None
                ),
                tools=tools,
                tool_choice="auto",
            )

            # Update messages with assistant response
            assistant_message = {
                "role": "assistant",
                "content": result["text"],
            }

            if result.get("tool_calls"):
                assistant_message["tool_calls"] = result["tool_calls"]

            messages.append(assistant_message)

            finish_reason = result.get("finish_reason")

            # Execute tool calls
            if finish_reason == "tool_calls" and result.get("tool_calls"):
                for tool_call in result["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    tool_args = json.loads(tool_call["function"]["arguments"])

                    if tool_name in tool_map:
                        try:
                            tool_result = tool_map[tool_name](**tool_args)
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call["id"],
                                    "name": tool_name,
                                    "content": json.dumps(tool_result),
                                }
                            )
                        except Exception as e:
                            logger.error(
                                "Tool execution error",
                                extra={
                                    "tool_name": tool_name,
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                exc_info=True,
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call["id"],
                                    "name": tool_name,
                                    "content": json.dumps({"error": str(e)}),
                                }
                            )
                    else:
                        logger.warning(
                            "Unknown tool in tool_map", extra={"tool_name": tool_name}
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": json.dumps(
                                    {"error": f"Tool {tool_name} not found"}
                                ),
                            }
                        )

            iteration += 1

        if iteration >= max_iterations:
            logger.warning(
                "Max iterations reached in chat_with_tools",
                extra={"max_iterations": max_iterations},
            )

        return {
            "text": result["text"],
            "reasoning_content": result.get("reasoning_content", ""),
            "tool_calls": result.get("tool_calls", []),
            "usage": result.get("usage", {}),
            "iterations": iteration,
        }
