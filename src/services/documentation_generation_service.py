"""
Documentation Generation Service
Автоматическая генерация документации из кода
Версия: 1.0.0
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    """Генератор документации из кода"""

    def __init__(self):
        self.supported_languages = ["bsl", "typescript", "python", "javascript"]

    def generate_documentation(
        self,
        code: str,
        language: str = "bsl",
        function_name: Optional[str] = None,
        format: str = "markdown",
    ) -> Dict[str, Any]:
        """
        Генерация документации из кода

        Args:
            code: Исходный код
            language: Язык программирования
            function_name: Имя функции (опционально)
            format: Формат документации (markdown, html, plain)

        Returns:
            Словарь с документацией
        """
        if language == "bsl":
            return self._generate_bsl_documentation(code, function_name, format)
        elif language in ["typescript", "javascript"]:
            return self._generate_ts_documentation(code, function_name, format)
        elif language == "python":
            return self._generate_python_documentation(code, function_name, format)
        else:
            raise ValueError(f"Неподдерживаемый язык: {language}")

    def _generate_bsl_documentation(
        self, code: str, function_name: Optional[str], format: str
    ) -> Dict[str, Any]:
        """Генерация документации для BSL"""

        doc = {
            "title": f"Документация для {function_name or 'кода'}",
            "language": "bsl",
            "generated_at": datetime.now().isoformat(),
            "sections": [],
        }

        # Извлечение функций
        functions = self._extract_bsl_functions(code)

        for func in functions:
            section = {
                "name": func["name"],
                "type": func["type"],  # Процедура или Функция
                "signature": func["signature"],
                "parameters": func["params"],
                "description": func["description"],
                "examples": func.get("examples", []),
                "return_value": func.get("return_value"),
                "notes": func.get("notes", []),
            }

            doc["sections"].append(section)

        # Генерация текста документации
        if format == "markdown":
            doc["content"] = self._format_markdown_bsl(doc)
        elif format == "html":
            doc["content"] = self._format_html_bsl(doc)
        else:
            doc["content"] = self._format_plain_bsl(doc)

        return doc

    def _extract_bsl_functions(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение функций из BSL кода с комментариями"""
        functions = []
        lines = code.split("\n")

        current_function = None
        in_function = False
        function_lines = []
        comment_buffer = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Сохранение комментариев перед функцией
            if stripped.startswith("//") or (
                stripped.startswith("'") and not in_function
            ):
                comment_buffer.append(stripped.lstrip("/'").strip())
                continue

            # Начало функции
            func_match = re.search(
                r"^\s*(Функция|Процедура)\s+(\w+)\s*(?:\(([^)]*)\))?",
                stripped,
                re.IGNORECASE,
            )
            if func_match:
                # Сохраняем предыдущую функцию
                if current_function and function_lines:
                    current_function["code"] = "\n".join(function_lines)
                    functions.append(current_function)

                # Начинаем новую функцию
                func_type = func_match.group(1)
                func_name = func_match.group(2)
                params_str = func_match.group(3) or ""

                current_function = {
                    "name": func_name,
                    "type": "Функция" if "Функция" in func_type else "Процедура",
                    "signature": line.strip(),
                    "params": self._parse_bsl_params(params_str),
                    "description": "\n".join(comment_buffer).strip()
                    or f"{func_type} {func_name}",
                    "code": "",
                    "examples": [],
                    "notes": [],
                }

                function_lines = [line]
                comment_buffer = []
                in_function = True
                continue

            # Если внутри функции
            if in_function and current_function:
                function_lines.append(line)

                # Конец функции
                if re.search(
                    r"\s*Конец(?:Функции|Процедуры)\s*$", stripped, re.IGNORECASE
                ):
                    current_function["code"] = "\n".join(function_lines)

                    # Извлечение return значения (для функций)
                    if current_function["type"] == "Функция":
                        return_match = re.search(
                            r"Возврат\s+([^;]+)",
                            current_function["code"],
                            re.IGNORECASE,
                        )
                        if return_match:
                            current_function["return_value"] = return_match.group(
                                1
                            ).strip()

                    functions.append(current_function)
                    current_function = None
                    in_function = False
                    function_lines = []

        # Сохраняем последнюю функцию
        if current_function and function_lines:
            current_function["code"] = "\n".join(function_lines)
            functions.append(current_function)

        return functions

    def _parse_bsl_params(self, params_str: str) -> List[Dict[str, str]]:
        """Парсинг параметров BSL функции"""
        if not params_str.strip():
            return []

        params = []
        for param in params_str.split(","):
            param = param.strip()
            if not param:
                continue

            # Формат: ИмяПараметра, ИмяПараметра = ЗначениеПоУмолчанию, ИмяПараметра ПередачаПоЗначению
            parts = param.split("=")
            param_name = parts[0].strip().split()[0]
            default_value = parts[1].strip() if len(parts) > 1 else None

            params.append(
                {
                    "name": param_name,
                    "type": "Any",  # BSL динамическая типизация
                    "default": default_value,
                    "description": "",
                }
            )

        return params

    def _format_markdown_bsl(self, doc: Dict[str, Any]) -> str:
        """Форматирование в Markdown"""
        lines = [f"# {doc['title']}\n"]
        lines.append(f"**Язык:** {doc['language'].upper()}  \n")
        lines.append(f"**Дата генерации:** {doc['generated_at']}  \n\n")
        lines.append("---\n\n")

        for section in doc["sections"]:
            lines.append(f"## {section['type']} {section['name']}\n\n")

            # Описание
            if section["description"]:
                lines.append(f"{section['description']}\n\n")

            # Сигнатура
            lines.append("```bsl\n")
            lines.append(f"{section['signature']}\n")
            lines.append("```\n\n")

            # Параметры
            if section["parameters"]:
                lines.append("### Параметры\n\n")
                lines.append("| Имя | Тип | Описание |\n")
                lines.append("|-----|-----|----------|\n")
                for param in section["parameters"]:
                    lines.append(
                        f"| `{param['name']}` | {param.get('type', 'Any')} | {param.get('description', '')} |\n"
                    )
                lines.append("\n")

            # Возвращаемое значение
            if section.get("return_value"):
                lines.append("### Возвращаемое значение\n\n")
                lines.append(f"`{section['return_value']}`\n\n")

            # Примеры
            if section.get("examples"):
                lines.append("### Примеры\n\n")
                for example in section["examples"]:
                    lines.append("```bsl\n")
                    lines.append(f"{example}\n")
                    lines.append("```\n\n")

            lines.append("---\n\n")

        return "".join(lines)

    def _format_html_bsl(self, doc: Dict[str, Any]) -> str:
        """Форматирование в HTML"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{doc['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #555; margin-top: 30px; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
    </style>
</head>
<body>
    <h1>{doc['title']}</h1>
    <p><strong>Язык:</strong> {doc['language'].upper()}</p>
    <p><strong>Дата генерации:</strong> {doc['generated_at']}</p>
    <hr>
"""

        for section in doc["sections"]:
            html += f"    <h2>{section['type']} {section['name']}</h2>\n"

            if section["description"]:
                html += f"    <p>{section['description']}</p>\n"

            html += f"    <pre><code>{section['signature']}</code></pre>\n"

            if section["parameters"]:
                html += "    <h3>Параметры</h3>\n"
                html += "    <table>\n"
                html += "        <tr><th>Имя</th><th>Тип</th><th>Описание</th></tr>\n"
                for param in section["parameters"]:
                    html += f"        <tr><td><code>{param['name']}</code></td><td>{param.get('type', 'Any')}</td><td>{param.get('description', '')}</td></tr>\n"
                html += "    </table>\n"

            if section.get("return_value"):
                html += "    <h3>Возвращаемое значение</h3>\n"
                html += f"    <p><code>{section['return_value']}</code></p>\n"

            html += "    <hr>\n"

        html += """</body>
</html>"""

        return html

    def _format_plain_bsl(self, doc: Dict[str, Any]) -> str:
        """Форматирование в plain text"""
        lines = [f"{doc['title']}\n"]
        lines.append(f"Язык: {doc['language'].upper()}\n")
        lines.append(f"Дата генерации: {doc['generated_at']}\n")
        lines.append("=" * 80 + "\n\n")

        for section in doc["sections"]:
            lines.append(f"{section['type']} {section['name']}\n")
            lines.append("-" * 80 + "\n")

            if section["description"]:
                lines.append(f"{section['description']}\n\n")

            lines.append(f"Сигнатура: {section['signature']}\n\n")

            if section["parameters"]:
                lines.append("Параметры:\n")
                for param in section["parameters"]:
                    lines.append(f"  - {param['name']}: {param.get('type', 'Any')}\n")
                lines.append("\n")

            if section.get("return_value"):
                lines.append(f"Возвращает: {section['return_value']}\n\n")

            lines.append("\n")

        return "".join(lines)

    def _generate_ts_documentation(
        self, code: str, function_name: Optional[str], format: str
    ) -> Dict[str, Any]:
        """
        Генерация документации для TypeScript/JavaScript
        Использует регулярные выражения для парсинга (AST parsing требует доп. библиотек)
        """
        doc = {
            "title": f"TypeScript Documentation - {function_name or 'Code'}",
            "language": "typescript",
            "generated_at": datetime.now().isoformat(),
            "sections": [],
        }

        # Извлечение функций и классов
        functions = self._extract_ts_functions(code)
        classes = self._extract_ts_classes(code)

        # Добавляем функции
        for func in functions:
            section = {
                "name": func["name"],
                "type": func["type"],  # function, async function, arrow function
                "signature": func["signature"],
                "parameters": func["params"],
                "return_type": func.get("return_type", "any"),
                "description": func["description"],
                "examples": func.get("examples", []),
            }
            doc["sections"].append(section)

        # Добавляем классы
        for cls in classes:
            section = {
                "name": cls["name"],
                "type": "class",
                "description": cls["description"],
                "methods": cls["methods"],
                "properties": cls.get("properties", []),
            }
            doc["sections"].append(section)

        # Генерация текста
        if format == "markdown":
            doc["content"] = self._format_markdown_ts(doc)
        else:
            doc["content"] = self._format_plain_ts(doc)

        return doc

    def _extract_ts_functions(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение функций из TypeScript/JavaScript"""
        functions = []

        # Паттерны для функций
        patterns = [
            # function name(params): returnType
            r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?::\s*([^{]+))?",
            # const name = (params): returnType =>
            r"(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)(?::\s*([^=]+))?\s*=>",
            # name: (params): returnType =>
            r"(\w+):\s*\(([^)]*)\)(?::\s*([^=]+))?\s*=>",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, code):
                func_name = match.group(1)
                params_str = match.group(2) if len(match.groups()) > 1 else ""
                return_type = (
                    match.group(3).strip()
                    if len(match.groups()) > 2 and match.group(3)
                    else "any"
                )

                # Извлечение JSDoc комментариев
                jsdoc = self._extract_jsdoc(code, match.start())

                functions.append(
                    {
                        "name": func_name,
                        "type": "async function"
                        if "async" in code[max(0, match.start() - 20) : match.start()]
                        else "function",
                        "signature": match.group(0),
                        "params": self._parse_ts_params(params_str),
                        "return_type": return_type,
                        "description": jsdoc.get(
                            "description", f"Function {func_name}"
                        ),
                        "examples": jsdoc.get("examples", []),
                    }
                )

        return functions

    def _extract_ts_classes(self, code: str) -> List[Dict[str, Any]]:
        """Извлечение классов из TypeScript"""
        classes = []

        # Паттерн для классов
        class_pattern = r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?\s*{"

        for match in re.finditer(class_pattern, code):
            class_name = match.group(1)
            extends = match.group(2) if len(match.groups()) > 1 else None

            # Извлечение JSDoc
            jsdoc = self._extract_jsdoc(code, match.start())

            classes.append(
                {
                    "name": class_name,
                    "extends": extends,
                    "description": jsdoc.get("description", f"Class {class_name}"),
                    "methods": [],  # Можно добавить парсинг методов
                    "properties": [],
                }
            )

        return classes

    def _extract_jsdoc(self, code: str, position: int) -> Dict[str, Any]:
        """Извлечение JSDoc комментариев"""
        # Ищем JSDoc комментарий перед функцией
        before_code = code[:position]
        jsdoc_pattern = r"/\*\*([^*]|\*(?!/))*\*/"
        matches = list(re.finditer(jsdoc_pattern, before_code))

        if not matches:
            return {"description": "", "examples": []}

        last_match = matches[-1]
        jsdoc_text = last_match.group(0)

        # Парсинг JSDoc
        description_lines = []
        examples = []

        for line in jsdoc_text.split("\n"):
            line = line.strip().lstrip("*").strip()
            if line.startswith("@example"):
                examples.append(line.replace("@example", "").strip())
            elif not line.startswith("@") and line and line != "/**" and line != "*/":
                description_lines.append(line)

        return {
            "description": " ".join(description_lines),
            "examples": examples,
        }

    def _parse_ts_params(self, params_str: str) -> List[Dict[str, str]]:
        """Парсинг параметров TypeScript"""
        if not params_str.strip():
            return []

        params = []
        for param in params_str.split(","):
            param = param.strip()
            if not param:
                continue

            # Формат: name: type = defaultValue
            parts = param.split(":")
            param_name = parts[0].strip()

            param_type = "any"
            default_value = None

            if len(parts) > 1:
                type_part = parts[1].strip()
                if "=" in type_part:
                    type_default = type_part.split("=")
                    param_type = type_default[0].strip()
                    default_value = type_default[1].strip()
                else:
                    param_type = type_part

            params.append(
                {
                    "name": param_name,
                    "type": param_type,
                    "default": default_value,
                    "description": "",
                }
            )

        return params

    def _format_markdown_ts(self, doc: Dict[str, Any]) -> str:
        """Форматирование TypeScript документации в Markdown"""
        lines = [f"# {doc['title']}\n\n"]
        lines.append(f"**Language:** TypeScript  \n")
        lines.append(f"**Generated:** {doc['generated_at']}  \n\n")
        lines.append("---\n\n")

        for section in doc["sections"]:
            if section["type"] == "class":
                lines.append(f"## Class {section['name']}\n\n")
                if section["description"]:
                    lines.append(f"{section['description']}\n\n")
            else:
                lines.append(f"## {section['type'].title()} {section['name']}\n\n")
                if section["description"]:
                    lines.append(f"{section['description']}\n\n")

                lines.append("```typescript\n")
                lines.append(f"{section['signature']}\n")
                lines.append("```\n\n")

                if section["parameters"]:
                    lines.append("### Parameters\n\n")
                    lines.append("| Name | Type | Default | Description |\n")
                    lines.append("|------|------|---------|-------------|\n")
                    for param in section["parameters"]:
                        default = param.get("default", "-")
                        lines.append(
                            f"| `{param['name']}` | `{param['type']}` | `{default}` | {param.get('description', '')} |\n"
                        )
                    lines.append("\n")

                if section.get("return_type"):
                    lines.append(f"**Returns:** `{section['return_type']}`\n\n")

            lines.append("---\n\n")

        return "".join(lines)

    def _format_plain_ts(self, doc: Dict[str, Any]) -> str:
        """Форматирование в plain text"""
        lines = [f"{doc['title']}\n"]
        lines.append("=" * 80 + "\n\n")

        for section in doc["sections"]:
            lines.append(f"{section['type'].title()}: {section['name']}\n")
            if section.get("description"):
                lines.append(f"{section['description']}\n\n")

        return "".join(lines)

    def _generate_python_documentation(
        self, code: str, function_name: Optional[str], format: str
    ) -> Dict[str, Any]:
        """
        Генерация документации для Python
        Использует AST для парсинга
        """
        import ast

        doc = {
            "title": f"Python Documentation - {function_name or 'Code'}",
            "language": "python",
            "generated_at": datetime.now().isoformat(),
            "sections": [],
        }

        try:
            # Парсинг AST
            tree = ast.parse(code)

            # Извлечение функций и классов
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(
                    node, ast.AsyncFunctionDef
                ):
                    func_info = self._extract_python_function(node, code)
                    doc["sections"].append(func_info)

                elif isinstance(node, ast.ClassDef):
                    class_info = self._extract_python_class(node, code)
                    doc["sections"].append(class_info)

            # Генерация текста
            if format == "markdown":
                doc["content"] = self._format_markdown_python(doc)
            else:
                doc["content"] = self._format_plain_python(doc)

        except SyntaxError as e:
            logger.error("Failed to parse Python code: %s", e)
            doc["content"] = f"Error parsing Python code: {e}"

        return doc

    def _extract_python_function(self, node: Any, code: str) -> Dict[str, Any]:
        """Извлечение информации о функции из AST"""
        import ast

        func_name = node.name
        is_async = isinstance(node, ast.AsyncFunctionDef)

        # Docstring
        docstring = ast.get_docstring(node) or f"Function {func_name}"

        # Параметры
        params = []
        for arg in node.args.args:
            param_name = arg.arg
            param_type = "Any"

            # Тип аннотация
            if arg.annotation:
                param_type = (
                    ast.unparse(arg.annotation) if hasattr(ast, "unparse") else "Any"
                )

            params.append(
                {
                    "name": param_name,
                    "type": param_type,
                    "description": "",
                }
            )

        # Return type
        return_type = "Any"
        if node.returns:
            return_type = (
                ast.unparse(node.returns) if hasattr(ast, "unparse") else "Any"
            )

        # Сигнатура
        args_str = ", ".join([f"{p['name']}: {p['type']}" for p in params])
        signature = f"{'async ' if is_async else ''}def {func_name}({args_str}) -> {return_type}"

        return {
            "name": func_name,
            "type": "async function" if is_async else "function",
            "signature": signature,
            "parameters": params,
            "return_type": return_type,
            "description": docstring,
            "examples": [],
        }

    def _extract_python_class(self, node: Any, code: str) -> Dict[str, Any]:
        """Извлечение информации о классе из AST"""
        import ast

        class_name = node.name
        docstring = ast.get_docstring(node) or f"Class {class_name}"

        # Методы
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        return {
            "name": class_name,
            "type": "class",
            "description": docstring,
            "methods": methods,
            "properties": [],
        }

    def _format_markdown_python(self, doc: Dict[str, Any]) -> str:
        """Форматирование Python документации в Markdown"""
        lines = [f"# {doc['title']}\n\n"]
        lines.append(f"**Language:** Python  \n")
        lines.append(f"**Generated:** {doc['generated_at']}  \n\n")
        lines.append("---\n\n")

        for section in doc["sections"]:
            if section["type"] == "class":
                lines.append(f"## Class {section['name']}\n\n")
                if section["description"]:
                    lines.append(f"{section['description']}\n\n")
                if section.get("methods"):
                    lines.append("**Methods:**\n")
                    for method in section["methods"]:
                        lines.append(f"- `{method}()`\n")
                    lines.append("\n")
            else:
                lines.append(f"## {section['type'].title()} {section['name']}\n\n")
                if section["description"]:
                    lines.append(f"{section['description']}\n\n")

                lines.append("```python\n")
                lines.append(f"{section['signature']}\n")
                lines.append("```\n\n")

                if section["parameters"]:
                    lines.append("### Parameters\n\n")
                    lines.append("| Name | Type | Description |\n")
                    lines.append("|------|------|-------------|\n")
                    for param in section["parameters"]:
                        lines.append(
                            f"| `{param['name']}` | `{param['type']}` | {param.get('description', '')} |\n"
                        )
                    lines.append("\n")

                if section.get("return_type"):
                    lines.append(f"**Returns:** `{section['return_type']}`\n\n")

            lines.append("---\n\n")

        return "".join(lines)

    def _format_plain_python(self, doc: Dict[str, Any]) -> str:
        """Форматирование в plain text"""
        lines = [f"{doc['title']}\n"]
        lines.append("=" * 80 + "\n\n")

        for section in doc["sections"]:
            lines.append(f"{section['type'].title()}: {section['name']}\n")
            if section.get("description"):
                lines.append(f"{section['description']}\n\n")

        return "".join(lines)


# Глобальный экземпляр
_doc_generator: Optional[DocumentationGenerator] = None


def get_documentation_generator() -> DocumentationGenerator:
    """Получение экземпляра генератора документации"""
    global _doc_generator
    if _doc_generator is None:
        _doc_generator = DocumentationGenerator()
    return _doc_generator
