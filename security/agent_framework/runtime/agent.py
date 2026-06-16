
"""Security agent runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class Finding:
    title: str
    severity: str
    description: str
    evidence: str = ""


@dataclass
class AgentResult:
    findings: List[Finding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


class ModuleResult(AgentResult):
    """Alias for clarity."""


class ScanContext:
    """State shared across modules (responses, metadata, etc.)."""

    def __init__(self) -> None:
        self.http_response: Optional["httpx.Response"] = None  # type: ignore[name-defined]
        self.telemetry: dict[str, str] = {}
        self.artifacts: dict[str, str] = {}


class BaseModule:
    """Base class for agent modules."""

    name: str = "base"
    profiles: Iterable[str] = ("web-api",)
    requires_http: bool = True

    def run(
        self,
        target: str,
        client: Optional["httpx.Client"],  # type: ignore[name-defined]
        context: ScanContext,
    ) -> ModuleResult:
        raise NotImplementedError


class SecurityAgent:
    """Security agent orchestrating a chain of modules."""

    def __init__(
        self,
        modules: Optional[Iterable[BaseModule]] = None,
        *,
        profile: str = "web-api",
    ) -> None:
        from .modules import PROFILE_MODULES

        self.profile = profile
        if modules is not None:
            self.modules = list(modules)
        else:
            try:
                self.modules = list(PROFILE_MODULES[profile])
            except KeyError as exc:  # pragma: no cover - defensive branch
                raise ValueError(f"Unknown profile: {profile}") from exc

    def run(
        self,
        target: str,
        *,
        client: Optional["httpx.Client"] = None,  # type: ignore[name-defined]
    ) -> AgentResult:
        import httpx

        result = AgentResult()
        context = ScanContext()

        http_modules = [module for module in self.modules if module.requires_http]
        client_provided = client is not None
        http_client = client if client_provided else None

        if http_modules and http_client is None:
            http_client = httpx.Client(timeout=5.0, follow_redirects=True)

        try:
            for module in self.modules:
                module_result = module.run(target, http_client, context)
                result.findings.extend(module_result.findings)
                result.notes.extend(module_result.notes)
        finally:
            if http_client is not None and not client_provided:
                http_client.close()

        if not result.notes:
            result.notes.append(f"Сканирование {target} завершено.")

        return result


def is_local_path(target: str) -> bool:
    """Helper to detect filesystem targets."""
    if target.startswith(("http://", "https://")):
        return False
    return Path(target).exists()

