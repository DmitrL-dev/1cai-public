"""Deterministic BSL security scanner used by the code-review pipeline."""

import re
from typing import Any, Dict, List


_QUERY_TEXT_PATTERN = re.compile(r"\b(select|выбрать)\b", flags=re.IGNORECASE)
_QUERY_ASSIGNMENT_PATTERN = re.compile(
    r"(запрос\s*\.\s*текст|query\s*\.\s*text|текстзапроса)\s*=.*\+",
    flags=re.IGNORECASE | re.DOTALL,
)
_DYNAMIC_EXECUTION_PATTERN = re.compile(
    r"(?<!\.)\b(выполнить|execute)\s*\(", flags=re.IGNORECASE
)
_XSS_PATTERN = re.compile(
    r"<\s*script\b|javascript\s*:|on(?:click|load|error)\s*=",
    flags=re.IGNORECASE,
)
_CREDENTIAL_PATTERN = re.compile(
    r"\b("
    r"password|passwd|pwd|api[_-]?key|apikey|token|secret(?:key)?|"
    r"пароль|токен|секрет|ключ|apiключ"
    r")\b\s*(?:=|:=)\s*[\"'][^\"']{4,}[\"']",
    flags=re.IGNORECASE,
)


class SecurityScanner:
    """Detects high-confidence security issues without external services."""

    def scan(self, code: str, ast: Dict[str, Any]) -> List[Dict[str, Any]]:
        return (
            self.scan_sql_injection(code, ast)
            + self.scan_hardcoded_credentials(code, ast)
            + self.scan_dynamic_execution(code, ast)
            + self.scan_xss_vulnerabilities(code, ast)
        )

    def scan_sql_injection(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        if "+" not in code or not _QUERY_TEXT_PATTERN.search(code):
            return []
        if not _QUERY_ASSIGNMENT_PATTERN.search(code):
            return []
        return [
            {
                "type": "SQL_INJECTION",
                "severity": "CRITICAL",
                "category": "security",
                "issue": "Dynamic query text concatenation can lead to SQL injection.",
                "line": self._line_of_first_marker(
                    code, ("Запрос.Текст", "Query.Text", "SELECT", "ВЫБРАТЬ")
                ),
                "rule_id": "bsl-dynamic-query-concat",
                "source": "deterministic_scanner",
            }
        ]

    def scan_hardcoded_credentials(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        issues = []
        for match in _CREDENTIAL_PATTERN.finditer(code):
            issues.append(
                {
                    "type": "HARDCODED_CREDENTIALS",
                    "severity": "CRITICAL",
                    "category": "security",
                    "issue": "Hardcoded credential detected.",
                    "line": self._line_for_index(code, match.start()),
                    "rule_id": "hardcoded-credential",
                    "source": "deterministic_scanner",
                }
            )
        return issues

    def scan_dynamic_execution(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        issues = []
        for match in _DYNAMIC_EXECUTION_PATTERN.finditer(code):
            issues.append(
                {
                    "type": "DYNAMIC_EXECUTION",
                    "severity": "HIGH",
                    "category": "security",
                    "issue": "Dynamic code execution detected.",
                    "line": self._line_for_index(code, match.start()),
                    "rule_id": "bsl-dynamic-execution",
                    "source": "deterministic_scanner",
                }
            )
        return issues

    def scan_xss_vulnerabilities(
        self, code: str, ast: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        issues = []
        for match in _XSS_PATTERN.finditer(code):
            issues.append(
                {
                    "type": "XSS",
                    "severity": "HIGH",
                    "category": "security",
                    "issue": "Potential script injection in generated HTML.",
                    "line": self._line_for_index(code, match.start()),
                    "rule_id": "html-script-injection",
                    "source": "deterministic_scanner",
                }
            )
        return issues

    def _line_of(self, code: str, needle: str) -> int:
        index = code.upper().find(needle.upper())
        return self._line_for_index(code, index if index >= 0 else 0)

    def _line_of_first_marker(self, code: str, markers: tuple[str, ...]) -> int:
        lowered = code.casefold()
        indexes = [lowered.find(marker.casefold()) for marker in markers]
        indexes = [index for index in indexes if index >= 0]
        return self._line_for_index(code, min(indexes) if indexes else 0)

    def _line_for_index(self, code: str, index: int) -> int:
        return code[:index].count("\n") + 1


__all__ = ["SecurityScanner"]
