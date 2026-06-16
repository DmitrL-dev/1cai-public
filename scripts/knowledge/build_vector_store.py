
#!/usr/bin/env python3
"""
Сбор локальной базы знаний для офлайн-режима.

Шаги:
1. Собирает Markdown/текстовые файлы из заданных директорий.
2. Делит текст на чанки.
3. Сохраняет результат в JSON (для дальнейшего обогащения embedding-ами).

На этом этапе скрипт не строит embeddings, чтобы не требовать дополнительных библиотек.
Поддержана интеграция с будущими пайплайнами (например, sentence-transformers).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List

DEFAULT_INPUT_DIRS = [
    Path("docs"),
    Path("analysis"),
    Path("the-book-of-secret-knowledge/README.md"),
]
DEFAULT_OUTPUT = Path("output/vector_store_raw.json")
DEFAULT_MAX_CHARS = 1200


@dataclass
class DocumentChunk:
    source: str
    chunk_id: str
    text: str


def iter_source_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if not path.exists():
            logging.warning("Пропускаю отсутствующий путь: %s", path)
            continue
        if path.is_file():
            yield path
        else:
            for file in path.rglob("*"):
                if file.suffix.lower() in {".md", ".txt"} and file.is_file():
                    yield file


def normalize_text(text: str) -> str:
    return (
        text.replace("\r\n", "\n")
        .replace("\r", "\n")
        .strip()
    )


def split_into_chunks(text: str, max_chars: int) -> List[str]:
    lines = text.split("\n")
    chunks: List[str] = []
    buffer: List[str] = []
    buffer_len = 0

    for line in lines:
        line = line.strip()
        if not line:
            line = ""

        line_len = len(line) + 1  # + newline
        if buffer_len + line_len > max_chars and buffer:
            chunks.append("\n".join(buffer).strip())
            buffer = []
            buffer_len = 0

        buffer.append(line)
        buffer_len += line_len

    if buffer:
        chunks.append("\n".join(buffer).strip())

    return [chunk for chunk in chunks if chunk]


def build_chunks(input_paths: Iterable[Path], max_chars: int) -> List[DocumentChunk]:
    chunks: List[DocumentChunk] = []
    for src in iter_source_files(input_paths):
        text = normalize_text(src.read_text(encoding="utf-8", errors="ignore"))
        for index, chunk_text in enumerate(split_into_chunks(text, max_chars), start=1):
            chunk_id = f"{src.as_posix()}#{index}"
            chunks.append(DocumentChunk(source=src.as_posix(), chunk_id=chunk_id, text=chunk_text))
    return chunks


def save_chunks(chunks: List[DocumentChunk], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump([asdict(chunk) for chunk in chunks], f, ensure_ascii=False, indent=2)
    logging.info("Сохранено %s чанков в %s", len(chunks), output_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сбор локальной базы знаний")
    parser.add_argument(
        "--input",
        nargs="+",
        type=Path,
        default=DEFAULT_INPUT_DIRS,
        help="Файлы и директории для парсинга (формат: Markdown, TXT)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Путь к JSON с сырыми чанками",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=DEFAULT_MAX_CHARS,
        help="Максимальный размер чанка в символах",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Включить детализированный лог",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")

    logging.info("Старт сбора базы знаний")
    logging.info("Источники: %s", ", ".join(path.as_posix() for path in args.input))
    chunks = build_chunks(args.input, args.max_chars)
    if not chunks:
        logging.warning("Не найдено контента. Проверьте настройки input.")
    save_chunks(chunks, args.output)


if __name__ == "__main__":
    # Для совместимости с Windows окружением проводим проверку кодировки stdout
    if os.name == "nt":
        import sys

        if sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")
    main()

