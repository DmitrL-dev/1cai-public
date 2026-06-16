"""
Проверка broken links в markdown файлах.

Сканирует все markdown файлы в проекте и проверяет:
- Внутренние ссылки (относительные пути)
- Внешние ссылки (HTTP/HTTPS)
- Якоря в документах
"""

import re
from pathlib import Path
from typing import List, Dict
import json
import argparse


class LinkChecker:
    """Проверка ссылок в markdown файлах."""
    
    def __init__(self, base_dir: Path):
        """Инициализация проверки.
        
        Args:
            base_dir: Базовая директория проекта.
        """
        self.base_dir = base_dir
        self.broken_links: List[Dict] = []
        self.total_links = 0
        self.internal_links = 0
        self.external_links = 0
        self.anchor_links = 0
    
    def check_directory(self, pattern: str = "**/*.md") -> Dict:
        """Проверяет все markdown файлы в директории.
        
        Args:
            pattern: Glob паттерн для поиска файлов.
            
        Returns:
            Словарь с результатами проверки.
        """
        print(f"Сканирование markdown файлов в {self.base_dir}...")
        print()
        
        markdown_files = list(self.base_dir.rglob(pattern))
        print(f"Найдено {len(markdown_files)} markdown файлов")
        print()
        
        for md_file in markdown_files:
            self._check_file(md_file)
        
        return self._generate_report()
    
    def _check_file(self, filepath: Path):
        """Проверяет один markdown файл.
        
        Args:
            filepath: Путь к файлу.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Поиск всех ссылок в markdown
            # Формат: [text](url) или [text](url "title")
            link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
            
            for match in re.finditer(link_pattern, content):
                link_text = match.group(1)
                link_url = match.group(2).split()[0]  # Убираем title если есть
                
                self.total_links += 1
                
                # Определение типа ссылки
                if link_url.startswith(('http://', 'https://')):
                    self.external_links += 1
                    # Внешние ссылки не проверяем (требует HTTP запросов)
                    continue
                
                elif link_url.startswith('#'):
                    self.anchor_links += 1
                    # Проверка якоря в текущем файле
                    if not self._check_anchor(filepath, link_url[1:]):
                        self._add_broken_link(
                            filepath,
                            link_text,
                            link_url,
                            "Якорь не найден в документе"
                        )
                
                else:
                    self.internal_links += 1
                    # Проверка внутренней ссылки
                    if not self._check_internal_link(filepath, link_url):
                        self._add_broken_link(
                            filepath,
                            link_text,
                            link_url,
                            "Файл не найден"
                        )
        
        except Exception as e:
            print(f"Ошибка при проверке {filepath}: {e}")
    
    def _check_internal_link(self, source_file: Path, link: str) -> bool:
        """Проверяет внутреннюю ссылку.
        
        Args:
            source_file: Файл-источник ссылки.
            link: URL ссылки.
            
        Returns:
            True если файл существует, False иначе.
        """
        # Убираем якорь если есть
        link_path = link.split('#')[0]
        
        if not link_path:
            return True  # Только якорь, уже проверен
        
        # Разрешение относительного пути
        target = (source_file.parent / link_path).resolve()
        
        return target.exists()
    
    def _check_anchor(self, filepath: Path, anchor: str) -> bool:
        """Проверяет наличие якоря в документе.
        
        Args:
            filepath: Путь к файлу.
            anchor: Имя якоря.
            
        Returns:
            True если якорь найден, False иначе.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Поиск заголовков которые могут быть якорями
            # GitHub автоматически создаёт якоря из заголовков
            header_pattern = r'^#+\s+(.+)$'
            
            for match in re.finditer(header_pattern, content, re.MULTILINE):
                header_text = match.group(1)
                # Преобразование заголовка в якорь (GitHub style)
                header_anchor = self._text_to_anchor(header_text)
                
                if header_anchor == anchor.lower():
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _text_to_anchor(self, text: str) -> str:
        """Преобразует текст в якорь (GitHub style).
        
        Args:
            text: Текст заголовка.
            
        Returns:
            Якорь в формате GitHub.
        """
        # Удаление специальных символов, замена пробелов на дефисы
        anchor = text.lower()
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        anchor = re.sub(r'\s+', '-', anchor)
        return anchor
    
    def _add_broken_link(
        self,
        filepath: Path,
        link_text: str,
        link_url: str,
        reason: str
    ):
        """Добавляет broken link в список.
        
        Args:
            filepath: Файл с broken link.
            link_text: Текст ссылки.
            link_url: URL ссылки.
            reason: Причина ошибки.
        """
        self.broken_links.append({
            "file": str(filepath.relative_to(self.base_dir)),
            "link_text": link_text,
            "link_url": link_url,
            "reason": reason
        })
    
    def _generate_report(self) -> Dict:
        """Генерирует отчёт о проверке.
        
        Returns:
            Словарь с результатами.
        """
        report = {
            "summary": {
                "total_links": self.total_links,
                "internal_links": self.internal_links,
                "external_links": self.external_links,
                "anchor_links": self.anchor_links,
                "broken_links": len(self.broken_links)
            },
            "broken_links": self.broken_links
        }
        
        return report
    
    def print_report(self, report: Dict):
        """Выводит отчёт в консоль.
        
        Args:
            report: Словарь с результатами.
        """
        print()
        print("=" * 80)
        print("ОТЧЁТ О ПРОВЕРКЕ ССЫЛОК")
        print("=" * 80)
        print()
        
        summary = report["summary"]
        print(f"Всего ссылок: {summary['total_links']}")
        print(f"  - Внутренние: {summary['internal_links']}")
        print(f"  - Внешние: {summary['external_links']} (не проверялись)")
        print(f"  - Якоря: {summary['anchor_links']}")
        print()
        print(f"Broken links: {summary['broken_links']}")
        print()
        
        if report["broken_links"]:
            print("Список broken links:")
            print()
            
            for link in report["broken_links"][:20]:  # Показываем первые 20
                print(f"📄 {link['file']}")
                print(f"   Текст: {link['link_text']}")
                print(f"   URL: {link['link_url']}")
                print(f"   Причина: {link['reason']}")
                print()
            
            if len(report["broken_links"]) > 20:
                print(f"... и ещё {len(report['broken_links']) - 20} broken links")
                print()
        
        print("=" * 80)
        
        # Сохранение детального отчёта
        with open("broken_links_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print()
        print("✅ Детальный отчёт сохранён: broken_links_report.json")
        print("=" * 80)


def main():
    """Главная функция."""
    parser = argparse.ArgumentParser(
        description="Проверка broken links в markdown файлах"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("."),
        help="Директория для проверки (по умолчанию: текущая)"
    )
    parser.add_argument(
        "--pattern",
        default="**/*.md",
        help="Glob паттерн для поиска файлов (по умолчанию: **/*.md)"
    )
    
    args = parser.parse_args()
    
    if not args.dir.exists():
        print(f"Ошибка: Директория {args.dir} не существует")
        return 1
    
    checker = LinkChecker(args.dir)
    report = checker.check_directory(args.pattern)
    checker.print_report(report)
    
    # Возвращаем код ошибки если есть broken links
    return 1 if report["summary"]["broken_links"] > 0 else 0


if __name__ == "__main__":
    exit(main())
