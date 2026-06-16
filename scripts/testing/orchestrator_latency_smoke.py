
#!/usr/bin/env python3
"""
orchestrator_latency_smoke.py - лёгкий латентностный smoke-тест для AI Orchestrator.

Цель:
- Прогнать несколько запросов через Orchestrator.process_query в offline-режиме
  (без Kimi/Qwen) и вывести время обработки.

Использование:
    python scripts/testing/orchestrator_latency_smoke.py --requests 10
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.ai.orchestrator import AIOrchestrator  # type: ignore[attr-defined]


async def run_smoke(requests: int) -> List[float]:
    orchestrator = AIOrchestrator()
    # Отключаем внешних клиентов, чтобы не дергать LLM/HTTP
    orchestrator.kimi_client = None
    orchestrator.qwen_client = None

    durations: List[float] = []
    query = "Просто поговорим о best practices"

    for _ in range(requests):
        start = time.perf_counter()
        _ = await orchestrator.process_query(query, {})
        durations.append(time.perf_counter() - start)

    return durations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrator latency smoke-test (offline mode)."
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=5,
        help="Количество запросов (по умолчанию 5).",
    )
    args = parser.parse_args()

    durations = asyncio.run(run_smoke(max(1, args.requests)))
    if not durations:
        print("No requests executed.")
        return 0

    print("=== Orchestrator Latency Smoke Test ===")
    for i, d in enumerate(durations, start=1):
        print(f"Request {i}: {d:.3f}s")

    avg = sum(durations) / len(durations)
    print(f"Avg latency: {avg:.3f}s over {len(durations)} requests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


