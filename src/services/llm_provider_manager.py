
from __future__ import annotations

"""
Управление конфигурацией провайдеров LLM и fallback-цепочками.

Файл работает поверх `config/llm_providers.yaml` и (опционально) читает состояние
из `output/current_llm_backend.json`.

При отсутствии конфигурации модуль остаётся пассивным, чтобы не ломать текущий
функционал.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/llm_providers.yaml")
STATE_PATH = Path("output/current_llm_backend.json")


@dataclass
class ProviderConfig:
    name: str
    provider_type: str
    priority: int
    base_url: str
    enabled: bool = True
    status: str = "active"
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def is_self_hosted(self) -> bool:
        return self.provider_type in {"self_hosted", "self-hosted"}


class LLMProviderManager:
    """Загрузка конфигураций и предоставление удобного API."""

    def __init__(
        self, config_path: Path = CONFIG_PATH, state_path: Path = STATE_PATH
    ) -> None:
        self.config_path = config_path
        self.state_path = state_path
        self.providers: Dict[str, ProviderConfig] = {}
        self.fallback_matrix: Dict[str, Dict[str, List[str] | str]] = {}
        self.health_config: Dict[str, int] = {}
        self.active_provider: Optional[str] = None

        self._load_config()
        self._load_state()

    def _load_config(self) -> None:
        if not self.config_path.exists():
            logger.debug("LLM provider config not found: %s", self.config_path)
            return

        try:
            raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse %s: %s", self.config_path, exc)
            return

        if not isinstance(raw, dict):
            logger.warning("Unexpected format in %s", self.config_path)
            return

        for name, cfg in (raw.get("providers") or {}).items():
            provider = ProviderConfig(
                name=name,
                provider_type=cfg.get("type", "remote"),
                priority=int(cfg.get("priority", 0)),
                base_url=cfg.get("base_url", ""),
                enabled=bool(cfg.get("enabled", True)),
                status=cfg.get("status", "active"),
                metadata={
                    k: v
                    for k, v in cfg.items()
                    if k not in {"type", "priority", "base_url", "enabled", "status"}
                },
            )
            self.providers[name] = provider

        self.fallback_matrix = raw.get("fallback_matrix", {}) or {}
        self.health_config = raw.get("health_checks", {}) or {}

    def _load_state(self) -> None:
        if not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            provider = data.get("provider")
            if provider in self.providers:
                self.active_provider = provider
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read LLM state %s: %s", self.state_path, exc)

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        return self.providers.get(name)

    def get_fallback_chain(self, role: str) -> Optional[Dict[str, List[str] | str]]:
        return self.fallback_matrix.get(role)

    def get_active_provider(self) -> Optional[ProviderConfig]:
        if self.active_provider:
            return self.providers.get(self.active_provider)
        return None

    def available_providers(self) -> List[ProviderConfig]:
        return [p for p in self.providers.values() if p.enabled]

    def has_configuration(self) -> bool:
        return bool(self.providers)


def load_llm_provider_manager() -> LLMProviderManager:
    """Удобный хэлпер для ленивой загрузки."""
    return LLMProviderManager()
