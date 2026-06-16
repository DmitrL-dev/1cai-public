
"""HTTP-focused basic security modules."""

from __future__ import annotations

from typing import Iterable

import httpx

from ..agent import BaseModule, Finding, ModuleResult, ScanContext


class HttpReachabilityModule(BaseModule):
    """Performs an initial GET request and records status/outages."""

    name = "http-reachability"
    profiles = ("web-api",)
    requires_http = True

    def run(
        self,
        target: str,
        client: httpx.Client | None,
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()

        if client is None:
            raise ValueError("HTTP client is required for HttpReachabilityModule")

        if context.http_response is None:
            try:
                context.http_response = client.get(target)
            except httpx.RequestError as exc:
                result.findings.append(
                    Finding(
                        title="HTTP endpoint unreachable",
                        severity="critical",
                        description=f"Ошибка подключения к {target}: {exc}",
                        evidence=str(exc),
                    )
                )
                return result

        response = context.http_response
        assert response is not None

        result.notes.append(
            f"HTTP {response.status_code} {response.reason_phrase} for {target}"
        )

        if response.status_code >= 500:
            result.findings.append(
                Finding(
                    title="Сервер вернул 5xx",
                    severity="high",
                    description=f"При обращении к {target} получен код {response.status_code}.",
                    evidence=response.text[:500],
                )
            )
        elif response.status_code >= 400:
            result.findings.append(
                Finding(
                    title="Сервис возвращает ошибку клиента",
                    severity="medium",
                    description=f"Для {target} получен код {response.status_code}.",
                    evidence=response.text[:500],
                )
            )

        return result


class SecurityHeadersModule(BaseModule):
    """Checks for presence of common security headers."""

    name = "security-headers"
    profiles = ("web-api",)
    requires_http = True
    REQUIRED_HEADERS: Iterable[tuple[str, str]] = (
        ("Content-Security-Policy", "medium"),
        ("Strict-Transport-Security", "medium"),
        ("X-Frame-Options", "low"),
        ("X-Content-Type-Options", "low"),
    )

    def run(
        self,
        target: str,
        client: httpx.Client | None,
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()

        if client is None:
            raise ValueError("HTTP client is required for SecurityHeadersModule")

        if context.http_response is None:
            try:
                context.http_response = client.get(target)
            except httpx.RequestError as exc:
                result.notes.append(
                    f"Пропуск проверки заголовков: {target} недоступен ({exc})."
                )
                return result

        response = context.http_response
        assert response is not None

        headers_normalized = {key.lower(): value for key, value in response.headers.items()}
        for header, severity in self.REQUIRED_HEADERS:
            if header.lower() not in headers_normalized:
                result.findings.append(
                    Finding(
                        title=f"Отсутствует заголовок {header}",
                        severity=severity,
                        description=(
                            f"Ответ сервиса {target} не содержит обязательный заголовок {header}."
                        ),
                    )
                )

        if not result.findings:
            result.notes.append(f"Все базовые security-заголовки присутствуют для {target}.")

        return result


class HttpTelemetryModule(BaseModule):
    """Collects basic telemetry from HTTP response."""

    name = "http-telemetry"
    profiles = ("web-api",)
    requires_http = True

    MAX_BODY_SNAPSHOT = 512

    def run(
        self,
        target: str,
        client: httpx.Client | None,
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()

        if client is None:
            raise ValueError("HTTP client is required for HttpTelemetryModule")

        if context.http_response is None:
            try:
                context.http_response = client.get(target)
            except httpx.RequestError as exc:
                result.notes.append(f"Telemetry skipped: {exc}")
                return result

        response = context.http_response
        assert response is not None

        context.telemetry = {
            "url": str(response.request.url),
            "status": str(response.status_code),
            "server": response.headers.get("Server", ""),
            "content_type": response.headers.get("Content-Type", ""),
            "headers": dict(response.headers.items()),
        }
        if response.text:
            context.telemetry["body_preview"] = response.text[: self.MAX_BODY_SNAPSHOT]

        result.notes.append(
            "Собрана телеметрия HTTP (заголовки, статус, превью body)."
        )

        return result

