
"""
kimi_benchmark.py - Простые performance-бенчмарки для Kimi-K2-Thinking.

Цели:
- Дать reproducible-скрипт для замера латентности Kimi (API/local).
- Использовать те же KimiClient/KimiConfig, что и оркестратор.

Пример:
    python scripts/testing/kimi_benchmark.py --requests 10 --concurrency 2
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.ai.clients.kimi_client import (  # type: ignore[attr-defined]
    KimiClient, KimiConfig, LLMNotConfiguredError)
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


@dataclass
class Sample:
    duration: float
    success: bool
    error_type: str | None = None


async def _run_single_request(client: KimiClient, prompt: str, max_tokens: int) -> Sample:
    start = time.perf_counter()
    try:
        await client.generate(
            prompt=prompt,
            system_prompt="You are an expert 1C:Enterprise developer. Answer briefly.",
            temperature=1.0,
            max_tokens=max_tokens,
        )
        duration = time.perf_counter() - start
        return Sample(duration=duration, success=True)
    except Exception as e:  # noqa: BLE001
        duration = time.perf_counter() - start
        logger.warning(
            "Kimi benchmark request failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return Sample(duration=duration, success=False, error_type=type(e).__name__)


async def run_benchmark(
    total_requests: int,
    concurrency: int,
    prompt: str,
    max_tokens: int,
) -> List[Sample]:
    config = KimiConfig()
    client = KimiClient(config=config)

    if not client.is_configured:
        raise LLMNotConfiguredError("Kimi client is not configured (check KIMI_API_KEY or KIMI_OLLAMA_URL).")

    logger.info(
        "Starting Kimi benchmark",
        extra={
            "mode": "local" if client.is_local else "api",
            "total_requests": total_requests,
            "concurrency": concurrency,
            "max_tokens": max_tokens,
        },
    )

    semaphore = asyncio.Semaphore(concurrency)
    samples: List[Sample] = []

    async def worker() -> None:
        while True:
            async with semaphore:
                if len(samples) >= total_requests:
                    return
                idx = len(samples) + 1
                logger.debug("Running benchmark request", extra={"index": idx})
                sample = await _run_single_request(client, prompt, max_tokens)
                samples.append(sample)

    workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.gather(*workers)
    return samples


def print_report(samples: List[Sample]) -> None:
    if not samples:
        print("No samples collected.")
        return

    durations = [s.duration for s in samples]
    successes = [s for s in samples if s.success]
    failures = [s for s in samples if not s.success]

    def pct(p: float) -> float:
        if not durations:
            return 0.0
        sorted_d = sorted(durations)
        k = int(len(sorted_d) * p)
        k = min(max(k, 0), len(sorted_d) - 1)
        return sorted_d[k]

    print("=== Kimi Benchmark Report ===")
    print(f"Total requests:     {len(samples)}")
    print(f"Success:            {len(successes)}")
    print(f"Failures:           {len(failures)}")
    if failures:
        by_type: dict[str, int] = {}
        for s in failures:
            if s.error_type:
                by_type[s.error_type] = by_type.get(s.error_type, 0) + 1
        print(f"Failure types:      {by_type}")

    print(f"Min latency:        {min(durations):.3f}s")
    print(f"Avg latency:        {statistics.mean(durations):.3f}s")
    if len(durations) > 1:
        print(f"p50 latency:        {pct(0.5):.3f}s")
        print(f"p95 latency:        {pct(0.95):.3f}s")
    print(f"Max latency:        {max(durations):.3f}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Kimi-K2-Thinking performance benchmark.")
    parser.add_argument("--requests", type=int, default=5, help="Количество запросов (по умолчанию 5).")
    parser.add_argument("--concurrency", type=int, default=1, help="Максимальная конкуррентность (по умолчанию 1).")
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Ограничение по токенам для ответа (по умолчанию 512).",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default="Сгенерируй простую функцию BSL для расчёта НДС по ставке 20%.",
        help="Промпт для бенчмарка.",
    )
    args = parser.parse_args()

    try:
        samples = asyncio.run(
            run_benchmark(
                total_requests=max(1, args.requests),
                concurrency=max(1, args.concurrency),
                prompt=args.prompt,
                max_tokens=args.max_tokens,
            )
        )
        print_report(samples)
        return 0
    except LLMNotConfiguredError as e:
        logger.warning(
            "Kimi benchmark skipped: not configured",
            extra={"error": str(e)},
        )
        print("Kimi benchmark skipped: client is not configured (KIMI_API_KEY / KIMI_OLLAMA_URL).")
        return 0
    except Exception as e:  # noqa: BLE001
        logger.error(
            "Kimi benchmark failed",
            extra={"error": str(e), "error_type": type(e).__name__},
            exc_info=True,
        )
        print(f"Kimi benchmark failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


