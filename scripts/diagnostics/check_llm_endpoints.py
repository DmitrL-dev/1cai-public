
#!/usr/bin/env python3
"""
Diagnostics for LLM providers declared in config/llm_providers.yaml.

Usage:
    python scripts/diagnostics/check_llm_endpoints.py
    python scripts/diagnostics/check_llm_endpoints.py --provider openai --timeout 5
    python scripts/diagnostics/check_llm_endpoints.py --config config/llm_providers.local.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
import yaml

DEFAULT_CONFIG = Path("config/llm_providers.yaml")


@dataclass
class ProviderCheckResult:
    name: str
    url: Optional[str]
    status: str
    http_status: Optional[int] = None
    message: Optional[str] = None
    latency_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LLMEndpointChecker:
    def __init__(self, timeout: float = 5.0) -> None:
        self.timeout = timeout

    def _resolve_url(self, provider_name: str, config: Dict[str, Any]) -> Optional[str]:
        if "health_url" in config:
            return config["health_url"]
        if "base_url" in config:
            return config["base_url"]
        return None

    def check_provider(
        self,
        provider_name: str,
        provider_config: Dict[str, Any],
        method: str = "GET",
    ) -> ProviderCheckResult:
        url = self._resolve_url(provider_name, provider_config)
        if not url:
            return ProviderCheckResult(
                name=provider_name,
                url=None,
                status="skipped",
                message="No base_url/health_url provided",
            )

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.request(method.upper(), url)
                ok = response.status_code < 400
                return ProviderCheckResult(
                    name=provider_name,
                    url=url,
                    status="ok" if ok else "fail",
                    http_status=response.status_code,
                    message=None if ok else response.text[:200],
                    latency_ms=response.elapsed.total_seconds() * 1000,
                )
        except httpx.RequestError as exc:
            return ProviderCheckResult(
                name=provider_name,
                url=url,
                status="error",
                message=str(exc),
            )


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data


def iterate_providers(
    providers: Dict[str, Any],
    selected: Optional[Iterable[str]] = None,
) -> Iterable[tuple[str, Dict[str, Any]]]:
    if not selected:
        yield from providers.items()
        return

    selected_set = {item.lower() for item in selected}
    for name, cfg in providers.items():
        if name.lower() in selected_set:
            yield name, cfg


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check availability of configured LLM providers.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to llm_providers.yaml (default: config/llm_providers.yaml)",
    )
    parser.add_argument(
        "--provider",
        "-p",
        action="append",
        help="Provider name to check (can be specified multiple times).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP timeout in seconds (default: 5).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    providers = config.get("providers", {})
    if not providers:
        print("No providers defined in config.", file=sys.stderr)
        return 1

    checker = LLMEndpointChecker(timeout=args.timeout)
    results: List[ProviderCheckResult] = []

    for name, cfg in iterate_providers(providers, args.provider):
        results.append(checker.check_provider(name, cfg))

    if args.json:
        json.dump([res.to_dict() for res in results], sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print("LLM Endpoint Diagnostics")
        print("========================")
        for res in results:
            detail = f"{res.status.upper():8} {res.name:15}"
            if res.url:
                detail += f" {res.url}"
            if res.http_status is not None:
                detail += f" [{res.http_status}]"
            if res.latency_ms is not None:
                detail += f" {res.latency_ms:.1f}ms"
            print(detail)
            if res.message:
                print(f"  -> {res.message}")

    failures = [res for res in results if res.status in {"fail", "error"}]
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

