
"""
Prometheus Metrics Export
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок

TIER 1 Improvement: Comprehensive monitoring
"""

from typing import Optional

import psutil
from fastapi import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)

from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


# ==================== REQUEST METRICS ====================

# Total requests
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests", [
        "method", "endpoint", "status_code"]
)

# Request duration
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Request size
http_request_size_bytes = Histogram(
    "http_request_size_bytes", "HTTP request size in bytes", [
        "method", "endpoint"]
)

# Response size
http_response_size_bytes = Histogram(
    "http_response_size_bytes", "HTTP response size in bytes", [
        "method", "endpoint"]
)


# ==================== AI METRICS ====================

# AI queries
ai_queries_total = Counter(
    "ai_queries_total", "Total AI queries", ["agent_type", "status", "model"]
)

# AI response time
ai_response_duration_seconds = Histogram(
    "ai_response_duration_seconds",
    "AI response duration",
    ["agent_type", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

# AI tokens used
ai_tokens_used_total = Counter(
    "ai_tokens_used_total",
    "Total AI tokens consumed",
    # token_type: prompt, completion, total
    ["agent_type", "model", "token_type"],
)

# AI service availability
ai_service_available = Gauge(
    "ai_service_available",
    "AI service availability (1 = available, 0 = unavailable)",
    ["service", "model"],
)

# AI errors
ai_errors_total = Counter(
    "ai_errors_total", "Total AI errors", ["service", "model", "error_type"]
)

# Kimi-K2-Thinking specific metrics
kimi_queries_total = Counter(
    "kimi_queries_total",
    "Total Kimi-K2-Thinking queries",
    ["mode", "status"],  # mode: api, local
)

kimi_response_duration_seconds = Histogram(
    "kimi_response_duration_seconds",
    "Kimi-K2-Thinking response duration",
    ["mode"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

kimi_tokens_used_total = Counter(
    "kimi_tokens_used_total",
    "Total Kimi-K2-Thinking tokens consumed",
    ["mode", "token_type"],
)

kimi_reasoning_steps = Histogram(
    "kimi_reasoning_steps",
    "Number of reasoning steps in Kimi responses",
    ["mode"],
    buckets=[1, 2, 5, 10, 20, 50, 100],
)

kimi_tool_calls_total = Counter(
    "kimi_tool_calls_total", "Total tool calls made by Kimi", [
        "mode", "tool_name"]
)

# AI Orchestrator metrics
orchestrator_queries_total = Counter(
    "orchestrator_queries_total",
    "Total orchestrator queries",
    ["query_type", "selected_service"],
)

orchestrator_fallback_total = Counter(
    "orchestrator_fallback_total",
    "Total fallback operations",
    ["from_service", "to_service", "reason"],
)

orchestrator_cache_hits_total = Counter(
    "orchestrator_cache_hits_total", "Total cache hits in orchestrator"
)

orchestrator_cache_misses_total = Counter(
    "orchestrator_cache_misses_total", "Total cache misses in orchestrator"
)

# Scenario Hub / Scenario API metrics
scenario_requests_total = Counter(
    "scenario_requests_total",
    "Total Scenario Hub API requests",
    ["endpoint", "autonomy_provided"],
)

# Scenario Recommender metrics
scenario_recommender_requests_total = Counter(
    "scenario_recommender_requests_total",
    "Total scenario recommendation requests",
    ["status"],
)

scenario_recommender_duration_seconds = Histogram(
    "scenario_recommender_duration_seconds",
    "Scenario recommendation duration",
    ["graph_size_category"],  # small (<100), medium (100-1000), large (>1000)
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)

scenario_recommender_recommendations_count = Histogram(
    "scenario_recommender_recommendations_count",
    "Number of scenarios recommended",
    buckets=[1, 2, 3, 5, 10, 20],
)

# Impact Analyzer metrics
impact_analyzer_requests_total = Counter(
    "impact_analyzer_requests_total", "Total impact analysis requests", [
        "status"]
)

impact_analyzer_duration_seconds = Histogram(
    "impact_analyzer_duration_seconds",
    "Impact analysis duration",
    ["max_depth", "include_tests"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)

impact_analyzer_affected_nodes_count = Histogram(
    "impact_analyzer_affected_nodes_count",
    "Number of affected nodes found",
    buckets=[1, 5, 10, 50, 100, 500, 1000],
)

# LLM Gateway metrics
llm_gateway_requests_total = Counter(
    "llm_gateway_requests_total",
    "Total LLM Gateway requests",
    ["provider", "role", "status"],  # status: success, error, hit (cache)
)

llm_gateway_latency_seconds = Histogram(
    "llm_gateway_latency_seconds",
    "LLM Gateway request latency",
    ["provider", "role"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

llm_gateway_fallbacks_total = Counter(
    "llm_gateway_fallbacks_total",
    "Total fallback operations",
    ["from_provider", "to_provider", "reason"],
)

llm_provider_health = Gauge(
    "llm_provider_health",
    "LLM provider health status (1=healthy, 0.5=degraded, 0=unhealthy)",
    ["provider"],
)

llm_provider_latency_ms = Gauge(
    "llm_provider_latency_ms", "LLM provider latency in milliseconds", [
        "provider"]
)

# DNS Manager metrics
dns_resolution_total = Counter(
    "dns_resolution_total",
    "Total DNS resolution requests",
    ["resolver", "type", "status"],  # types: doh, dot, standard
)

dns_resolution_duration_seconds = Histogram(
    "dns_resolution_duration_seconds",
    "DNS resolution duration",
    ["resolver", "type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
)

dns_resolver_health = Gauge(
    "dns_resolver_health",
    "DNS resolver health status (1=healthy, 0=unhealthy)",
    ["resolver"],
)

# Network Resilience metrics
network_path_health = Gauge(
    "network_path_health",
    "Network path health status (1=healthy, 0=unhealthy)",
    ["path_id", "path_type"],
)

network_path_latency_ms = Gauge(
    "network_path_latency_ms",
    "Network path latency in milliseconds",
    ["path_id", "path_type"],
)

network_failover_total = Counter(
    "network_failover_total",
    "Total network failover operations",
    ["from_path", "to_path", "reason"],
)

# Traffic Shaping metrics
traffic_shaping_operations_total = Counter(
    "traffic_shaping_operations_total",
    "Total traffic shaping operations",
    ["operation_type", "status"],
)

traffic_shaping_delay_seconds = Histogram(
    "traffic_shaping_delay_seconds",
    "Traffic shaping delay",
    ["operation_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# VPN Manager metrics
vpn_tunnel_health = Gauge(
    "vpn_tunnel_health",
    "VPN tunnel health status (1=healthy, 0=unhealthy)",
    ["tunnel_name", "tunnel_type"],
)

vpn_tunnel_latency_ms = Gauge(
    "vpn_tunnel_latency_ms",
    "VPN tunnel latency in milliseconds",
    ["tunnel_name", "tunnel_type"],
)

vpn_tunnel_throughput_bytes = Gauge(
    "vpn_tunnel_throughput_bytes",
    "VPN tunnel throughput in bytes per second",
    ["tunnel_name", "tunnel_type"],
)

# Protocol Obfuscation metrics
protocol_obfuscation_operations_total = Counter(
    "protocol_obfuscation_operations_total",
    "Total protocol obfuscation operations",
    ["obfuscation_type", "status"],
)

protocol_obfuscation_overhead_bytes = Histogram(
    "protocol_obfuscation_overhead_bytes",
    "Protocol obfuscation overhead in bytes",
    ["obfuscation_type"],
    buckets=[0, 64, 128, 256, 512, 1024, 2048, 4096],
)

# LLM Provider Abstraction metrics
llm_provider_selections_total = Counter(
    "llm_provider_selections_total",
    "Total LLM provider selections",
    ["provider_id", "query_type", "reason"],
)

llm_provider_selection_duration_seconds = Histogram(
    "llm_provider_selection_duration_seconds",
    "LLM provider selection duration",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1],
)

llm_provider_cost_estimate = Histogram(
    "llm_provider_cost_estimate",
    "Estimated cost per 1k tokens for selected provider",
    ["provider_id"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# Intelligent Cache metrics
intelligent_cache_operations_total = Counter(
    "intelligent_cache_operations_total",
    "Intelligent Cache operations",
    [
        "operation",
        "status",
    ],  # operation: get, set, invalidate_by_tags, invalidate_by_query_type, clear
)

intelligent_cache_duration_seconds = Histogram(
    "intelligent_cache_duration_seconds",
    "Intelligent Cache operation duration",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

intelligent_cache_size = Gauge(
    "intelligent_cache_size",
    "Current size of Intelligent Cache",
    ["cache_type"],  # cache_type: orchestrator
)

intelligent_cache_max_size = Gauge(
    "intelligent_cache_max_size", "Maximum size of Intelligent Cache", [
        "cache_type"]
)

intelligent_cache_hits_total = Counter(
    "intelligent_cache_hits_total",
    "Total Intelligent Cache hits",
    ["cache_type", "query_type"],
)

intelligent_cache_misses_total = Counter(
    "intelligent_cache_misses_total",
    "Total Intelligent Cache misses",
    ["cache_type", "query_type"],
)

intelligent_cache_evictions_total = Counter(
    "intelligent_cache_evictions_total",
    "Total Intelligent Cache evictions",
    ["cache_type", "eviction_reason"],  # eviction_reason: lru, ttl_expired
)

intelligent_cache_invalidations_total = Counter(
    "intelligent_cache_invalidations_total",
    "Total Intelligent Cache invalidations",
    # invalidation_type: tags, query_type, manual
    ["cache_type", "invalidation_type"],
)

# ==================== EMBEDDING SERVICE METRICS ====================

# Embedding requests
embedding_requests_total = Counter(
    "embedding_requests_total",
    "Total embedding requests",
    ["device", "status"],  # device: cpu, gpu, hybrid, cache; status: success, error
)

# Embedding duration
embedding_duration_seconds = Histogram(
    "embedding_duration_seconds",
    "Embedding processing duration",
    ["device"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Items processed
embedding_items_processed_total = Counter(
    "embedding_items_processed_total",
    "Total items processed by embedding service",
    ["device"],
)

# Cache metrics
embedding_cache_hits_total = Counter(
    "embedding_cache_hits_total", "Total embedding cache hits"
)

embedding_cache_misses_total = Counter(
    "embedding_cache_misses_total", "Total embedding cache misses"
)

# Device usage percentage
embedding_device_usage_percent = Gauge(
    "embedding_device_usage_percent",
    "Device usage percentage for embeddings",
    ["device"],  # device: cpu, gpu
)

# Circuit breaker metrics
embedding_circuit_breaker_state = Gauge(
    "embedding_circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["device"],  # device: cpu, gpu
)

embedding_circuit_breaker_failures = Counter(
    "embedding_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["device"],
)

# Health check metrics
embedding_health_status = Gauge(
    "embedding_health_status",
    "Health status of embedding service components (1=healthy, 0=unhealthy)",
    ["component"],  # component: cpu, gpu, cache
)

embedding_health_check_duration_seconds = Histogram(
    "embedding_health_check_duration_seconds",
    "Duration of health checks",
    ["component"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# Semantic cache metrics
embedding_semantic_cache_hits_total = Counter(
    "embedding_semantic_cache_hits_total",
    "Total semantic cache hits (similarity-based)",
)

embedding_semantic_cache_similarity = Histogram(
    "embedding_semantic_cache_similarity",
    "Cosine similarity scores for semantic cache hits",
    buckets=[0.90, 0.92, 0.94, 0.95, 0.96, 0.98, 0.99, 1.0],
)

# Multi-layer cache metrics
embedding_cache_layer_hits_total = Counter(
    "embedding_cache_layer_hits_total",
    "Cache hits by layer",
    ["layer"],  # layer: l1, l2, l3
)

embedding_cache_layer_misses_total = Counter(
    "embedding_cache_layer_misses_total", "Cache misses by layer", ["layer"]
)

# Quantization metrics
embedding_quantization_enabled = Gauge(
    "embedding_quantization_enabled",
    "Whether quantization is enabled (1=enabled, 0=disabled)",
)

embedding_quantization_ratio = Gauge(
    "embedding_quantization_ratio",
    "Memory savings ratio from quantization",
    ["dtype"],  # dtype: int8, int16
)

# Multi-GPU metrics
embedding_gpu_count = Gauge("embedding_gpu_count",
                            "Number of available GPU devices")

embedding_gpu_requests_total = Counter(
    "embedding_gpu_requests_total", "Total requests per GPU device", ["gpu_id"]
)

embedding_gpu_memory_usage_gb = Gauge(
    "embedding_gpu_memory_usage_gb",
    "GPU memory usage in GB",
    ["gpu_id", "type"],  # types: total, allocated, free, reserved
)

# Adaptive batch size metrics
embedding_optimal_batch_size = Gauge(
    "embedding_optimal_batch_size",
    "Optimal batch size calculated based on GPU memory",
    ["gpu_id"],
)

embedding_batch_size_adjustments_total = Counter(
    "embedding_batch_size_adjustments_total",
    "Total batch size adjustments",
    ["adjustment_type"],  # adjustment_type: increased, decreased, unchanged
)

# SLO/SLI metrics
embedding_slo_latency_p95 = Gauge(
    "embedding_slo_latency_p95", "Current SLI for latency p95", ["slo_name"]
)

embedding_slo_error_budget = Gauge(
    "embedding_slo_error_budget", "Current error budget for SLO", ["slo_name"]
)

embedding_slo_violations_total = Counter(
    "embedding_slo_violations_total", "Total SLO violations", ["slo_name"]
)

# Adaptive Quantization metrics
embedding_adaptive_quantization_calibrated = Gauge(
    "embedding_adaptive_quantization_calibrated",
    "Whether adaptive quantization is calibrated (1=calibrated, 0=not calibrated)",
)

embedding_adaptive_quantization_scale = Gauge(
    "embedding_adaptive_quantization_scale",
    "Current quantization scale factor",
    ["dtype"],
)

# Semantic Cache ANN metrics
embedding_semantic_cache_ann_size = Gauge(
    "embedding_semantic_cache_ann_size",
    "Current size of semantic cache ANN index",
    ["index_type"],  # index_type: linear, faiss, hnswlib
)

embedding_semantic_cache_ann_search_duration_seconds = Histogram(
    "embedding_semantic_cache_ann_search_duration_seconds",
    "Duration of ANN search operations",
    ["index_type"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# Predictive Batch Optimizer metrics
embedding_predictive_batch_history_size = Gauge(
    "embedding_predictive_batch_history_size", "Current size of prediction history"
)

embedding_predictive_batch_model_trained = Gauge(
    "embedding_predictive_batch_model_trained",
    "Whether prediction model is trained (1=trained, 0=not trained)",
)

embedding_predictive_batch_prediction_accuracy = Gauge(
    "embedding_predictive_batch_prediction_accuracy",
    "Accuracy of batch size predictions (MAE)",
)

# Weighted GPU Scheduler metrics
embedding_weighted_gpu_weights = Gauge(
    "embedding_weighted_gpu_weights", "Current weights for GPU devices", [
        "gpu_id"]
)

embedding_weighted_gpu_load = Gauge(
    "embedding_weighted_gpu_load", "Current load for GPU devices", ["gpu_id"]
)

embedding_weighted_gpu_requests_total = Counter(
    "embedding_weighted_gpu_requests_total",
    "Total requests per GPU via weighted scheduler",
    ["gpu_id"],
)


# ==================== BUSINESS METRICS ====================

# Active users
active_users = Gauge("active_users", "Currently active users")

# Active tenants
active_tenants = Gauge("active_tenants", "Currently active tenants")

# Code reviews
code_reviews_total = Counter(
    "code_reviews_total", "Total code reviews", ["status", "language"]
)

# Tests generated
tests_generated_total = Counter(
    "tests_generated_total", "Total tests generated", ["language", "framework"]
)

# Projects
projects_total = Gauge("projects_total", "Total projects", ["status"])


# ==================== BA SESSION METRICS ====================

ba_ws_active_sessions = Gauge(
    "ba_ws_active_sessions", "Currently active BA websocket sessions"
)

ba_ws_active_participants = Gauge(
    "ba_ws_active_participants", "Currently active BA websocket participants"
)

ba_ws_events_total = Counter(
    "ba_ws_events_total", "Total BA websocket events", ["event_type"]
)

ba_ws_disconnects_total = Counter(
    "ba_ws_disconnects_total", "Total BA websocket disconnects", ["reason"]
)

ba_ws_audit_failures_total = Counter(
    "ba_ws_audit_failures_total", "Total BA session audit write failures"
)


# ==================== DATABASE METRICS ====================

# Database queries
db_queries_total = Counter(
    "db_queries_total", "Total database queries", ["database", "operation"]
)

# Database query duration
db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query duration",
    ["database", "operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# Connection pool
db_pool_size = Gauge(
    "db_pool_size", "Database connection pool size", ["database"])

db_pool_available = Gauge(
    "db_pool_available_connections", "Available database connections", [
        "database"]
)


# ==================== CACHE METRICS ====================

# Cache hits/misses
cache_operations_total = Counter(
    "cache_operations_total", "Cache operations", [
        "operation", "layer", "status"]
)

# Cache size
cache_size_bytes = Gauge("cache_size_bytes", "Cache size in bytes", ["layer"])


# ==================== SYSTEM METRICS ====================

# System info
system_info = Info("system", "System information")

# CPU usage
system_cpu_usage_percent = Gauge(
    "system_cpu_usage_percent", "CPU usage percentage")

# Memory usage
system_memory_usage_percent = Gauge(
    "system_memory_usage_percent", "Memory usage percentage"
)

system_memory_available_bytes = Gauge(
    "system_memory_available_bytes", "Available memory in bytes"
)

# Disk usage
system_disk_usage_percent = Gauge(
    "system_disk_usage_percent", "Disk usage percentage")


# ==================== ERROR METRICS ====================

# Errors by type
errors_total = Counter("errors_total", "Total errors",
                       ["error_type", "endpoint"])

# Circuit breaker state
circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=open, 2=half_open)",
    ["service"],
)


# ==================== HELPER FUNCTIONS ====================


def update_system_metrics():
    """
    Update system metrics (CPU, memory, disk)

    Best practices:
    - Graceful error handling (don't crash if psutil unavailable)
    - Safe disk path handling (works on Windows/Linux)
    - Structured logging
    """
    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        system_cpu_usage_percent.set(cpu_percent)

        # Memory
        memory = psutil.virtual_memory()
        system_memory_usage_percent.set(memory.percent)
        system_memory_available_bytes.set(memory.available)

        # Disk (best practice: handle different OS paths)
        try:
            # Try root path (Linux/Mac)
            disk = psutil.disk_usage("/")
        except (OSError, PermissionError):
            # Fallback to current directory (Windows)
            import os

            disk = psutil.disk_usage(os.getcwd())

        system_disk_usage_percent.set(disk.percent)

    except ImportError:
        logger.warning(
            "psutil not available, system metrics disabled",
            extra={"module": "prometheus_metrics"},
        )
    except Exception as e:
        logger.error(
            f"Failed to update system metrics: {e}",
            exc_info=True,
            extra={"error_type": type(e).__name__},
        )


def track_request(
    method: str, endpoint: str, status_code: int, duration: float, size: int = 0
):
    """Track HTTP request"""
    http_requests_total.labels(
        method=method, endpoint=endpoint, status_code=status_code
    ).inc()
    http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
        duration
    )

    if size > 0:
        http_response_size_bytes.labels(
            method=method, endpoint=endpoint).observe(size)


def track_ai_query(
    agent_type: str, duration: float, status: str = "success", tokens: int = 0
):
    """Track AI query"""
    ai_queries_total.labels(agent_type=agent_type, status=status).inc()
    ai_response_duration_seconds.labels(
        agent_type=agent_type).observe(duration)

    if tokens > 0:
        ai_tokens_used_total.labels(
            agent_type=agent_type, model="gpt-4").inc(tokens)


def track_db_query(database: str, operation: str, duration: float):
    """Track database query"""
    db_queries_total.labels(database=database, operation=operation).inc()
    db_query_duration_seconds.labels(database=database, operation=operation).observe(
        duration
    )


def track_cache_operation(layer: str, operation: str, status: str):
    """Track cache operation"""
    cache_operations_total.labels(
        operation=operation, layer=layer, status=status).inc()


def track_ba_session_event(event_type: str) -> None:
    """Track BA websocket events such as join/leave/chat."""
    ba_ws_events_total.labels(event_type=event_type).inc()


def track_ba_session_disconnect(reason: str) -> None:
    """Track BA websocket disconnects."""
    ba_ws_disconnects_total.labels(reason=reason).inc()


def track_ba_session_audit_failure() -> None:
    """Track audit log failures for BA sessions."""
    ba_ws_audit_failures_total.inc()


def set_ba_session_counts(active_sessions: int, active_participants: int):
    """
    Update BA websocket session gauges atomically.
    """
    ba_ws_active_sessions.set(max(0, active_sessions))
    ba_ws_active_participants.set(max(0, active_participants))


def track_scenario_recommendation(
    duration: float,
    graph_size_category: str,
    recommendations_count: int,
    status: str = "success",
):
    """Track scenario recommendation"""
    scenario_recommender_requests_total.labels(status=status).inc()
    scenario_recommender_duration_seconds.labels(
        graph_size_category=graph_size_category
    ).observe(duration)
    scenario_recommender_recommendations_count.observe(recommendations_count)


def track_impact_analysis(
    duration: float,
    max_depth: int,
    include_tests: bool,
    affected_nodes_count: int,
    status: str = "success",
):
    """Track impact analysis"""
    impact_analyzer_requests_total.labels(status=status).inc()
    impact_analyzer_duration_seconds.labels(
        max_depth=str(max_depth), include_tests=str(include_tests)
    ).observe(duration)
    impact_analyzer_affected_nodes_count.observe(affected_nodes_count)


def track_llm_provider_selection(
    duration: float,
    provider_id: str,
    query_type: str,
    reason: str = "default",
    cost_per_1k_tokens: Optional[float] = None,
):
    """Track LLM provider selection"""
    llm_provider_selections_total.labels(
        provider_id=provider_id, query_type=query_type, reason=reason
    ).inc()
    llm_provider_selection_duration_seconds.observe(duration)
    if cost_per_1k_tokens is not None:
        llm_provider_cost_estimate.labels(provider_id=provider_id).observe(
            cost_per_1k_tokens
        )


def track_intelligent_cache_operation(
    operation: str,
    duration: float,
    status: str = "success",
    cache_type: str = "orchestrator",
):
    """Track Intelligent Cache operation"""
    intelligent_cache_operations_total.labels(
        operation=operation, status=status).inc()
    intelligent_cache_duration_seconds.labels(
        operation=operation).observe(duration)


def track_intelligent_cache_hit(
    cache_type: str = "orchestrator", query_type: Optional[str] = None
):
    """Track Intelligent Cache hit"""
    intelligent_cache_hits_total.labels(
        cache_type=cache_type, query_type=query_type or "unknown"
    ).inc()


def track_intelligent_cache_miss(
    cache_type: str = "orchestrator", query_type: Optional[str] = None
):
    """Track Intelligent Cache miss"""
    intelligent_cache_misses_total.labels(
        cache_type=cache_type, query_type=query_type or "unknown"
    ).inc()


def track_intelligent_cache_eviction(
    cache_type: str = "orchestrator", eviction_reason: str = "lru"
):
    """Track Intelligent Cache eviction"""
    intelligent_cache_evictions_total.labels(
        cache_type=cache_type, eviction_reason=eviction_reason
    ).inc()


def track_intelligent_cache_invalidation(
    cache_type: str = "orchestrator", invalidation_type: str = "manual"
):
    """Track Intelligent Cache invalidation"""
    intelligent_cache_invalidations_total.labels(
        cache_type=cache_type, invalidation_type=invalidation_type
    ).inc()


def update_intelligent_cache_size(
    cache_type: str = "orchestrator", current_size: int = 0, max_size: int = 0
):
    """Update Intelligent Cache size metrics"""
    intelligent_cache_size.labels(cache_type=cache_type).set(current_size)
    intelligent_cache_max_size.labels(cache_type=cache_type).set(max_size)


# ==================== METRICS ENDPOINT ====================


async def metrics_endpoint() -> Response:
    """
    Prometheus metrics endpoint

    Usage in FastAPI:
        from src.monitoring.prometheus_metrics import metrics_endpoint

        @app.get("/metrics")
        async def metrics():
            return await metrics_endpoint()
    """

    # Update system metrics before export
    update_system_metrics()

    # Generate metrics in Prometheus format
    metrics_output = generate_latest()

    return Response(content=metrics_output, media_type=CONTENT_TYPE_LATEST)
