"""
Автоматический генератор docstrings для Python файлов.

Этот скрипт анализирует Python файлы и добавляет базовые docstrings
в формате Google Style для модулей, классов и функций, которые их не имеют.
"""

import ast
from pathlib import Path
import argparse


class DocstringGenerator:
    """Генератор docstrings для Python кода."""
    
    def __init__(self, dry_run: bool = False):
        """Инициализация генератора.
        
        Args:
            dry_run: Если True, только показывает изменения без записи.
        """
        self.dry_run = dry_run
        self.stats = {
            "files_processed": 0,
            "docstrings_added": 0,
            "modules": 0,
            "classes": 0,
            "functions": 0
        }
    
    def generate_module_docstring(self, filepath: Path) -> str:
        """Генерирует docstring для модуля.
        
        Args:
            filepath: Путь к файлу модуля.
            
        Returns:
            Сгенерированный docstring.
        """
        module_name = filepath.stem
        return f'''"""Модуль {module_name}.

TODO: Добавить подробное описание модуля.

Этот docstring был автоматически сгенерирован.
Пожалуйста, обновите его с правильным описанием.
"""

'''
    
    def generate_class_docstring(self, node: ast.ClassDef) -> str:
        """Генерирует docstring для класса.
        
        Args:
            node: AST узел класса.
            
        Returns:
            Сгенерированный docstring.
        """
        return f'''"""Класс {node.name}.
        
        TODO: Добавить описание класса.
        
        Attributes:
            TODO: Описать атрибуты класса.
        """'''
    
    def generate_function_docstring(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        """Генерирует docstring для функции.
        
        Args:
            node: AST узел функции.
            
        Returns:
            Сгенерированный docstring.
        """
        # Анализ параметров
        args_section = ""
        if node.args.args:
            args_lines = []
            for arg in node.args.args:
                if arg.arg != "self" and arg.arg != "cls":
                    args_lines.append(f"            {arg.arg}: TODO: Описать параметр.")
            
            if args_lines:
                args_section = "\n        \n        Args:\n" + "\n".join(args_lines)
        
        # Анализ возвращаемого значения
        returns_section = ""
        if node.returns:
            returns_section = "\n        \n        Returns:\n            TODO: Описать возвращаемое значение."
        
        return f'''"""TODO: Описать функцию {node.name}.{args_section}{returns_section}
        """'''
    
    def add_docstrings_to_file(self, filepath: Path) -> bool:
        """Добавляет docstrings в файл.
        
        Args:
            filepath: Путь к Python файлу.
            
        Returns:
            True если файл был изменён, False иначе.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            tree = ast.parse(content)
            lines = content.splitlines(keepends=True)
            
            modifications = []
            
            # Проверка module docstring
            if not ast.get_docstring(tree):
                module_doc = self.generate_module_docstring(filepath)
                modifications.append((0, module_doc))
                self.stats["modules"] += 1
                self.stats["docstrings_added"] += 1
            
            # Проверка классов и функций
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    if not ast.get_docstring(node):
                        docstring = self.generate_class_docstring(node)
                        # Вставка после определения класса
                        insert_line = node.lineno
                        modifications.append((insert_line, docstring))
                        self.stats["classes"] += 1
                        self.stats["docstrings_added"] += 1
                
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Пропускаем приватные функции
                    if node.name.startswith("_") and node.name != "__init__":
                        continue
                    
                    if not ast.get_docstring(node):
                        docstring = self.generate_function_docstring(node)
                        insert_line = node.lineno
                        modifications.append((insert_line, docstring))
                        self.stats["functions"] += 1
                        self.stats["docstrings_added"] += 1
            
            if not modifications:
                return False
            
            # Применение изменений
            if not self.dry_run:
                # Сортировка по номеру строки в обратном порядке
                modifications.sort(reverse=True)
                
                for line_no, docstring in modifications:
                    # Вставка docstring после определения
                    if line_no < len(lines):
                        indent = self._get_indent(lines[line_no])
                        indented_doc = self._indent_docstring(docstring, indent + "    ")
                        lines.insert(line_no, indented_doc)
                
                with open(filepath, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            
            self.stats["files_processed"] += 1
            return True
            
        except Exception as e:
            print(f"Ошибка обработки {filepath}: {e}")
            return False
    
    def _get_indent(self, line: str) -> str:
        """Получает отступ строки.
        
        Args:
            line: Строка кода.
            
        Returns:
            Строка с пробелами отступа.
        """
        return line[:len(line) - len(line.lstrip())]
    
    def _indent_docstring(self, docstring: str, indent: str) -> str:
        """Добавляет отступ к docstring.
        
        Args:
            docstring: Текст docstring.
            indent: Строка отступа.
            
        Returns:
            Docstring с отступами.
        """
        lines = docstring.splitlines(keepends=True)
        return "".join(indent + line for line in lines)
    
    def process_directory(self, directory: Path, pattern: str = "**/*.py"):
        """Обрабатывает все Python файлы в директории.
        
        Args:
            directory: Путь к директории.
            pattern: Glob паттерн для поиска файлов.
        """
        print(f"Обработка директории: {directory}")
        print(f"Режим: {'DRY RUN (без изменений)' if self.dry_run else 'ЗАПИСЬ'}")
        print()
        
        for filepath in directory.rglob(pattern):
            if "__pycache__" in str(filepath):
                continue
            
            if self.add_docstrings_to_file(filepath):
                print(f"✅ {filepath}")
        
        self.print_summary()
    
    def print_summary(self):
        """Выводит сводку по обработке."""
        print()
        print("=" * 80)
        print("СВОДКА")
        print("=" * 80)
        print(f"Файлов обработано: {self.stats['files_processed']}")
        print(f"Docstrings добавлено: {self.stats['docstrings_added']}")
        print(f"  - Модули: {self.stats['modules']}")
        print(f"  - Классы: {self.stats['classes']}")
        print(f"  - Функции: {self.stats['functions']}")
        print("=" * 80)
        
        if self.dry_run:
            print("\n⚠️  Это был DRY RUN. Файлы не были изменены.")
            print("Запустите без --dry-run для применения изменений.")


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Автоматический генератор docstrings"
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Директория для обработки"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать изменения без записи"
    )
    parser.add_argument(
        "--pattern",
        default="**/*.py",
        help="Glob паттерн для поиска файлов (по умолчанию: **/*.py)"
    )
    
    args = parser.parse_args()
    
    if not args.directory.exists():
        print(f"Ошибка: Директория {args.directory} не существует")
        return 1
    
    generator = DocstringGenerator(dry_run=args.dry_run)
    generator.process_directory(args.directory, args.pattern)
    
    return 0


if __name__ == "__main__":
    exit(main())
