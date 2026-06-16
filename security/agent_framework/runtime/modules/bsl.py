
"""Static analysis heuristics for 1C BSL sources."""

from __future__ import annotations

import re
from pathlib import Path

from ..agent import BaseModule, Finding, ModuleResult, ScanContext

DANGEROUS_PATTERNS = [
    (re.compile(r"\bВыполнить\s*\("), "Использование Выполнить() может приводить к RCE."),
    (re.compile(r"\bExecute\s*\("), "Использование Execute() может приводить к RCE."),
    (re.compile(r"\bEval\s*\("), "Использование Eval() может приводить к RCE."),
]

DEBUG_PATTERN = re.compile(r"\bСообщить\b|\bMessage\s*\(")
PASSWORD_PATTERN = re.compile(r"Парол[ья]\s*=\s*\"[^\"]*\"")
HTTP_PATTERN = re.compile(r"HTTP(Запрос|Соединение|ЗапросКURL)", re.IGNORECASE)
SQL_CONCAT_PATTERN = re.compile(r"\"SELECT[^\"]*\"\s*\+\s*[^\s]", re.IGNORECASE)
PRIVILEGED_PATTERN = re.compile(r"УстановитьПривилегированныйРежим\s*\(\s*Истина\s*\)", re.IGNORECASE)
HTTP_NEW_PATTERN = re.compile(r"Новый\s+HTTP(Соединение|Запрос)", re.IGNORECASE)
SQL_TEXT_PATTERN = re.compile(r"Запрос\.Текст\s*=", re.IGNORECASE)
PRIVILEGED_PATTERN = re.compile(r"УстановитьПривилегированныйРежим\s*\(\s*Истина\s*\)", re.IGNORECASE)


class BSLStaticSecurityModule(BaseModule):
    """Run simple heuristics over BSL sources."""

    name = "bsl-static-security"
    profiles = ("bsl-1c",)
    requires_http = False

    def run(
        self,
        target: str,
        client,  # type: ignore[override]
        context: ScanContext,
    ) -> ModuleResult:
        result = ModuleResult()
        path = Path(target)

        files: list[Path] = []
        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = [p for p in path.rglob("*") if p.suffix.lower() in {".bsl", ".os"}]
        else:
            result.findings.append(
                Finding(
                    title="BSL путь недоступен",
                    severity="medium",
                    description=f"Путь {target} не найден.",
                )
            )
            return result

        if not files:
            result.notes.append("BSL-файлы не найдены.")
            return result

        for file_path in files:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                result.notes.append(f"Не удалось прочитать {file_path}.")
                continue

            for pattern, description in DANGEROUS_PATTERNS:
                if pattern.search(content):
                    result.findings.append(
                        Finding(
                            title=f"Опасное выполнение кода ({file_path.name})",
                            severity="high",
                            description=description,
                            evidence=str(file_path),
                        )
                    )

            if DEBUG_PATTERN.search(content):
                result.findings.append(
                    Finding(
                        title=f"Отладочные вызовы в {file_path.name}",
                        severity="low",
                        description="Обнаружены вызовы Сообщить()/Message(). Убедитесь, что они отключены в проде.",
                        evidence=str(file_path),
                    )
                )

            if PASSWORD_PATTERN.search(content):
                result.findings.append(
                    Finding(
                        title=f"Подозрение на хардкод пароля ({file_path.name})",
                        severity="medium",
                        description="Найдено присваивание переменной *Пароль*. Проверьте, что секреты не захардкожены.",
                        evidence=str(file_path),
                    )
                )

            if HTTP_PATTERN.search(content):
                result.notes.append(
                    f"{file_path.name}: обнаружены HTTP вызовы, убедитесь в проверке сертификатов/таймаутов."
                )
            if HTTP_NEW_PATTERN.search(content):
                result.findings.append(
                    Finding(
                        title=f"Создаётся HTTP соединение ({file_path.name})",
                        severity="low",
                        description="Проверьте использование HTTPS, таймаутов и обработку ошибок.",
                        evidence=str(file_path),
                    )
                )

            if SQL_CONCAT_PATTERN.search(content):
                result.findings.append(
                    Finding(
                        title=f"Потенциальная SQL-конкатенация ({file_path.name})",
                        severity="medium",
                        description="Обнаружено построение SQL через конкатенацию — проверьте защиту от инъекций.",
                        evidence=str(file_path),
                    )
                )

            if SQL_TEXT_PATTERN.search(content) and "+" in content:
                result.findings.append(
                    Finding(
                        title=f"Динамическое построение SQL ({file_path.name})",
                        severity="medium",
                        description="Запрос.Текст формируется динамически. Убедитесь в безопасной подстановке параметров.",
                        evidence=str(file_path),
                    )
                )

            if PRIVILEGED_PATTERN.search(content):
                result.findings.append(
                    Finding(
                        title=f"Включён привилегированный режим ({file_path.name})",
                        severity="high",
                        description="Обнаружено УстановитьПривилегированныйРежим(Истина). Проверьте необходимость и безопасность.",
                        evidence=str(file_path),
                    )
                )

        if not result.findings:
            result.notes.append("BSL-файлы прошли базовые проверки.")

        return result

