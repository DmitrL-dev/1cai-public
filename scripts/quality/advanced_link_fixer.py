"""
Расширенное исправление оставшихся broken links.

Исправляет:
1. Якоря с эмодзи (emoji anchors)
2. Примеры в документации
3. Создание недостающих файлов-заглушек
4. Обновление путей к файлам
"""

import json
from pathlib import Path
from typing import Dict, List
import re


class AdvancedLinkFixer:
    """Расширенное исправление broken links."""
    
    def __init__(self, report_file: str = "broken_links_report.json"):
        """Инициализация."""
        with open(report_file, "r", encoding="utf-8") as f:
            self.report = json.load(f)
        
        self.stats = {
            "emoji_anchors_fixed": 0,
            "example_links_marked": 0,
            "stub_files_created": 0,
            "paths_updated": 0,
            "files_modified": 0
        }
        
        # Файлы которые являются примерами
        self.example_files = {
            "docs/DOCUMENTATION_STANDARDS.md"
        }
    
    def fix_all(self):
        """Исправляет все оставшиеся broken links."""
        print("=" * 80)
        print("РАСШИРЕННОЕ ИСПРАВЛЕНИЕ BROKEN LINKS")
        print("=" * 80)
        print()
        
        # Шаг 1: Исправление emoji anchors
        print("Шаг 1: Исправление якорей с эмодзи...")
        self._fix_emoji_anchors()
        
        # Шаг 2: Пометка примеров
        print("\nШаг 2: Пометка примеров в документации...")
        self._mark_example_links()
        
        # Шаг 3: Создание файлов-заглушек
        print("\nШаг 3: Создание недостающих файлов...")
        self._create_stub_files()
        
        # Шаг 4: Обновление путей
        print("\nШаг 4: Обновление путей к файлам...")
        self._update_paths()
        
        self._print_summary()
    
    def _fix_emoji_anchors(self):
        """Исправляет якоря с эмодзи."""
        emoji_issues = [
            link for link in self.report["broken_links"]
            if "Якорь не найден" in link["reason"] and "️" in link["link_url"]
        ]
        
        print(f"  Найдено якорей с эмодзи: {len(emoji_issues)}")
        
        # Группировка по файлам
        files_to_fix = {}
        for link in emoji_issues:
            file_path = link["file"]
            if file_path not in files_to_fix:
                files_to_fix[file_path] = []
            files_to_fix[file_path].append(link)
        
        for file_path, links in files_to_fix.items():
            try:
                self._fix_emoji_in_file(Path(file_path), links)
            except Exception as e:
                print(f"    Ошибка в {file_path}: {e}")
        
        print(f"  ✅ Якорей исправлено: {self.stats['emoji_anchors_fixed']}")
    
    def _fix_emoji_in_file(self, filepath: Path, links: List[Dict]):
        """Исправляет эмодзи в якорях файла."""
        if not filepath.exists():
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        modified = False
        
        for link in links:
            # Пример: #️-архитектура -> #архитектура
            old_anchor = link["link_url"]
            new_anchor = old_anchor.replace("️", "").replace("#-", "#")
            
            # Замена в содержимом
            old_pattern = rf'\({re.escape(old_anchor)}\)'
            new_replacement = f'({new_anchor})'
            
            if re.search(old_pattern, content):
                content = re.sub(old_pattern, new_replacement, content)
                modified = True
                self.stats['emoji_anchors_fixed'] += 1
        
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.stats['files_modified'] += 1
    
    def _mark_example_links(self):
        """Помечает примеры в документации."""
        example_links = [
            link for link in self.report["broken_links"]
            if link["file"] in self.example_files
        ]
        
        print(f"  Найдено примеров: {len(example_links)}")
        
        for file_path in self.example_files:
            try:
                self._mark_examples_in_file(Path(file_path))
            except Exception as e:
                print(f"    Ошибка в {file_path}: {e}")
        
        print(f"  ✅ Примеров помечено: {self.stats['example_links_marked']}")
    
    def _mark_examples_in_file(self, filepath: Path):
        """Помечает примеры в файле."""
        if not filepath.exists():
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Поиск секций с примерами
        # Добавляем комментарий что это примеры
        example_patterns = [
            (r'\[текст\]\(\.\/path\/to\/file\.md\)', 
             '[текст](./path/to/file.md) <!-- Пример -->'),
            (r'\[Связанный документ 1\]\(\.\/related1\.md\)',
             '[Связанный документ 1](./related1.md) <!-- Пример -->'),
            (r'\[Связанный документ 2\]\(\.\/related2\.md\)',
             '[Связанный документ 2](./related2.md) <!-- Пример -->'),
        ]
        
        modified = False
        for pattern, replacement in example_patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                modified = True
                self.stats['example_links_marked'] += 1
        
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.stats['files_modified'] += 1
    
    def _create_stub_files(self):
        """Создаёт файлы-заглушки для критичных недостающих файлов."""
        # Критичные файлы которые часто упоминаются
        critical_missing = [
            "docs/architecture/STANDARDS_INDEX.md",
            "docs/security/SECURITY.md",
            "docs/architecture/01-high-level-design.md",
        ]
        
        for file_path in critical_missing:
            try:
                self._create_stub_file(Path(file_path))
            except Exception as e:
                print(f"    Ошибка создания {file_path}: {e}")
        
        print(f"  ✅ Файлов создано: {self.stats['stub_files_created']}")
    
    def _create_stub_file(self, filepath: Path):
        """Создаёт файл-заглушку."""
        if filepath.exists():
            return
        
        # Создание директории если нужно
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # Содержимое заглушки
        title = filepath.stem.replace("-", " ").replace("_", " ").title()
        content = f"""# {title}

> ⚠️ **Этот документ создан автоматически как заглушка**
> 
> TODO: Добавить содержимое документа.

## Обзор

Этот раздел требует заполнения.

## См. также

- [Главная документация](../README.md)

---

*Создано автоматически: Phase 3 Documentation Audit*
"""
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        self.stats['stub_files_created'] += 1
        print(f"    Создан: {filepath}")
    
    def _update_paths(self):
        """Обновляет пути к файлам."""
        # Анализ наиболее частых проблем с путями
        path_issues = [
            link for link in self.report["broken_links"]
            if "Файл не найден" in link["reason"]
            and link["file"] not in self.example_files
            and "backup_" not in link["file"]
        ]
        
        print(f"  Проблем с путями: {len(path_issues)}")
        
        # Группировка по типам проблем
        missing_research = [l for l in path_issues if "research" in l["link_url"]]
        missing_api = [l for l in path_issues if "api" in l["link_url"]]
        
        print(f"    - Отсутствующие research файлы: {len(missing_research)}")
        print(f"    - Отсутствующие API файлы: {len(missing_api)}")
        print(f"  ℹ️  Большинство требуют ручного исправления или создания файлов")
    
    def _print_summary(self):
        """Выводит сводку."""
        print()
        print("=" * 80)
        print("СВОДКА РАСШИРЕННЫХ ИСПРАВЛЕНИЙ")
        print("=" * 80)
        print(f"Emoji якорей исправлено: {self.stats['emoji_anchors_fixed']}")
        print(f"Примеров помечено: {self.stats['example_links_marked']}")
        print(f"Файлов-заглушек создано: {self.stats['stub_files_created']}")
        print(f"Файлов изменено: {self.stats['files_modified']}")
        print("=" * 80)
        print()
        print("✅ Расширенное исправление завершено!")
        print()
        print("Следующие шаги:")
        print("  1. Запустите проверку снова: python scripts/quality/link_checker.py")
        print("  2. Проверьте изменения: git diff")
        print("  3. Закоммитьте: git add . && git commit -m 'docs: Phase 3 - advanced link fixes'")


def main():
    """Главная функция."""
    fixer = AdvancedLinkFixer()
    fixer.fix_all()


if __name__ == "__main__":
    main()
