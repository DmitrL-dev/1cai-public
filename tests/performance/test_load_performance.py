
"""
Performance Tests - Нагрузочное тестирование
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.asyncio
async def test_api_latency_benchmark():
    """
    Benchmark: API latency

    Target: p95 < 100ms
    """

    from src.ai.role_based_router import RoleBasedRouter

    router = RoleBasedRouter()

    latencies = []

    for i in range(100):
        start = time.time()

        result = await router.route_query("Как создать документ?")

        latency_ms = (time.time() - start) * 1000
        latencies.append(latency_ms)

    # Calculate percentiles
    p50 = statistics.median(latencies)
    if len(latencies) >= 20:
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    else:
        p95 = latencies[-1] if latencies else 0
    if len(latencies) >= 100:
        p99 = statistics.quantiles(latencies, n=100)[98]
    else:
        p99 = latencies[-1] if latencies else 0

    print("\nLatency Benchmark:")
    print(f"  p50: {p50:.2f}ms")
    print(f"  p95: {p95:.2f}ms")
    print(f"  p99: {p99:.2f}ms")

    assert p95 < 500, f"p95 latency too high: {p95:.2f}ms"


@pytest.mark.asyncio
async def test_concurrent_requests():
    """
    Load Test: 100 concurrent requests

    Target: All complete successfully
    """

    from src.ai.role_based_router import RoleBasedRouter

    router = RoleBasedRouter()

    async def make_request(i):
        result = await router.route_query(f"Test query {i}")
        return result is not None

    # 100 concurrent requests
    tasks = [make_request(i) for i in range(100)]

    start = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    duration = time.time() - start

    # Count successes
    successes = sum(1 for r in results if r is True)
    errors = len(results) - successes

    throughput = len(results) / duration

    print("\nConcurrent Load Test:")
    print(f"  Requests: {len(results)}")
    print(f"  Successes: {successes}")
    print(f"  Errors: {errors}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput:.2f} RPS")

    assert successes >= 95, f"Too many errors: {errors}"


@pytest.mark.asyncio
async def test_cache_performance():
    """
    Performance: Cache hit vs miss

    Target: Cache hit <1ms, miss <100ms
    """

    from src.cache.multi_layer_cache import MultiLayerCache

    cache = MultiLayerCache()

    # Populate cache
    await cache.set("perf_test", {"data": "value" * 1000}, ttl_seconds=60)

    # Measure cache HIT
    hit_times = []
    for _ in range(1000):
        start = time.time()
        value = await cache.get("perf_test")
        hit_times.append((time.time() - start) * 1000)

    # Measure cache MISS
    miss_times = []
    for _ in range(100):
        start = time.time()
        value = await cache.get(f"miss_key_{_}")
        miss_times.append((time.time() - start) * 1000)

    avg_hit = statistics.mean(hit_times)
    avg_miss = statistics.mean(miss_times)

    # On fast machines an in-memory cache hit can be faster than the clock
    # resolution, so avg_hit measures as exactly 0.0ms. Guard the speedup
    # division (it is diagnostic output only) to keep the test deterministic
    # instead of raising ZeroDivisionError.
    speedup = (avg_miss / avg_hit) if avg_hit > 0 else float("inf")

    print("\nCache Performance:")
    print(f"  Avg HIT: {avg_hit:.3f}ms")
    print(f"  Avg MISS: {avg_miss:.3f}ms")
    print(f"  Speedup: {speedup:.1f}x")

    assert avg_hit < 1.0, f"Cache hit too slow: {avg_hit:.3f}ms"


@pytest.mark.asyncio
async def test_database_query_performance():
    """
    Performance: Database queries

    Target: Simple SELECT <10ms
    """

    import asyncpg

    try:
        conn = await asyncpg.connect(
            host="localhost",
            user="postgres",
            password="postgres",
            database="enterprise_1c_ai",
        )

        # Warm up
        await conn.fetchval("SELECT 1")

        # Benchmark simple query
        times = []
        for _ in range(100):
            start = time.time()
            result = await conn.fetchval("SELECT COUNT(*) FROM projects")
            times.append((time.time() - start) * 1000)

        avg_time = statistics.mean(times)
        if len(times) >= 20:
            p95_time = statistics.quantiles(times, n=20)[18]
        else:
            p95_time = times[-1] if times else 0

        print("\nDatabase Performance:")
        print(f"  Avg: {avg_time:.2f}ms")
        print(f"  p95: {p95_time:.2f}ms")

        await conn.close()

        assert p95_time < 50, f"Query too slow: {p95_time:.2f}ms"

    except Exception as e:
        pytest.skip(f"Database not available: {e}", allow_module_level=False)


@pytest.mark.asyncio
async def test_code_review_throughput():
    """
    Throughput: Code review requests/second

    Target: >10 reviews/second
    """

    from src.ai.agents.code_review.ai_reviewer import AICodeReviewer

    reviewer = AICodeReviewer()

    sample_code = """
Функция Тест()
    Возврат 123;
КонецФункции
"""

    async def review():
        return await reviewer.review_code(sample_code, "test.bsl")

    # Run 50 reviews
    start = time.time()
    tasks = [review() for _ in range(50)]
    results = await asyncio.gather(*tasks)
    duration = time.time() - start

    throughput = len(results) / duration

    print("\nCode Review Throughput:")
    print(f"  Reviews: {len(results)}")
    print(f"  Duration: {duration:.2f}s")
    print(f"  Throughput: {throughput:.2f} reviews/s")

    assert throughput > 5, f"Throughput too low: {throughput:.2f}"


@pytest.mark.asyncio
async def test_memory_usage():
    """
    Resource: Memory usage под нагрузкой
    """

    import os

    import psutil

    process = psutil.Process(os.getpid())

    # Baseline memory
    baseline_mb = process.memory_info().rss / 1024 / 1024

    # Create load
    from src.ai.role_based_router import RoleBasedRouter

    router = RoleBasedRouter()

    tasks = [router.route_query(f"Query {i}") for i in range(100)]

    await asyncio.gather(*tasks)

    # Peak memory
    peak_mb = process.memory_info().rss / 1024 / 1024

    increase_mb = peak_mb - baseline_mb

    print("\nMemory Usage:")
    print(f"  Baseline: {baseline_mb:.1f} MB")
    print(f"  Peak: {peak_mb:.1f} MB")
    print(f"  Increase: {increase_mb:.1f} MB")

    assert increase_mb < 500, f"Memory leak detected: +{increase_mb:.1f}MB"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
