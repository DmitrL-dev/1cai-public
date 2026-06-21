
"""
Enhanced Health Checker Service
Версия: 2.0.0

Улучшения:
- Добавлен timeout для health checks
- Улучшена обработка ошибок
- Structured logging
"""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict

from src.utils.structured_logging import StructuredLogger
from src.config import settings

logger = StructuredLogger(__name__).logger


class HealthChecker:
    """
    Comprehensive health checker for all system dependencies

    Checks:
    - PostgreSQL
    - Redis
    - Neo4j
    - Qdrant
    - Elasticsearch
    - External APIs (OpenAI, Supabase)
    """

    def __init__(self):
        self.checks = []

    async def check_all(self, timeout: float = 10.0, pg_saver=None) -> Dict:
        """
        Run all health checks in parallel with timeout

        Args:
            timeout: Maximum time to wait for all checks (seconds)
            pg_saver: Optional PostgreSQLSaver instance for check
        """
        # Input validation
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            logger.warning(
                "Invalid timeout in check_all",
                extra={"timeout": timeout, "timeout_type": type(timeout).__name__},
            )
            timeout = 10.0  # Default timeout

        checks = [
            self.check_postgresql(pg_saver),
            self.check_redis(),
            self.check_neo4j(),
            self.check_qdrant(),
            self.check_elasticsearch(),
            self.check_openai(),
        ]

        try:
            # Execute all checks with timeout (best practice)
            results = await asyncio.wait_for(
                asyncio.gather(*checks, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(
                "Health checks timeout",
                extra={"timeout": timeout, "checks_count": len(checks)},
            )
            # Return timeout status for all services
            results = [TimeoutError()] * len(checks)

        services = {}
        unhealthy = []

        service_names = [
            "postgresql",
            "redis",
            "neo4j",
            "qdrant",
            "elasticsearch",
            "openai",
        ]

        for name, result in zip(service_names, results):
            if isinstance(result, Exception):
                services[name] = "unhealthy"
                unhealthy.append(name)
                error_type = type(result).__name__
                logger.error(
                    "Health check failed",
                    extra={
                        "service": name,
                        "error_type": error_type,
                        "error_message": str(result),
                    },
                )
            else:
                services[name] = result.get("status", "unknown")
                if result.get("status") != "healthy":
                    unhealthy.append(name)

        overall = (
            "healthy"
            if not unhealthy
            else "degraded" if len(unhealthy) < 3 else "unhealthy"
        )

        return {
            "status": overall,
            "timestamp": datetime.now().isoformat(),
            "services": services,
            "unhealthy_services": unhealthy,
            "healthy_count": len(service_names) - len(unhealthy),
            "total_count": len(service_names),
        }

    async def check_postgresql(self, pg_saver=None) -> Dict:
        """Check PostgreSQL connection"""
        try:
            from urllib.parse import urlparse

            import asyncpg

            # Try to use provided PostgreSQLSaver first
            if pg_saver:
                try:
                    if pg_saver.is_connected():
                        return {
                            "status": "healthy",
                            "message": "Connected via provided PostgreSQLSaver",
                        }
                    else:
                        logger.debug(
                            "Provided PostgreSQLSaver exists but not connected, trying to connect...")
                        if pg_saver.connect() and pg_saver.is_connected():
                            return {
                                "status": "healthy",
                                "message": "Connected via provided PostgreSQLSaver (reconnected)",
                            }
                except Exception as e:
                    logger.debug("Provided PostgreSQLSaver check failed: %s", e)

            # Try to create and connect new PostgreSQLSaver
            try:
                from src.db.postgres_saver import PostgreSQLSaver
                pg_saver = PostgreSQLSaver()
                if pg_saver.connect():
                    if pg_saver.is_connected():
                        return {
                            "status": "healthy",
                            "message": "Connected via new PostgreSQLSaver",
                        }
                    else:
                        logger.debug(
                            "PostgreSQLSaver.connect() returned True but is_connected() returns False")
                else:
                    logger.debug("PostgreSQLSaver.connect() returned False")
            except ValueError as e:
                # Password not provided - this is expected, continue to direct connection
                logger.debug(
                    f"PostgreSQLSaver initialization failed (likely missing password): {e}")
            except Exception as e:
                logger.debug(
                    f"PostgreSQLSaver check failed, using direct connection: {e}")

            # Fallback to direct connection
            db_url = settings.database_url
            if not db_url:
                # Try individual env variables
                host = settings.postgres_host
                port = settings.postgres_port
                database = settings.postgres_db
                user = settings.postgres_user
                password = settings.postgres_password

                if not password:
                    logger.warning(
                        "PostgreSQL password not provided in environment variables")
                    return {
                        "status": "unhealthy",
                        "error": "PostgreSQL password not provided",
                    }
            else:
                parsed = urlparse(db_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 5432
                database = parsed.path.lstrip("/") or "knowledge_base"
                user = parsed.username or "admin"
                password = parsed.password or settings.postgres_password

                if not password:
                    logger.warning("PostgreSQL password not provided in DATABASE_URL")
                    return {
                        "status": "unhealthy",
                        "error": "PostgreSQL password not provided",
                    }

            started_at = time.perf_counter()

            # Use context manager for proper connection cleanup (best practice)
            async with asyncpg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                timeout=5.0,
            ) as conn:
                # Test query
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    raise ValueError("Test query returned unexpected result")

                # Check table count
                table_count = await conn.fetchval(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
                )

            return {
                "status": "healthy",
                "response_time_ms": round((time.perf_counter() - started_at) * 1000, 2),
                "tables": table_count,
                "connection_method": "direct_asyncpg",
            }

        except asyncpg.exceptions.InvalidPasswordError as e:
            logger.error(
                "PostgreSQL authentication failed",
                extra={"error": str(e), "host": host,
                                    "database": database, "user": user},
            )
            return {"status": "unhealthy", "error": "Authentication failed - check password"}
        except asyncpg.exceptions.ConnectionDoesNotExistError as e:
            logger.error(
                "PostgreSQL connection error",
                extra={"error": str(e), "host": host, "port": port,
                                    "database": database},
            )
            return {"status": "unhealthy", "error": f"Connection failed: {str(e)}"}
        except Exception as e:
            logger.error(
                "PostgreSQL health check failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "host": host,
                    "port": port,
                    "database": database,
                    "user": user,
                },
                exc_info=True,
            )
            return {"status": "unhealthy", "error": str(e)}

    async def check_redis(self) -> Dict:
        """Check Redis connection"""
        try:
            import redis.asyncio as aioredis

            import redis.asyncio as aioredis

            redis_url = settings.redis_url
            client = aioredis.from_url(redis_url, socket_connect_timeout=5)

            # Ping
            await client.ping()

            # Get info
            info = await client.info()

            await client.close()

            return {
                "status": "healthy",
                "version": info.get("redis_version", "unknown"),
                "uptime_seconds": info.get("uptime_in_seconds", 0),
            }

        except Exception as e:
            logger.error(
                "Redis health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"status": "unhealthy", "error": str(e)}

    async def check_neo4j(self) -> Dict:
        """Check Neo4j connection"""
        try:
            from neo4j import AsyncGraphDatabase

            from neo4j import AsyncGraphDatabase

            neo4j_uri = settings.neo4j_uri
            neo4j_user = settings.neo4j_user
            neo4j_pass = settings.neo4j_password

            driver = AsyncGraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))

            async with driver.session() as session:
                result = await session.run("RETURN 1 as num")
                await result.single()

                # Get node count
                count_result = await session.run("MATCH (n) RETURN count(n) as count")
                count_record = await count_result.single()

            await driver.close()

            return {"status": "healthy", "nodes": count_record["count"]}

        except Exception as e:
            logger.error(
                "Neo4j health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"status": "degraded", "error": str(e)}  # Optional service

    async def check_qdrant(self) -> Dict:
        """Check Qdrant connection"""
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=5,
            )

            # Get collections
            collections = client.get_collections()

            return {"status": "healthy", "collections": len(collections.collections)}

        except Exception as e:
            logger.error(
                "Qdrant health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"status": "degraded", "error": str(e)}

    async def check_elasticsearch(self) -> Dict:
        """Check Elasticsearch connection"""
        try:
            from elasticsearch import AsyncElasticsearch

            es = AsyncElasticsearch([settings.es_url])

            # Cluster health
            health = await es.cluster.health()

            await es.close()

            return {
                "status": (
                    "healthy" if health["status"] in ["green", "yellow"] else "degraded"
                ),
                "cluster_status": health["status"],
                "nodes": health["number_of_nodes"],
            }

        except Exception as e:
            logger.error(
                "Elasticsearch health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"status": "degraded", "error": str(e)}

    async def check_openai(self) -> Dict:
        """Check OpenAI API availability"""
        try:
            import httpx

            api_key = settings.openai_api_key

            if not api_key or api_key == "test":
                return {"status": "disabled", "message": "API key not configured"}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )

                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "models_available": len(response.json()["data"]),
                    }
                else:
                    return {"status": "degraded", "http_status": response.status_code}

        except Exception as e:
            logger.error(
                "OpenAI health check failed",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"status": "degraded", "error": str(e)}


# Global instance
_health_checker = None


def get_health_checker() -> HealthChecker:
    """Get singleton health checker"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
