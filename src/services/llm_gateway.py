"""
LLM Gateway — центральная точка выбора провайдера с поддержкой fallback-цепочек.

Версия: 2.2.0
Refactored: Enhanced resilience (timeouts, circuit breakers) and security.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence

import yaml

if TYPE_CHECKING:
    pass
from src.monitoring.prometheus_metrics import (
    llm_gateway_fallbacks_total,
    llm_gateway_latency_seconds,
    llm_gateway_requests_total,
    llm_provider_health,
    llm_provider_latency_ms,
)
from src.resilience.error_recovery import CircuitBreaker

from .llm_health_monitor import LLMHealthMonitor, ProviderHealthStatus
from .llm_provider_manager import (
    LLMProviderManager,
    ProviderConfig,
    load_llm_provider_manager,
)

logger = logging.getLogger(__name__)


@dataclass
class LLMGatewayResponse:
    provider: str
    model: str
    response: str
    metadata: Dict[str, Any]


class LLMGateway:
    """
    LLM шлюз: определяет порядок провайдеров и возвращает структурированный ответ.
    """

    def __init__(
        self,
        manager: Optional[LLMProviderManager] = None,
        enable_cache: bool = True,
        enable_health_monitoring: bool = True,
        enable_circuit_breaker: bool = True,
        client_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.manager = manager or load_llm_provider_manager()
        self._ensure_manager()
        self.simulation_config = self._load_simulation_config()

        self._clients: Dict[str, Any] = {}
        self._client_factory = client_factory

        self.cache: Optional[IntelligentCache] = None
        if enable_cache:
            try:
                from src.ai.intelligent_cache import IntelligentCache

                self.cache = IntelligentCache(max_size=1000, default_ttl_seconds=300)
            except Exception as e:
                logger.warning("Failed to initialize cache: %s", e)

        self.health_monitor: Optional[LLMHealthMonitor] = None
        if enable_health_monitoring and self.manager:
            try:
                health_config = self.manager.health_config
                self.health_monitor = LLMHealthMonitor(
                    manager=self.manager,
                    check_interval_seconds=health_config.get("interval_seconds", 60),
                    failure_threshold=health_config.get("failure_threshold", 3),
                    recovery_threshold=health_config.get("recovery_threshold", 2),
                )
                asyncio.create_task(self.health_monitor.start_monitoring())
            except Exception as e:
                logger.warning("Failed to initialize health monitor: %s", e)

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        if enable_circuit_breaker:
            for provider in self.manager.providers.values():
                if provider.enabled:
                    retry_policy = provider.metadata.get("retry_policy", {})
                    self.circuit_breakers[provider.name] = CircuitBreaker(
                        failure_threshold=5,
                        success_threshold=2,
                        timeout_seconds=retry_policy.get("backoff_seconds", 60),
                    )

    def _ensure_manager(self) -> None:
        if not self.manager or not self.manager.has_configuration():
            logger.warning(
                "LLMGateway running without provider configuration; defaults will be used."
            )

    def get_client(self, provider_name: str) -> Any:
        if provider_name in self._clients:
            return self._clients[provider_name]

        client = None
        if self._client_factory:
            client = self._client_factory(provider_name)

        if not client:
            client = self._create_default_client(provider_name)

        if client:
            self._clients[provider_name] = client

        return client

    def _create_default_client(self, provider_name: str) -> Any:
        try:
            if provider_name == "gigachat":
                from src.ai.clients.gigachat_client import GigaChatClient

                return GigaChatClient()
            elif provider_name == "yandex-gpt":
                from src.ai.clients.yandexgpt_client import YandexGPTClient

                return YandexGPTClient()
            elif provider_name == "naparnik":
                from src.ai.clients.naparnik_client import NaparnikClient

                return NaparnikClient()
            elif provider_name in {"local-qwen", "local-mistral", "ollama"}:
                from src.ai.clients.ollama_client import OllamaClient

                return OllamaClient()
        except Exception as e:
            logger.debug("Failed to create default client for %s: {e}", provider_name)
        return None

    async def generate(
        self,
        prompt: str,
        role: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> LLMGatewayResponse:
        start_time = time.time()

        simulated = self._simulate_response(prompt, role)
        if simulated:
            return simulated

        cache_key = self._build_cache_key(
            prompt, role, temperature, max_tokens, system_prompt
        )
        if self.cache:
            try:
                cached = await asyncio.to_thread(self.cache.get, cache_key)
                if cached:
                    logger.debug(f"Cache hit for prompt: {prompt[:50]}...")
                    llm_gateway_requests_total.labels(
                        provider="cache", role=role or "unknown", status="hit"
                    ).inc()
                    return cached
            except Exception as e:
                logger.debug("Cache get error: %s", e)

        provider_chain = self._build_provider_chain(role)

        if not provider_chain:
            logger.warning("LLMGateway: no providers available")
            return self._build_offline_fallback_response(
                "unknown", "unknown", prompt, role, []
            )

        last_error: Optional[Exception] = None

        for provider in provider_chain:
            if self.health_monitor and not self.health_monitor.is_provider_healthy(
                provider.name
            ):
                logger.debug(f"Provider {provider.name} is unhealthy, skipping")
                continue

            circuit_breaker = self.circuit_breakers.get(provider.name)
            if circuit_breaker and not circuit_breaker.state.should_attempt():
                logger.debug(f"Circuit breaker OPEN for {provider.name}, skipping")
                continue

            try:
                # Enforce strict timeout for provider call
                timeout = kwargs.get("timeout", 30.0)  # Default 30s timeout

                if circuit_breaker:
                    response = await circuit_breaker.call(
                        self._call_provider_with_timeout,  # Use timeout wrapper
                        provider,
                        prompt,
                        timeout=timeout,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=system_prompt,
                        role=role,
                        **kwargs,
                    )
                else:
                    response = await self._call_provider_with_timeout(
                        provider,
                        prompt,
                        timeout=timeout,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        system_prompt=system_prompt,
                        role=role,
                        **kwargs,
                    )

                duration = time.time() - start_time

                llm_gateway_requests_total.labels(
                    provider=provider.name, role=role or "unknown", status="success"
                ).inc()
                llm_gateway_latency_seconds.labels(
                    provider=provider.name, role=role or "unknown"
                ).observe(duration)

                if self.health_monitor:
                    health = self.health_monitor.get_provider_health(provider.name)
                    if health:
                        llm_provider_health.labels(provider=provider.name).set(
                            1.0
                            if health.status == ProviderHealthStatus.HEALTHY
                            else 0.5
                        )
                        if health.latency_ms:
                            llm_provider_latency_ms.labels(provider=provider.name).set(
                                health.latency_ms
                            )

                if self.cache:
                    try:
                        await asyncio.to_thread(self.cache.set, cache_key, response)
                    except Exception as e:
                        logger.debug("Cache set error: %s", e)

                return response

            except Exception as e:
                last_error = e
                logger.warning("Provider {provider.name} failed: %s", e)
                llm_gateway_requests_total.labels(
                    provider=provider.name, role=role or "unknown", status="error"
                ).inc()

                if provider != provider_chain[-1]:
                    next_provider = provider_chain[provider_chain.index(provider) + 1]
                    llm_gateway_fallbacks_total.labels(
                        from_provider=provider.name,
                        to_provider=next_provider.name,
                        reason=str(type(e).__name__),
                    ).inc()
                continue

        logger.error("All providers failed, last error: %s", last_error)
        return await self._offline_fallback(prompt, role, last_error)

    async def _call_provider_with_timeout(self, *args, timeout: float = 30.0, **kwargs):
        """Wrapper to enforce timeout on provider calls"""
        try:
            return await asyncio.wait_for(
                self._call_provider(*args, **kwargs), timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Provider call timed out after {timeout}s")

    async def _call_provider(
        self,
        provider: ProviderConfig,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_prompt: Optional[str] = None,
        role: Optional[str] = None,
        **kwargs,
    ) -> LLMGatewayResponse:
        model_name = self._resolve_model_name(provider)
        client = self.get_client(provider.name)

        if not client:
            if (
                provider.name in {"local-qwen", "local-mistral"}
                or provider.is_self_hosted
            ):
                client = self.get_client("ollama")

        if not client:
            raise ValueError(f"No client available for provider: {provider.name}")

        try:
            if (
                provider.name in {"local-qwen", "local-mistral"}
                or provider.is_self_hosted
            ):
                result = await client.generate(
                    prompt=prompt,
                    model_name=model_name,
                    system_prompt=system_prompt or "You are a helpful AI assistant.",
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            else:
                result = await client.generate(
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    system_prompt=system_prompt,
                )

            return LLMGatewayResponse(
                provider=provider.name,
                model=model_name,
                response=result.get("text", ""),
                metadata={
                    "role": role,
                    "usage": result.get("usage", {}),
                    "raw": result.get("raw", {}),
                },
            )
        except Exception as e:
            raise RuntimeError(f"Client generation failed: {e}") from e

    async def _offline_fallback(
        self, prompt: str, role: Optional[str], last_error: Optional[Exception]
    ) -> LLMGatewayResponse:
        logger.warning("All LLM providers unavailable, using offline fallback")

        ollama_client = self.get_client("ollama")
        if ollama_client:
            try:
                result = await ollama_client.generate(
                    prompt=prompt,
                    model_name="llama3",
                    system_prompt="You are a helpful AI assistant.",
                )
                return LLMGatewayResponse(
                    provider="ollama-offline",
                    model="llama3",
                    response=result.get("text", ""),
                    metadata={"role": role, "offline": True, "fallback": True},
                )
            except Exception as e:
                logger.debug("Ollama offline fallback also failed: %s", e)

        return LLMGatewayResponse(
            provider="offline",
            model="none",
            response="Извините, все LLM провайдеры временно недоступны.",
            metadata={
                "role": role,
                "offline": True,
                "fallback": True,
                "fallback_reason": "all_providers_unavailable",
                "error": str(last_error) if last_error else "All providers unavailable",
            },
        )

    def _build_cache_key(
        self,
        prompt: str,
        role: Optional[str],
        temperature: float,
        max_tokens: int,
        system_prompt: Optional[str],
    ) -> str:
        key_data = f"{prompt}:{role}:{temperature}:{max_tokens}:{system_prompt or ''}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def _build_provider_chain(self, role: Optional[str]) -> List[ProviderConfig]:
        if not self.manager or not self.manager.has_configuration():
            return []

        providers: List[ProviderConfig] = []
        seen = set()
        healthy_providers = set()
        if self.health_monitor:
            healthy_providers = set(self.health_monitor.get_healthy_providers())

        active = self.manager.get_active_provider()
        if active and active.name not in seen:
            if not self.health_monitor or active.name in healthy_providers:
                providers.append(active)
                seen.add(active.name)

        if role:
            override = self.manager.get_fallback_chain(role)
            if override:
                primary_name = override.get("primary")
                chain_names = override.get("chain", [])

                for name in [primary_name, *(chain_names or [])]:
                    if not isinstance(name, str):
                        continue
                    provider = self.manager.get_provider(name)
                    if provider and provider.enabled and provider.name not in seen:
                        if (
                            not self.health_monitor
                            or provider.name in healthy_providers
                        ):
                            providers.append(provider)
                            seen.add(provider.name)

        if not providers:
            openai_provider = (
                self.manager.get_provider("openai") if self.manager else None
            )
            if openai_provider and openai_provider.enabled:
                if not self.health_monitor or openai_provider.name in healthy_providers:
                    providers.append(openai_provider)

        return providers

    def _resolve_model_name(self, provider: ProviderConfig) -> str:
        models_meta = provider.metadata.get("models") if provider.metadata else None
        if isinstance(models_meta, list) and models_meta:
            first = models_meta[0]
            if isinstance(first, dict):
                return first.get("name", "unknown-model")
            if isinstance(first, str):
                return first
        return "unknown-model"

    def _build_offline_fallback_response(
        self,
        provider: str,
        model: str,
        prompt: str,
        role: Optional[str],
        fallback: List[str],
    ) -> LLMGatewayResponse:
        diagnostic = (
            "[LLM offline fallback]\n"
            f"provider: {provider}\n"
            f"model: {model}\n"
            f"fallback_chain: {', '.join(fallback) if fallback else 'none'}\n"
            f"prompt_preview: {prompt[:200]}"
        )
        return LLMGatewayResponse(
            provider=provider,
            model=model,
            response=diagnostic,
            metadata={
                "role": role,
                "fallback_chain": fallback,
                "offline": True,
                "fallback": True,
                "fallback_reason": "no_provider_available",
            },
        )

    def _load_simulation_config(self) -> Dict[str, Any]:
        config_path = Path("config/llm_gateway_simulation.yaml")
        if not config_path.exists():
            return {}
        try:
            return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _simulate_response(
        self, prompt: str, role: Optional[str]
    ) -> Optional[LLMGatewayResponse]:
        if (
            not self.simulation_config
            or self.simulation_config.get("mode") != "simulation"
        ):
            return None

        scenarios: Sequence[Dict[str, Any]] = (
            self.simulation_config.get("scenarios") or []
        )
        for scenario in scenarios:
            match_cfg = scenario.get("match", {})
            if role and match_cfg.get("role") and match_cfg.get("role") != role:
                continue
            contains: Sequence[str] = match_cfg.get("contains") or []
            if contains and not any(
                keyword.lower() in prompt.lower() for keyword in contains
            ):
                continue

            response_cfg = scenario.get("response") or {}
            return LLMGatewayResponse(
                provider=response_cfg.get("provider", "simulation-provider"),
                model=response_cfg.get("model", "simulation-model"),
                response=response_cfg.get("text", "[LLM simulation]"),
                metadata={
                    "role": role,
                    "scenario": scenario.get("name"),
                    "simulation": True,
                    **response_cfg.get("metadata", {}),
                },
            )
        return None


def load_llm_gateway() -> LLMGateway:
    return LLMGateway()
