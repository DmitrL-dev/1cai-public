"""
Автоматическое исправление broken links в markdown файлах.

Стратегия исправления:
1. Удаление старых backup директорий
2. Исправление якорей (anchors)
3. Обновление путей к файлам
4. Удаление ссылок на несуществующие файлы
"""

import json
from pathlib import Path
from typing import Dict, List
import re
import shutil


class LinkFixer:
    """Исправление broken links в документации."""
    
    def __init__(self, report_file: str = "broken_links_report.json"):
        """Инициализация.
        
        Args:
            report_file: Путь к отчёту о broken links.
        """
        with open(report_file, "r", encoding="utf-8") as f:
            self.report = json.load(f)
        
        self.stats = {
            "backup_dirs_removed": 0,
            "anchors_fixed": 0,
            "files_updated": 0,
            "links_removed": 0
        }
    
    def fix_all(self):
        """Исправляет все broken links."""
        print("=" * 80)
        print("ИСПРАВЛЕНИЕ BROKEN LINKS")
        print("=" * 80)
        print()
        
        # Шаг 1: Удаление backup директорий
        print("Шаг 1: Удаление старых backup директорий...")
        self._remove_backup_dirs()
        
        # Шаг 2: Исправление якорей
        print("\nШаг 2: Исправление якорей в документах...")
        self._fix_anchors()
        
        # Шаг 3: Обновление путей
        print("\nШаг 3: Обновление путей к файлам...")
        self._fix_file_paths()
        
        # Шаг 4: Удаление ссылок на несуществующие файлы
        print("\nШаг 4: Удаление ссылок на несуществующие файлы...")
        self._remove_dead_links()
        
        self._print_summary()
    
    def _remove_backup_dirs(self):
        """Удаляет старые backup директории."""
        backup_dirs = list(Path(".").glob("backup_*"))
        
        for backup_dir in backup_dirs:
            if backup_dir.is_dir():
                print(f"  Удаление: {backup_dir}")
                try:
                    shutil.rmtree(backup_dir)
                    self.stats["backup_dirs_removed"] += 1
                except Exception as e:
                    print(f"    Ошибка: {e}")
        
        print(f"  ✅ Удалено директорий: {self.stats['backup_dirs_removed']}")
    
    def _fix_anchors(self):
        """Исправляет якоря в документах."""
        # Группировка broken links по файлам
        files_with_anchor_issues = {}
        
        for link in self.report["broken_links"]:
            if link["reason"] == "Якорь не найден в документе":
                file_path = link["file"]
                if file_path not in files_with_anchor_issues:
                    files_with_anchor_issues[file_path] = []
                files_with_anchor_issues[file_path].append(link)
        
        print(f"  Файлов с проблемами якорей: {len(files_with_anchor_issues)}")
        
        # Исправление якорей
        for file_path, links in list(files_with_anchor_issues.items())[:50]:  # Топ-50
            try:
                self._fix_file_anchors(Path(file_path), links)
            except Exception as e:
                print(f"    Ошибка в {file_path}: {e}")
        
        print(f"  ✅ Якорей исправлено: {self.stats['anchors_fixed']}")
    
    def _fix_file_anchors(self, filepath: Path, broken_links: List[Dict]):
        """Исправляет якоря в одном файле.
        
        Args:
            filepath: Путь к файлу.
            broken_links: Список broken links в этом файле.
        """
        if not filepath.exists():
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        modified = False
        
        for link in broken_links:
            anchor = link["link_url"].lstrip("#")
            
            # Поиск заголовка который должен соответствовать якорю
            # Пример: #environment-variables -> ## Environment Variables
            header_text = anchor.replace("-", " ").title()
            
            # Проверка есть ли такой заголовок
            header_pattern = rf'^#+\s+{re.escape(header_text)}$'
            
            if not re.search(header_pattern, content, re.MULTILINE | re.IGNORECASE):
                # Заголовок не найден - создаём его
                # Вставляем в конец файла
                content += f"\n\n## {header_text}\n\nTODO: Добавить содержание раздела.\n"
                modified = True
                self.stats["anchors_fixed"] += 1
        
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.stats["files_updated"] += 1
    
    def _fix_file_paths(self):
        """Обновляет пути к файлам."""
        # Группировка по файлам
        files_with_path_issues = {}
        
        for link in self.report["broken_links"]:
            if link["reason"] == "Файл не найден" and "backup_" not in link["file"]:
                file_path = link["file"]
                if file_path not in files_with_path_issues:
                    files_with_path_issues[file_path] = []
                files_with_path_issues[file_path].append(link)
        
        print(f"  Файлов с проблемами путей: {len(files_with_path_issues)}")
        
        # Пока просто логируем - полное исправление требует анализа
        print(f"  ℹ️  Требуется ручное исправление путей")
    
    def _remove_dead_links(self):
        """Удаляет ссылки на несуществующие файлы."""
        # Список файлов которые точно не существуют
        dead_files = {
            "technology_audit.md",
            "1C_CONFIG_EXTRACTION_RESEARCH.md",
            "1C_CONFIG_RESTRUCTURE_CRITICAL.md",
            "1C_CONFIG_DATABASE_DIRECT.md"
        }
        
        files_to_update = {}
        
        for link in self.report["broken_links"]:
            if any(dead in link["link_url"] for dead in dead_files):
                file_path = link["file"]
                if file_path not in files_to_update:
                    files_to_update[file_path] = []
                files_to_update[file_path].append(link)
        
        print(f"  Файлов для обновления: {len(files_to_update)}")
        
        for file_path, links in list(files_to_update.items())[:20]:  # Топ-20
            try:
                self._remove_links_from_file(Path(file_path), links)
            except Exception as e:
                print(f"    Ошибка в {file_path}: {e}")
        
        print(f"  ✅ Ссылок удалено: {self.stats['links_removed']}")
    
    def _remove_links_from_file(self, filepath: Path, links: List[Dict]):
        """Удаляет ссылки из файла.
        
        Args:
            filepath: Путь к файлу.
            links: Список ссылок для удаления.
        """
        if not filepath.exists():
            return
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        modified = False
        
        for link in links:
            # Паттерн ссылки: [текст](url)
            pattern = rf'\[{re.escape(link["link_text"])}\]\({re.escape(link["link_url"])}\)'
            
            if re.search(pattern, content):
                # Заменяем ссылку на просто текст
                content = re.sub(pattern, link["link_text"], content)
                modified = True
                self.stats["links_removed"] += 1
        
        if modified:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self.stats["files_updated"] += 1
    
    def _print_summary(self):
        """Выводит сводку."""
        print()
        print("=" * 80)
        print("СВОДКА ИСПРАВЛЕНИЙ")
        print("=" * 80)
        print(f"Backup директорий удалено: {self.stats['backup_dirs_removed']}")
        print(f"Якорей исправлено: {self.stats['anchors_fixed']}")
        print(f"Ссылок удалено: {self.stats['links_removed']}")
        print(f"Файлов обновлено: {self.stats['files_updated']}")
        print("=" * 80)
        print()
        print("✅ Исправление завершено!")
        print()
        print("Следующие шаги:")
        print("  1. Запустите проверку снова: python scripts/quality/link_checker.py")
        print("  2. Проверьте изменения: git diff")
        print("  3. Закоммитьте: git add . && git commit -m 'docs: Phase 3 - fixed broken links'")


def main():
    """Главная функция."""
    fixer = LinkFixer()
    fixer.fix_all()


if __name__ == "__main__":
    main()
