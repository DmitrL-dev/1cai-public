
"""Modules for repository static analysis."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from ..agent import BaseModule, Finding, ModuleResult, ScanContext


class SensitiveFilesModule(BaseModule):
    """Detects sensitive files committed to repository."""

    name = "sensitive-files"
    profiles = ("repo-static",)
    requires_http = False

    SENSITIVE_NAMES: Iterable[str] = (
        ".env",
        "id_rsa",
        "id_dsa",
        "secrets.json",
        "credentials.json",
    )

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
                    title="Каталог не найден",
                    severity="medium",
                    description=f"Путь {target} не существует.",
                )
            )
            return result

        if not path.is_dir():
            result.notes.append(f"{target} — не каталог, пропускаем проверку чувствительных файлов.")
            return result

        found = []
        for name in self.SENSITIVE_NAMES:
            candidate = path / name
            if candidate.exists():
                found.append(candidate)

        for candidate in found:
            result.findings.append(
                Finding(
                    title=f"Найден потенциально чувствительный файл: {candidate.name}",
                    severity="high",
                    description=f"Файл {candidate} присутствует в репозитории. Требуется ревизия.",
                    evidence=str(candidate),
                )
            )

        if not found:
            result.notes.append("Чувствительные файлы не обнаружены.")

        return result


SECRET_PATTERN = re.compile(
    r"(api[_-]?key|secret|token|password)\s*[=:]\s*[\"']?[A-Za-z0-9_\-]{12,}",
    re.IGNORECASE,
)


class RepoSecretsModule(BaseModule):
    """Very lightweight search for secrets in text files."""

    name = "repo-secrets"
    profiles = ("repo-static",)
    requires_http = False
    MAX_FILE_SIZE = 512 * 1024  # 512 KB

    def run(
        self,
        target: str,
        client,  # type: ignore[override]
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()
        path = Path(target)

        if not path.exists() or not path.is_dir():
            result.notes.append("Пропуск поиска секретов: путь недоступен или не каталог.")
            return result

        matches = []
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
                continue
            try:
                if file_path.stat().st_size > self.MAX_FILE_SIZE:
                    continue
            except OSError:
                continue

            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for match in SECRET_PATTERN.finditer(text):
                snippet = match.group(0)
                matches.append((file_path, snippet))

        for file_path, snippet in matches:
            result.findings.append(
                Finding(
                    title="Подозрение на секрет в репозитории",
                    severity="critical",
                    description=f"В файле {file_path} найдена строка, похожая на секрет.",
                    evidence=snippet[:120],
                )
            )

        if not matches:
            result.notes.append("Подозрительные секреты не найдены.")

        return result

