"""
Lifespan Management for 1C AI Stack

Управление жизненным циклом приложения: startup/shutdown.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.config import settings
from src.infrastructure.db.connection import close_pool, create_pool
from src.infrastructure.repositories.marketplace import MarketplaceRepository

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle management with best practices.
    
    Features:
    - OpenTelemetry setup
    - Database pool initialization
    - Redis connection
    - Graceful shutdown
    """
    pool = None
    redis_client = None
    marketplace_repo = None
    scheduler = None

    try:
        logger.info("Starting 1C AI Stack...")
        
        # Setup OpenTelemetry
        await _setup_opentelemetry(app)
        
        # Database pool
        pool = await _create_database_pool()
        
        # Redis
        redis_client = await _create_redis_client(app)
        
        # Marketplace repository
        if pool:
            marketplace_repo = await _create_marketplace_repo(app, pool, redis_client)
        
        # Scheduler
        if marketplace_repo:
            scheduler = _start_scheduler(app, marketplace_repo)
        
        # User rate limit middleware
        if redis_client:
            _add_rate_limit_middleware(app, redis_client)
        
        logger.info("Security layer initialized (Agents Rule of Two)")
        logger.info("Application startup completed successfully")

    except Exception as e:
        logger.error(f"Critical error during startup: {e}", exc_info=True)
        logger.warning("Continuing startup in degraded mode...")

    try:
        yield
    finally:
        logger.info("Shutting down...")
        
        if scheduler:
            try:
                scheduler.shutdown(wait=False)
            except Exception as e:
                logger.warning(f"Error shutting down scheduler: {e}")
        
        if marketplace_repo:
            try:
                await marketplace_repo.refresh_cached_views()
            except Exception as e:
                logger.warning(f"Error refreshing marketplace cache: {e}")
        
        if redis_client:
            try:
                await redis_client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis: {e}")
        
        if pool:
            try:
                await close_pool()
            except Exception as e:
                logger.warning(f"Error closing database pool: {e}")
        
        logger.info("Resources released")


async def _setup_opentelemetry(app: FastAPI):
    """Setup OpenTelemetry instrumentation."""
    otlp_endpoint = os.getenv("OTLP_ENDPOINT")
    if not otlp_endpoint:
        return
    
    try:
        from src.infrastructure.monitoring.opentelemetry_setup import (
            instrument_asyncpg,
            instrument_fastapi_app,
            instrument_httpx,
            instrument_redis,
            setup_opentelemetry,
        )
        
        setup_opentelemetry(
            service_name="1c-ai-stack",
            service_version="2.2.0",
            otlp_endpoint=otlp_endpoint,
            enable_console_exporter=os.getenv("OTEL_CONSOLE_EXPORTER", "false").lower() == "true",
        )
        instrument_fastapi_app(app)
        instrument_asyncpg()
        instrument_httpx()
        instrument_redis()
        logger.info("OpenTelemetry instrumentation enabled")
    except Exception as e:
        logger.warning(f"OpenTelemetry setup failed: {e}")


async def _create_database_pool():
    """Create database connection pool."""
    try:
        logger.info("Attempting to create database pool (timeout: 5s)...")
        pool = await asyncio.wait_for(create_pool(), timeout=5.0)
        if pool:
            logger.info("Database pool created successfully")
        return pool
    except asyncio.TimeoutError:
        logger.warning("Database connection timeout after 5s, continuing without DB")
        return None
    except Exception as e:
        logger.warning(f"Database not available: {e}")
        return None


async def _create_redis_client(app: FastAPI):
    """Create Redis client."""
    try:
        redis_client = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        app.state.redis = redis_client
        logger.info("Redis client connected")
        return redis_client
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        app.state.redis = None
        return None


async def _create_marketplace_repo(app: FastAPI, pool, redis_client):
    """Create marketplace repository."""
    try:
        bucket = settings.aws_s3_bucket or settings.minio_default_bucket or ""
        storage_config = {
            "bucket": bucket,
            "region": settings.aws_s3_region or "",
            "endpoint": settings.aws_s3_endpoint or settings.minio_endpoint,
            "access_key": settings.aws_access_key_id or settings.minio_root_user,
            "secret_key": settings.aws_secret_access_key or settings.minio_root_password,
            "create_bucket": settings.aws_s3_create_bucket,
        }
        
        marketplace_repo = MarketplaceRepository(
            pool, cache=redis_client, storage_config=storage_config
        )
        await marketplace_repo.init()
        app.state.marketplace_repo = marketplace_repo
        logger.info("Marketplace repository ready")
        return marketplace_repo
    except Exception as e:
        logger.error(f"Failed to initialize marketplace repository: {e}")
        app.state.marketplace_repo = None
        return None


def _start_scheduler(app: FastAPI, marketplace_repo):
    """Start background scheduler."""
    try:
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            marketplace_repo.refresh_cached_views,
            "interval",
            minutes=settings.marketplace_cache_refresh_minutes,
        )
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("Marketplace cache refresh scheduler started")
        return scheduler
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        return None


def _add_rate_limit_middleware(app: FastAPI, redis_client):
    """Add user rate limit middleware."""
    try:
        from src.middleware.user_rate_limit import UserRateLimitMiddleware
        from src.modules.auth.api.dependencies import get_auth_service
        
        auth_service = get_auth_service()
        if auth_service:
            app.add_middleware(
                UserRateLimitMiddleware,
                redis_client=redis_client,
                max_requests=settings.user_rate_limit_per_minute,
                window_seconds=settings.user_rate_limit_window_seconds,
                auth_service=auth_service,
            )
            logger.info("User rate limit middleware added")
    except Exception as e:
        logger.warning(f"Failed to add rate limit middleware: {e}")
