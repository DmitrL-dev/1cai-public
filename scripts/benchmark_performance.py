
#!/usr/bin/env python3
"""
Performance Benchmark Script
Measures actual performance against targets

Target for 10/10:
- p50 latency: < 50ms
- p95 latency: < 200ms
- p99 latency: < 500ms
- Throughput: > 1000 req/s
- Error rate: < 0.1%
"""

import asyncio
import statistics
import time

import httpx

API_URL = "http://localhost:8000"


async def measure_endpoint_performance(endpoint: str, num_requests: int = 1000) -> dict:
    """Measure endpoint performance"""
    
    latencies = []
    errors = 0
    
    async with httpx.AsyncClient(base_url=API_URL, timeout=30.0) as client:
        tasks = []
        
        start_time = time.time()
        
        # Send requests
        for _ in range(num_requests):
            tasks.append(make_request(client, endpoint))
        
        # Wait for all
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = time.time() - start_time
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                errors += 1
            elif isinstance(result, dict):
                latencies.append(result['latency'])
        
        # Calculate percentiles
        if latencies:
            p50 = statistics.median(latencies)
            p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
            p99 = statistics.quantiles(latencies, n=100)[98]  # 99th percentile
        else:
            p50 = p95 = p99 = 0
        
        throughput = num_requests / total_time
        error_rate = (errors / num_requests) * 100
        
        return {
            'endpoint': endpoint,
            'total_requests': num_requests,
            'successful': num_requests - errors,
            'errors': errors,
            'error_rate': round(error_rate, 2),
            'total_time': round(total_time, 2),
            'throughput': round(throughput, 2),
            'latency': {
                'p50': round(p50 * 1000, 2),  # Convert to ms
                'p95': round(p95 * 1000, 2),
                'p99': round(p99 * 1000, 2),
                'min': round(min(latencies) * 1000, 2) if latencies else 0,
                'max': round(max(latencies) * 1000, 2) if latencies else 0,
                'avg': round(statistics.mean(latencies) * 1000, 2) if latencies else 0
            }
        }


async def make_request(client: httpx.AsyncClient, endpoint: str) -> dict:
    """Make single request and measure latency"""
    start = time.time()
    
    try:
        response = await client.get(endpoint)
        latency = time.time() - start
        
        return {
            'latency': latency,
            'status': response.status_code
        }
    except Exception as e:
        return {
            'latency': time.time() - start,
            'error': str(e)
        }


async def run_benchmark():
    """Run complete performance benchmark"""
    
    print("🚀 Starting Performance Benchmark...\n")
    
    endpoints = [
        '/health',
        '/api/dashboard/owner',
        '/api/dashboard/executive',
        '/api/dashboard/pm'
    ]
    
    results = []
    
    for endpoint in endpoints:
        print(f"📊 Benchmarking {endpoint}...")
        result = await measure_endpoint_performance(endpoint, 1000)
        results.append(result)
        
        # Print results
        print(f"  Throughput: {result['throughput']} req/s")
        print(f"  Latency p50: {result['latency']['p50']}ms")
        print(f"  Latency p95: {result['latency']['p95']}ms")
        print(f"  Latency p99: {result['latency']['p99']}ms")
        print(f"  Error rate: {result['error_rate']}%")
        print()
    
    # Overall assessment
    print("\n" + "="*50)
    print("OVERALL PERFORMANCE ASSESSMENT")
    print("="*50)
    
    avg_p95 = statistics.mean([r['latency']['p95'] for r in results])
    avg_throughput = statistics.mean([r['throughput'] for r in results])
    max_error_rate = max([r['error_rate'] for r in results])
    
    print(f"\nAverage p95 latency: {avg_p95:.2f}ms")
    print(f"Average throughput: {avg_throughput:.2f} req/s")
    print(f"Max error rate: {max_error_rate:.2f}%")
    
    # Grading
    grade = "F"
    if avg_p95 < 50 and avg_throughput > 1000:
        grade = "A+"
    elif avg_p95 < 100 and avg_throughput > 500:
        grade = "A"
    elif avg_p95 < 200 and avg_throughput > 200:
        grade = "B"
    elif avg_p95 < 500:
        grade = "C"
    
    print(f"\n🎯 PERFORMANCE GRADE: {grade}")
    
    # Targets for 10/10
    print("\n📊 TARGETS FOR 10/10:")
    print(f"  p95 latency: {avg_p95:.1f}ms / 50ms target {'✅' if avg_p95 < 50 else '⏳'}")
    print(f"  Throughput: {avg_throughput:.0f}/s / 1000/s target {'✅' if avg_throughput > 1000 else '⏳'}")
    print(f"  Error rate: {max_error_rate:.2f}% / 0.1% target {'✅' if max_error_rate < 0.1 else '⏳'}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())


