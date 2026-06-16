
#!/usr/bin/env python3
"""
Псевдо-ETL для моделирования генерации векторной базы.

Берёт чанки из `output/vector_store_raw.json`, создаёт стабильные псевдослучайные
векторы и сохраняет их в `output/vector_store_mock.json`. Векторная длина по
умолчанию — 8 (для демонстрации).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сбор псевдо-векторного хранилища")
    parser.add_argument("--input", type=Path, default=Path("output/vector_store_raw.json"), help="Источник чанков")
    parser.add_argument("--output", type=Path, default=Path("output/vector_store_mock.json"), help="Целевой JSON")
    parser.add_argument("--vector-size", type=int, default=8, help="Размер псевдовектора")
    return parser.parse_args()


def build_vector(seed_text: str, size: int) -> List[float]:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    return [round(b / 255.0, 4) for b in digest[:size]]


def main() -> None:
    args = parse_args()
    if not args.input.exists():
        raise SystemExit(f"Не найден источник чанков: {args.input}")

    raw_chunks: List[Dict[str, Any]] = json.loads(args.input.read_text(encoding="utf-8"))
    mock_vectors = []

    for chunk in raw_chunks:
        vector = build_vector(chunk["text"], args.vector_size)
        mock_vectors.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source": chunk["source"],
                "vector": vector,
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(mock_vectors, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Сохранено {len(mock_vectors)} псевдовекторов в {args.output}")


if __name__ == "__main__":
    main()



