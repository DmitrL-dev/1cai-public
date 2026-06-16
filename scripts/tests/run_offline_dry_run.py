
#!/usr/bin/env python3
"""
Автоматизированный dry-run офлайн-сценария.

Выполняет последовательность шагов:
1. Симулирует health-check провайдеров.
2. Получает ответы от LLM Gateway (в режиме моделирования).
3. Формирует псевдо-векторную базу.
4. Собирает сводный отчёт.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from scripts.diagnostics.mock_healthcheck import \
    build_report as build_health_report
from scripts.knowledge.mock_embedding_builder import build_vector
from src.services.llm_gateway import load_llm_gateway

RAW_VECTOR_PATH = Path("output/vector_store_raw.json")
MOCK_VECTOR_PATH = Path("output/vector_store_mock.json")
REPORT_PATH = Path("output/offline_dry_run_report.json")


def simulate_vectors(vector_size: int = 8) -> int:
    if not RAW_VECTOR_PATH.exists():
        return 0

    raw_chunks = json.loads(RAW_VECTOR_PATH.read_text(encoding="utf-8"))
    mock_vectors = []
    for chunk in raw_chunks:
        vector = build_vector(chunk["text"], vector_size)
        mock_vectors.append(
            {"chunk_id": chunk["chunk_id"], "source": chunk["source"], "vector": vector}
        )

    MOCK_VECTOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    MOCK_VECTOR_PATH.write_text(json.dumps(mock_vectors, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(mock_vectors)


def main() -> None:
    gateway = load_llm_gateway()
    gateway_samples = {
        "architect": gateway.generate("Построй диаграмму mermaid для сервиса", role="architect").response,
        "devops": gateway.generate("latency ошибка", role="devops").response,
    }

    health_report = build_health_report(down=["openai"])
    vectors_generated = simulate_vectors()

    report: Dict[str, Any] = {
        "health_check": health_report,
        "gateway_samples": gateway_samples,
        "vectors_generated": vectors_generated,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Off-line dry run report stored at {REPORT_PATH}")


if __name__ == "__main__":
    main()



