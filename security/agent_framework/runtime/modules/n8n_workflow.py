
"""Modules for analysing n8n workflow exports."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from ..agent import BaseModule, Finding, ModuleResult, ScanContext


class N8nWorkflowSecurityModule(BaseModule):
    """Static checks for n8n workflow JSON exports."""

    name = "n8n-workflow-security"
    profiles = ("n8n-workflow",)
    requires_http = False

    def run(
        self,
        target: str,
        client,  # type: ignore[override]
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()
        path = Path(target)

        if not path.exists():
            result.findings.append(
                Finding(
                    title="Файл workflow не найден",
                    severity="medium",
                    description=f"Путь {target} не существует.",
                )
            )
            return result

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            result.findings.append(
                Finding(
                    title="Некорректный JSON workflow",
                    severity="medium",
                    description=f"Ошибка разбора {target}: {exc}",
                    evidence=str(exc),
                )
            )
            return result

        nodes = data.get("nodes", []) or []
        if not nodes:
            result.notes.append("Nodes в workflow не обнаружены.")
            return result

        insecure = False
        for node in nodes:
            parameters = node.get("parameters", {}) or {}
            credentials = node.get("credentials")
            node_type = node.get("type")
            node_name = node.get("name")

            url = parameters.get("url") or parameters.get("path") or parameters.get("endpoint")
            if isinstance(url, str) and url.startswith("http://"):
                insecure = True
                result.findings.append(
                    Finding(
                        title=f"Небезопасный URL в узле {node_name}",
                        severity="high",
                        description=f"Узел {node_name} использует небезопасный протокол HTTP: {url}",
                        evidence=str(node_name),
                    )
                )
            if isinstance(url, str):
                parsed = urlparse(url)
                if parsed.username or parsed.password:
                    result.findings.append(
                        Finding(
                            title=f"Узел {node_name} содержит учетные данные в URL",
                            severity="high",
                            description="Найдены hardcoded credentials в URL. Используйте Credentials storage.",
                            evidence=url,
                        )
                    )

            if parameters.get("allowUnauthorizedCerts") is True:
                result.findings.append(
                    Finding(
                        title=f"Разрешены невалидные сертификаты в {node_name}",
                        severity="medium",
                        description="Параметр allowUnauthorizedCerts=true может привести к MITM-атакам.",
                    )
                )

            if node_type == "n8n-nodes-base.httpRequest":
                auth_mode = parameters.get("authentication")
                if auth_mode in (None, "none"):
                    result.findings.append(
                        Finding(
                            title=f"HTTP Request без аутентификации ({node_name})",
                            severity="medium",
                            description="Рекомендуется включить аутентификацию или ограничить доступ.",
                        )
                    )
                if parameters.get("ignoreSSLIssues") is True:
                    result.findings.append(
                        Finding(
                            title=f"HTTP Request отключает проверку SSL ({node_name})",
                            severity="medium",
                            description="ignoreSSLIssues=true ослабляет безопасность соединения.",
                        )
                    )
            if node_type == "n8n-nodes-base.webhook":
                path = parameters.get("path") or ""
                if isinstance(path, str) and len(path.strip()) < 8:
                    result.findings.append(
                        Finding(
                            title=f"Webhook с коротким путём ({node_name})",
                            severity="medium",
                            description=(
                                "Путь вебхука слишком короткий. Рекомендуется использовать более длинный и уникальный путь."
                            ),
                            evidence=path,
                        )
                    )
                if parameters.get("responseMode") == "onReceived":
                    result.notes.append(
                        f"Webhook {node_name} использует responseMode=onReceived — убедитесь в rate limiting."
                    )
                if parameters.get("authentication") in (None, "none"):
                    result.findings.append(
                        Finding(
                            title=f"Webhook без аутентификации ({node_name})",
                            severity="high",
                            description="Webhook не защищён токеном/паролем. Включите auth или HMAC.",
                        )
                    )

            if node_type in {"n8n-nodes-base.function", "n8n-nodes-base.functionItem"}:
                code = parameters.get("functionCode") or parameters.get("code") or ""
                if isinstance(code, str):
                    lowered = code.lower()
                    if "eval(" in lowered or "function(" in lowered:
                        result.findings.append(
                            Finding(
                                title=f"Function node выполняет динамический код ({node_name})",
                                severity="high",
                                description="Обнаружено использование eval/Function. Проверьте безопасность.",
                                evidence=node_name,
                            )
                        )
                    if "http" in lowered and "request" in lowered and "headers" not in lowered:
                        result.notes.append(
                            f"Function {node_name}: проверьте обработку HTTP-запросов (отсутствует контроль заголовков)."
                        )

            if not credentials:
                result.notes.append(f"Узел {node_name} не использует credentials.")

        if not insecure and not result.findings:
            result.notes.append("Workflow прошёл базовые проверки (HTTP, сертификаты, auth).")

        return result

