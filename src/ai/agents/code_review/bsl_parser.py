
"""
BSL Parser
Парсинг BSL кода в AST для анализа
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BSLParser:
    """
    Simplified BSL Parser
    Парсит BSL код и извлекает структуру

    Note: В production использовать tree-sitter с BSL grammar
    Сейчас - упрощенный regex-based парсер
    """

    def __init__(self):
        self.functions = []
        self.procedures = []
        self.variables = []
        self.queries = []

    def parse(self, code: str) -> Dict[str, Any]:
        """Совместимость с упрощённым интерфейсом (`parse` == `parse_file`)."""
        return self.parse_file(code)

    def parse_file(self, code: str) -> Dict[str, Any]:
        """
        Парсит BSL файл

        Returns:
            {
                'functions': [...],
                'procedures': [...],
                'variables': [...],
                'queries': [...],
                'complexity': int,
                'loc': int
            }
        """
        logger.info("Parsing BSL code")

        # Reset state
        self.functions = []
        self.procedures = []
        self.variables = []
        self.queries = []

        # Split into lines
        lines = code.split("\n")

        # Parse functions
        self.functions = self._extract_functions(code, lines)

        # Parse procedures
        self.procedures = self._extract_procedures(code, lines)

        # Parse variables
        self.variables = self._extract_variables(code, lines)

        # Parse queries
        self.queries = self._extract_queries(code, lines)

        # Calculate complexity
        total_complexity = sum(f["complexity"] for f in self.functions)
        total_complexity += sum(p["complexity"] for p in self.procedures)

        return {
            "functions": self.functions,
            "procedures": self.procedures,
            "variables": self.variables,
            "queries": self.queries,
            "total_complexity": total_complexity,
            "loc": len(lines),
            "functions_count": len(self.functions),
            "procedures_count": len(self.procedures),
        }

    def _extract_functions(self, code: str, lines: List[str]) -> List[Dict]:
        """Извлечение функций"""
        functions = []

        # Pattern: Функция ИмяФункции(Параметры) Экспорт?
        pattern = r"Функция\s+(\w+)\s*\((.*?)\)\s*(Экспорт)?"

        matches = re.finditer(pattern, code, re.IGNORECASE | re.DOTALL)

        for match in matches:
            func_name = match.group(1)
            params_str = match.group(2)
            is_export = match.group(3) is not None

            # Find function body
            start_pos = match.end()
            end_pattern = re.search(r"КонецФункции", code[start_pos:], re.IGNORECASE)

            if end_pattern:
                body = code[start_pos : start_pos + end_pattern.start()]
            else:
                body = ""

            # Calculate line numbers
            start_line = code[: match.start()].count("\n") + 1
            end_line = (
                code[: start_pos + end_pattern.end()].count("\n") + 1
                if end_pattern
                else start_line
            )

            # Parse parameters
            params = self._parse_parameters(params_str)

            # Calculate complexity
            complexity = self._calculate_complexity(body)

            functions.append(
                {
                    "name": func_name,
                    "parameters": params,
                    "is_export": is_export,
                    "body": body,
                    "start_line": start_line,
                    "end_line": end_line,
                    "complexity": complexity,
                    "has_documentation": self._has_documentation(code, match.start()),
                }
            )

        return functions

    def _extract_procedures(self, code: str, lines: List[str]) -> List[Dict]:
        """Извлечение процедур"""
        procedures = []

        pattern = r"Процедура\s+(\w+)\s*\((.*?)\)\s*(Экспорт)?"
        matches = re.finditer(pattern, code, re.IGNORECASE | re.DOTALL)

        for match in matches:
            proc_name = match.group(1)
            params_str = match.group(2)
            is_export = match.group(3) is not None

            start_pos = match.end()
            end_pattern = re.search(r"КонецПроцедуры", code[start_pos:], re.IGNORECASE)

            if end_pattern:
                body = code[start_pos : start_pos + end_pattern.start()]
            else:
                body = ""

            start_line = code[: match.start()].count("\n") + 1
            end_line = (
                code[: start_pos + end_pattern.end()].count("\n") + 1
                if end_pattern
                else start_line
            )

            params = self._parse_parameters(params_str)
            complexity = self._calculate_complexity(body)

            procedures.append(
                {
                    "name": proc_name,
                    "parameters": params,
                    "is_export": is_export,
                    "body": body,
                    "start_line": start_line,
                    "end_line": end_line,
                    "complexity": complexity,
                    "has_documentation": self._has_documentation(code, match.start()),
                }
            )

        return procedures

    def _extract_variables(self, code: str, lines: List[str]) -> List[Dict]:
        """Извлечение переменных"""
        variables = []

        # Module-level variables (Перем)
        pattern = r"Перем\s+(\w+)\s*(Экспорт)?"
        matches = re.finditer(pattern, code, re.IGNORECASE)

        for match in matches:
            var_name = match.group(1)
            is_export = match.group(2) is not None
            line_num = code[: match.start()].count("\n") + 1

            variables.append(
                {"name": var_name, "is_export": is_export, "line": line_num}
            )

        return variables

    def _extract_queries(self, code: str, lines: List[str]) -> List[Dict]:
        """Извлечение запросов"""
        queries = []

        # Find query text assignments
        pattern = r'Запрос\.Текст\s*=\s*"(.*?)"'
        matches = re.finditer(pattern, code, re.IGNORECASE | re.DOTALL)

        for match in matches:
            query_text = match.group(1)
            line_num = code[: match.start()].count("\n") + 1

            queries.append(
                {
                    "text": query_text,
                    "line": line_num,
                    "has_parameters": "&" in query_text,
                    "has_index_hint": "ИНДЕКСИРОВАТЬ" in query_text.upper(),
                }
            )

        return queries

    def _parse_parameters(self, params_str: str) -> List[Dict]:
        """Парсинг параметров функции/процедуры"""
        if not params_str.strip():
            return []

        params = []
        for param in params_str.split(","):
            param = param.strip()
            if param:
                # Check for default value
                if "=" in param:
                    param_name, default_value = param.split("=", 1)
                    params.append(
                        {
                            "name": param_name.strip(),
                            "has_default": True,
                            "default_value": default_value.strip(),
                        }
                    )
                else:
                    params.append({"name": param, "has_default": False})

        return params

    def _calculate_complexity(self, body: str) -> int:
        """Расчет цикломатической сложности"""
        complexity = 1  # Base

        # Count decision points
        complexity += len(re.findall(r"\bЕсли\b", body, re.IGNORECASE))
        complexity += len(re.findall(r"\bИначеЕсли\b", body, re.IGNORECASE))
        complexity += len(re.findall(r"\bДля\b", body, re.IGNORECASE))
        complexity += len(re.findall(r"\bДля\s+Каждого\b", body, re.IGNORECASE))
        complexity += len(re.findall(r"\bПока\b", body, re.IGNORECASE))
        complexity += len(re.findall(r"\bПопытка\b", body, re.IGNORECASE))

        return complexity

    def _has_documentation(self, code: str, func_start_pos: int) -> bool:
        """Проверка наличия документации перед функцией"""

        # Ищем комментарии перед функцией (в пределах 10 строк)
        lines_before = code[:func_start_pos].split("\n")[-10:]

        # Проверяем есть ли многострочный комментарий
        comment_block = "\n".join(lines_before)

        # Паттерны документации
        doc_patterns = [
            r"//\s*Функция",
            r"//\s*Параметры:",
            r"//\s*Возвращаемое значение:",
        ]

        return any(
            re.search(pattern, comment_block, re.IGNORECASE) for pattern in doc_patterns
        )
