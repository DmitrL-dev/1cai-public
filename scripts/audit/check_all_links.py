
#!/usr/bin/env python3
"""Проверка всех ссылок во всех Markdown-файлах проекта.

Скрипт ищет относительные ссылки и проверяет, что целевые файлы
существуют. Результаты записываются в BROKEN_LINKS_REPORT.txt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent
EXCLUDE_DIRS = {"private", "edt-plugin"}
REPORT_PATH = ROOT / "BROKEN_LINKS_REPORT.txt"
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass
class LinkInfo:
    source_file: Path
    link_text: str
    target: str

    @property
    def display(self) -> str:
        rel_source = self.source_file.relative_to(ROOT)
        return f"{rel_source}: [{self.link_text}]({self.target})"


def iter_markdown_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.md"):
        if ".git" in path.parts:
            continue
        if any(part in EXCLUDE_DIRS for part in path.parts):
            continue
        yield path


def extract_links(markdown: str) -> List[tuple[str, str]]:
    links: List[tuple[str, str]] = []
    for match in LINK_PATTERN.finditer(markdown):
        raw_target = match.group(1).strip()
        text_start = markdown.rfind("[", 0, match.start())
        text_end = markdown.rfind("]", 0, match.start())
        link_text = markdown[text_start + 1 : text_end] if text_start != -1 else raw_target
        links.append((link_text, raw_target))
    return links


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
    )


def is_anchor(target: str) -> bool:
    return target.startswith("#")


def check_link(source: Path, target: str) -> bool:
    # Отбрасываем query и fragment
    target_path, _, fragment = target.partition("#")

    if is_external_link(target):
        return True
    if is_anchor(target) or (not target_path and fragment):
        return True

    # относительные пути
    resolved = (source.parent / target_path).resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        # ссылка выходит за пределы проекта
        return False

    return resolved.exists()


def main() -> None:
    markdown_files = list(iter_markdown_files(ROOT))
    broken: List[LinkInfo] = []
    total_links = 0

    for md_file in markdown_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            broken.append(LinkInfo(md_file, "<read-error>", f"{exc}"))
            continue

        for text, target in extract_links(content):
            total_links += 1
            if check_link(md_file, target):
                continue
            broken.append(LinkInfo(md_file, text, target))

    with REPORT_PATH.open("w", encoding="utf-8") as report:
        report.write("РЕЗУЛЬТАТЫ ПРОВЕРКИ ССЫЛОК\n")
        report.write("=" * 70 + "\n\n")
        report.write(f"Всего markdown-файлов: {len(markdown_files)}\n")
        report.write(f"Всего ссылок: {total_links}\n")
        report.write(f"Битых ссылок: {len(broken)}\n\n")

        if broken:
            report.write("БИТЫЕ ССЫЛКИ:\n")
            report.write("-" * 70 + "\n")
            for link in broken:
                report.write(f"- {link.display}\n")
        else:
            report.write("Битых ссылок не найдено.\n")

    print(f"Проверено файлов: {len(markdown_files)}")
    print(f"Всего ссылок: {total_links}")
    print(f"Битых ссылок: {len(broken)}")
    print(f"Отчёт: {REPORT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
