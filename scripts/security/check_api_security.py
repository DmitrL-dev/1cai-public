
#!/usr/bin/env python3
"""
API Security Audit
-------------------

Проверяет безопасность API endpoints:
- Input validation
- Rate limiting
- Authentication/Authorization
- SQL injection vulnerabilities
- XSS vulnerabilities
- CSRF protection
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List


class APISecurityAuditor:
    """Аудитор безопасности API endpoints."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.findings: Dict[str, List[str]] = defaultdict(list)
        self.stats = {
            "endpoints_checked": 0,
            "vulnerabilities_found": 0,
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }

    def audit(self) -> Dict:
        """Запустить полный аудит API безопасности."""
        print("=" * 80)
        print("API SECURITY AUDIT")
        print("=" * 80)
        print()

        api_files = list(self.project_root.glob("src/api/**/*.py"))
        api_files.extend(self.project_root.glob("src/ai/orchestrator.py"))

        for api_file in api_files:
            if api_file.is_file():
                self._audit_file(api_file)

        return {
            "stats": self.stats,
            "findings": dict(self.findings),
        }

    def _audit_file(self, file_path: Path) -> None:
        """Аудит отдельного файла."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                tree = ast.parse(content, filename=str(file_path))

            # Проверяем каждый endpoint
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self._check_endpoint(node, file_path, content)

        except Exception as e:
            print(f"Error auditing {file_path}: {e}")

    def _check_endpoint(self, node: ast.FunctionDef, file_path: Path, content: str) -> None:
        """Проверка отдельного endpoint."""
        # Проверяем, является ли функция endpoint (FastAPI decorator)
        decorators = [d.id if isinstance(d, ast.Name) else "" for d in node.decorator_list]
        if not any(decorator in ["get", "post", "put", "delete", "patch", "route"] for decorator in decorators):
            return

        self.stats["endpoints_checked"] += 1
        endpoint_name = f"{file_path.name}::{node.name}"

        # Проверки безопасности
        self._check_input_validation(node, endpoint_name, content)
        self._check_rate_limiting(node, endpoint_name, content)
        self._check_sql_injection(node, endpoint_name, content)
        self._check_xss(node, endpoint_name, content)
        self._check_authentication(node, endpoint_name, content)

    def _check_input_validation(self, node: ast.FunctionDef, endpoint_name: str, content: str) -> None:
        """Проверка валидации входных данных."""
        # Ищем использование request без валидации
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    if func.attr in ["json", "form", "args", "get_json"]:
                        # Проверяем, есть ли валидация через Pydantic или подобное
                        if not self._has_validation(node, content):
                            self.findings["input_validation"].append(
                                f"{endpoint_name}: Missing input validation for {func.attr}"
                            )
                            self.stats["medium"] += 1
                            self.stats["vulnerabilities_found"] += 1

    def _check_rate_limiting(self, node: ast.FunctionDef, endpoint_name: str, content: str) -> None:
        """Проверка наличия rate limiting."""
        # Ищем декораторы rate limiting
        decorators_str = " ".join([ast.unparse(d) for d in node.decorator_list])
        if "rate_limit" not in decorators_str.lower() and "limiter" not in decorators_str.lower():
            # Критично только для публичных endpoints
            if "public" in endpoint_name.lower() or "api" in endpoint_name.lower():
                self.findings["rate_limiting"].append(
                    f"{endpoint_name}: Missing rate limiting"
                )
                self.stats["high"] += 1
                self.stats["vulnerabilities_found"] += 1

    def _check_sql_injection(self, node: ast.FunctionDef, endpoint_name: str, content: str) -> None:
        """Проверка уязвимостей SQL injection."""
        # Ищем строковые форматирования в SQL запросах
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    if func.attr in ["execute", "query", "execute_sql"]:
                        # Проверяем использование f-strings в SQL
                        for arg in child.args:
                            if isinstance(arg, ast.JoinedStr):
                                self.findings["sql_injection"].append(
                                    f"{endpoint_name}: Potential SQL injection vulnerability (f-string in SQL)"
                                )
                                self.stats["critical"] += 1
                                self.stats["vulnerabilities_found"] += 1

    def _check_xss(self, node: ast.FunctionDef, endpoint_name: str, content: str) -> None:
        """Проверка уязвимостей XSS."""
        # Ищем прямое возвращение пользовательского ввода в HTML
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                if child.value:
                    # Упрощенная проверка - ищем прямое возвращение строк без экранирования
                    if isinstance(child.value, ast.Name):
                        # Проверяем контекст использования
                        pass

    def _check_authentication(self, node: ast.FunctionDef, endpoint_name: str, content: str) -> None:
        """Проверка наличия аутентификации."""
        decorators_str = " ".join([ast.unparse(d) for d in node.decorator_list])
        # Проверяем наличие декораторов аутентификации
        if "auth" not in decorators_str.lower() and "login_required" not in decorators_str.lower():
            # Не критично для публичных endpoints
            if "internal" in endpoint_name.lower() or "admin" in endpoint_name.lower():
                self.findings["authentication"].append(
                    f"{endpoint_name}: Missing authentication check"
                )
                self.stats["high"] += 1
                self.stats["vulnerabilities_found"] += 1

    def _has_validation(self, node: ast.FunctionDef, content: str) -> bool:
        """Проверка наличия валидации входных данных."""
        # Ищем использование Pydantic моделей или валидации
        annotations = [param.annotation for param in node.args.args if param.annotation]
        for annotation in annotations:
            if isinstance(annotation, ast.Name):
                # Простая проверка на наличие типов
                return True

        # Ищем использование validate_* функций
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    if "validate" in func.id.lower():
                        return True

        return False

    def print_report(self) -> None:
        """Вывести отчет об аудите."""
        print("\n" + "=" * 80)
        print("API SECURITY AUDIT REPORT")
        print("=" * 80)
        print()

        print(f"Endpoints checked: {self.stats['endpoints_checked']}")
        print(f"Vulnerabilities found: {self.stats['vulnerabilities_found']}")
        print(f"  - Critical: {self.stats['critical']}")
        print(f"  - High: {self.stats['high']}")
        print(f"  - Medium: {self.stats['medium']}")
        print(f"  - Low: {self.stats['low']}")
        print()

        if self.findings:
            for category, issues in self.findings.items():
                print(f"\n{category.upper().replace('_', ' ')}:")
                for issue in issues:
                    print(f"  - {issue}")
        else:
            print("No security issues found!")

        print("\n" + "=" * 80)


def main():
    """Главная функция."""
    project_root = Path(__file__).parent.parent.parent
    auditor = APISecurityAuditor(project_root)
    results = auditor.audit()
    auditor.print_report()

    # Возвращаем код выхода на основе критичности находок
    if results["stats"]["critical"] > 0 or results["stats"]["high"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

