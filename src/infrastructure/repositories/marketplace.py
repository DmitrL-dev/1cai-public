
"""
PostgreSQL repository for marketplace data with caching and storage helpers.
Версия: 2.1.0

Улучшения:
- Structured logging
- Улучшена обработка ошибок
- Input validation
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    import asyncpg  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    asyncpg = None  # type: ignore

from redis.asyncio import Redis

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

from src.infrastructure.logging.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger

if asyncpg is not None:  # pragma: no branch
    AsyncpgPool = asyncpg.Pool
    AsyncpgRecord = asyncpg.Record
else:  # pragma: no cover
    AsyncpgPool = Any
    AsyncpgRecord = Dict[str, Any]


class MarketplaceRepository:
    """CRUD/access layer for marketplace entities."""

    CACHE_TTL_SECONDS = 300
    FEATURED_CACHE_KEY = "marketplace:featured:{limit}"
    TRENDING_CACHE_KEY = "marketplace:trending:{limit}"
    CATEGORY_CACHE_KEY = "marketplace:category-counts"

    def __init__(
        self,
        pool: AsyncpgPool,
        cache: Optional[Redis] = None,
        storage_config: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the repository.
        
        Args:
            pool: Database connection pool.
            cache: Redis cache client.
            storage_config: S3 storage configuration.
        """
        self.pool = pool
        self.cache = cache
        self.storage_config = storage_config or {}
        if "create_bucket" not in self.storage_config:
            self.storage_config["create_bucket"] = True
        elif not isinstance(self.storage_config["create_bucket"], bool):
            self.storage_config["create_bucket"] = str(self.storage_config["create_bucket"]).lower() not in {
                "false",
                "0",
                "no",
            }
        self._s3_client = None
        self._bucket_verified = False

    async def init(self) -> None:
        """Initialize the database schema."""
        if asyncpg is None:
            raise RuntimeError("asyncpg is required for MarketplaceRepository.init")
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_plugins (
                    id SERIAL PRIMARY KEY,
                    plugin_id TEXT UNIQUE NOT NULL,
                    owner_id TEXT NOT NULL,
                    owner_username TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL,
                    version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    visibility TEXT NOT NULL,
                    homepage TEXT,
                    repository TEXT,
                    download_url TEXT,
                    icon_url TEXT,
                    changelog TEXT,
                    readme TEXT,
                    artifact_path TEXT,
                    screenshot_urls JSONB DEFAULT '[]',
                    keywords JSONB DEFAULT '[]',
                    license TEXT,
                    min_version TEXT,
                    supported_platforms JSONB DEFAULT '[]',
                    rating NUMERIC DEFAULT 0,
                    ratings_count INT DEFAULT 0,
                    downloads INT DEFAULT 0,
                    installs INT DEFAULT 0,
                    featured BOOLEAN DEFAULT FALSE,
                    verified BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    published_at TIMESTAMPTZ
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_reviews (
                    id SERIAL PRIMARY KEY,
                    review_id TEXT UNIQUE NOT NULL,
                    plugin_id TEXT NOT NULL REFERENCES marketplace_plugins(plugin_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    rating INT NOT NULL,
                    comment TEXT,
                    pros TEXT,
                    cons TEXT,
                    helpful_count INT DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_installs (
                    plugin_id TEXT NOT NULL REFERENCES marketplace_plugins(plugin_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    installed_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (plugin_id, user_id)
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_favorites (
                    plugin_id TEXT NOT NULL REFERENCES marketplace_plugins(plugin_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (plugin_id, user_id)
                );
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS marketplace_complaints (
                    id SERIAL PRIMARY KEY,
                    complaint_id TEXT UNIQUE NOT NULL,
                    plugin_id TEXT NOT NULL REFERENCES marketplace_plugins(plugin_id) ON DELETE CASCADE,
                    user_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

    async def close(self) -> None:
        """Close connections."""
        if self.cache:
            await self.cache.close()

    async def create_plugin(
        self,
        plugin_id: str,
        owner_id: str,
        owner_username: str,
        payload: Dict[str, Any],
        download_url: str,
    ) -> Dict[str, Any]:
        """Create a new plugin."""
        # Input validation
        if not plugin_id or not isinstance(plugin_id, str):
            logger.warning(
                "Invalid plugin_id in create_plugin",
                extra={"plugin_id_type": type(
                    plugin_id).__name__ if plugin_id else None},
            )
            raise ValueError("plugin_id must be a non-empty string")

        if not owner_id or not isinstance(owner_id, str):
            logger.warning(
                "Invalid owner_id in create_plugin",
                extra={"owner_id_type": type(owner_id).__name__ if owner_id else None},
            )
            raise ValueError("owner_id must be a non-empty string")

        if not owner_username or not isinstance(owner_username, str):
            logger.warning(
                "Invalid owner_username in create_plugin",
                extra={"owner_username_type": (
                    type(owner_username).__name__ if owner_username else None)},
            )
            raise ValueError("owner_username must be a non-empty string")

        if not isinstance(payload, dict):
            logger.warning(
                "Invalid payload type in create_plugin",
                extra={"payload_type": type(payload).__name__},
            )
            raise ValueError("payload must be a dictionary")

        if not download_url or not isinstance(download_url, str):
            logger.warning(
                "Invalid download_url in create_plugin",
                extra={"download_url_type": (
                    type(download_url).__name__ if download_url else None)},
            )
            raise ValueError("download_url must be a non-empty string")

        # Validate required fields
        if "name" not in payload or not payload["name"]:
            raise ValueError("payload must contain 'name' field")

        if "description" not in payload or not payload["description"]:
            raise ValueError("payload must contain 'description' field")

        if "version" not in payload or not payload["version"]:
            raise ValueError("payload must contain 'version' field")

        category_value = payload.get("category")
        if hasattr(category_value, "value"):
            category_value = category_value.value
        visibility_value = payload.get("visibility", "public")
        if hasattr(visibility_value, "value"):
            visibility_value = visibility_value.value

        query = """
            INSERT INTO marketplace_plugins (
                plugin_id,
                owner_id,
                owner_username,
                name,
                description,
                category,
                version,
                status,
                visibility,
                homepage,
                repository,
                download_url,
                icon_url,
                changelog,
                readme,
                artifact_path,
                screenshot_urls,
                keywords,
                license,
                min_version,
                supported_platforms,
                rating,
                ratings_count,
                downloads,
                installs,
                featured,
                verified,
                created_at,
                updated_at,
                published_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                $14, $15, $16, $17, $18, $19, $20, $21, 0, 0, 0, 0, FALSE, FALSE, NOW(), NOW(), NULL
            )
            RETURNING *
        """

        screenshot_urls = payload.get("screenshot_urls", [])
        keywords = payload.get("keywords", [])
        supported_platforms = payload.get("supported_platforms", [])

        values = (
            plugin_id,
            owner_id,
            owner_username,
            payload["name"],
            payload["description"],
            category_value,
            payload["version"],
            payload.get("status", "pending"),
            visibility_value,
            payload.get("homepage"),
            payload.get("repository"),
            download_url,
            payload.get("icon_url"),
            payload.get("changelog"),
            payload.get("readme"),
            payload.get("artifact_path"),
            json.dumps(screenshot_urls),
            json.dumps(keywords),
            payload.get("license"),
            payload.get("min_version"),
            json.dumps(supported_platforms),
        )

        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(query, *values)

            if not record:
                logger.warning(
                    "Failed to create plugin - no record returned",
                    extra={"plugin_id": plugin_id, "owner_id": owner_id},
                )
                raise ValueError("Failed to create plugin")

            await self._invalidate_caches()

            logger.info(
                "Plugin created successfully",
                extra={
                    "plugin_id": plugin_id,
                    "owner_id": owner_id,
                    "name": payload.get("name"),
                    "category": category_value,
                },
            )

            return self._record_to_plugin(record)
        except Exception as e:
            logger.error(
                f"Error creating plugin: {e}",
                extra={
                    "plugin_id": plugin_id,
                    "owner_id": owner_id,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    async def store_artifact(
        self,
        plugin_id: str,
        data: bytes,
        filename: str,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Store plugin artifact."""
        # Input validation
        if not plugin_id or not isinstance(plugin_id, str):
            logger.warning(
                "Invalid plugin_id in store_artifact",
                extra={"plugin_id_type": type(
                    plugin_id).__name__ if plugin_id else None},
            )
            raise ValueError("plugin_id must be a non-empty string")

        if not data or not isinstance(data, bytes):
            logger.warning(
                "Invalid data in store_artifact",
                extra={"data_type": type(data).__name__ if data else None},
            )
            raise ValueError("Artifact data must be non-empty bytes")

        if not filename or not isinstance(filename, str):
            logger.warning(
                "Invalid filename in store_artifact",
                extra={"filename_type": type(filename).__name__ if filename else None},
            )
            raise ValueError("filename must be a non-empty string")

        # Validate file size (prevent DoS)
        max_file_size = 100 * 1024 * 1024  # 100MB max
        if len(data) > max_file_size:
            logger.warning(
                "Artifact file too large",
                extra={
                    "plugin_id": plugin_id,
                    "filename": filename,
                    "file_size": len(data),
                    "max_size": max_file_size,
                },
            )
            raise ValueError(
                f"Artifact file too large: {len(data)} bytes. Maximum: {max_file_size} bytes")

        # Sanitize filename (prevent path traversal)
        filename = os.path.basename(filename)  # Remove any path components
        if not filename or filename == "." or filename == "..":
            logger.warning(
                "Filename sanitized to invalid value",
                extra={"plugin_id": plugin_id, "original_filename": filename},
            )
            raise ValueError("Invalid filename")

        if not self._s3_available:
            raise RuntimeError(
                "Object storage is not configured for marketplace artifacts")

        await self._ensure_bucket()

        object_key = self._build_object_key(plugin_id, filename)

        loop = asyncio.get_running_loop()

        def _upload() -> None:
            client = self._get_s3_client()
            if client is None:
                raise RuntimeError("S3 client is not available")
            put_kwargs: Dict[str, Any] = {
                "Bucket": self.storage_config["bucket"],
                "Key": object_key,
                "Body": data,
            }
            if content_type:
                put_kwargs["ContentType"] = content_type
            client.put_object(**put_kwargs)

        try:
            await loop.run_in_executor(None, _upload)

            logger.info(
                "Artifact uploaded successfully",
                extra={
                    "plugin_id": plugin_id,
                    "object_key": object_key,
                    "artifact_filename": filename,
                    "size": len(data),
                },
            )
        except (BotoCoreError, ClientError) as exc:
            logger.error(
                f"Failed to upload artifact: {exc}",
                extra={
                    "plugin_id": plugin_id,
                    "object_key": object_key,
                    "artifact_filename": filename,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            raise RuntimeError(f"Failed to upload artifact: {exc}") from exc

        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(
                    """
                    UPDATE marketplace_plugins
                    SET artifact_path = $2,
                    download_url = $3,
                    updated_at = NOW()
                    WHERE plugin_id = $1
                    RETURNING *
                    """,
                    plugin_id,
                    object_key,
                    f"/marketplace/plugins/{plugin_id}/download",
                )

            if not record:
                logger.warning(
                    "Plugin not found after artifact upload",
                    extra={"plugin_id": plugin_id},
                )
                raise ValueError("Plugin not found")

            await self._invalidate_caches(plugin_id)

            logger.info(
                "Plugin artifact path updated",
                extra={"plugin_id": plugin_id, "artifact_path": object_key},
            )

            return self._record_to_plugin(record)
        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Error updating plugin artifact path: {e}",
                extra={
                    "plugin_id": plugin_id,
                    "object_key": object_key,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            raise

    async def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin by ID."""
        # Input validation
        if not plugin_id or not isinstance(plugin_id, str):
            logger.warning(
                "Invalid plugin_id in get_plugin",
                extra={"plugin_id_type": type(
                    plugin_id).__name__ if plugin_id else None},
            )
            return None

        try:
            async with self.pool.acquire() as conn:
                record = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
            if record:
                return self._record_to_plugin(record)
            return None
        except Exception as e:
            logger.error(
                f"Error getting plugin: {e}",
                extra={"plugin_id": plugin_id, "error_type": type(e).__name__},
                exc_info=True,
            )
            return None

    async def update_plugin(self, plugin_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update plugin details."""
        if not update_data:
            return await self.get_plugin(plugin_id)

        set_parts: List[str] = ["updated_at = NOW()"]
        values: List[Any] = [plugin_id]
        idx = 1

        for key, value in update_data.items():
            column = self._map_field_to_column(key)
            if column is None:
                continue
            idx += 1
            set_parts.append(f"{column} = ${idx}")
            if key in {"keywords", "supported_platforms", "screenshot_urls"}:
                values.append(json.dumps(value))
            else:
                values.append(value)

        if len(set_parts) == 1:
            return await self.get_plugin(plugin_id)

        query = "UPDATE marketplace_plugins SET " + \
            ", ".join(set_parts) + " WHERE plugin_id = $1 RETURNING *"

        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(query, *values)
        if record:
            await self._invalidate_caches(plugin_id)
            return self._record_to_plugin(record)
        return None

    async def soft_delete_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Soft delete a plugin."""
        async with self.pool.acquire() as conn:
            record = await conn.fetchrow(
                """
                UPDATE marketplace_plugins
                SET status = 'removed', updated_at = NOW()
                WHERE plugin_id = $1
                RETURNING *
                """,
                plugin_id,
            )
        if record:
            await self._invalidate_caches(plugin_id)
            return self._record_to_plugin(record)
        return None

    async def search_plugins(
        self,
        query_text: Optional[str],
        category: Optional[str],
        author: Optional[str],
        sort_by: str,
        order: str,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search plugins."""
        conditions = ["status = 'approved'", "visibility = 'public'"]
        params: List[Any] = []

        if query_text:
            conditions.append(
                "(LOWER(name) LIKE $1 OR LOWER(description) LIKE $1 OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(keywords) kw WHERE LOWER(kw) LIKE $1))"
            )
            params.append(f"%{query_text.lower()}%")
        if category:
            conditions.append(f"category = ${len(params)+1}")
            params.append(category)
        if author:
            conditions.append(f"owner_username = ${len(params)+1}")
            params.append(author)

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

        order_column = {
            "rating": "rating",
            "downloads": "downloads",
            "updated": "updated_at",
            "name": "name",
        }.get(sort_by, "rating")
        order_value = "DESC" if order.lower() == "desc" else "ASC"

        offset = (page - 1) * page_size

        sql = f"""
            SELECT *, COUNT(*) OVER() AS total_count
            FROM marketplace_plugins
            {where_clause}
            ORDER BY {order_column} {order_value}
            LIMIT $${len(params)+1} OFFSET $${len(params)+2}
        """

        params.extend([page_size, offset])

        async with self.pool.acquire() as conn:
            records = await conn.fetch(sql, *params)

        if not records:
            return [], 0

        total = records[0]["total_count"]
        return [self._record_to_plugin(rec) for rec in records], total

    async def record_install(self, plugin_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Record plugin installation."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                plugin = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
                if not plugin:
                    return None
                await conn.execute(
                    """
                    INSERT INTO marketplace_installs (plugin_id, user_id)
                    VALUES ($1, $2)
                    ON CONFLICT DO NOTHING
                    """,
                    plugin_id,
                    user_id,
                )
                # Optimized: Use single UPDATE with subquery (best practice: avoid N+1)
                await conn.execute(
                    """
                    UPDATE marketplace_plugins
                    SET downloads = downloads + 1,
                    installs = (
                        SELECT COUNT(*)
                        FROM marketplace_installs
                        WHERE plugin_id = marketplace_plugins.plugin_id
                    ),
                    updated_at = NOW()
                    WHERE plugin_id = $1
                    """,
                    plugin_id,
                )
                record = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
        await self._invalidate_caches(plugin_id)
        if record:
            return self._record_to_plugin(record)
        return None

    async def remove_install(self, plugin_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove plugin installation record."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                plugin = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
                if not plugin:
                    return None
                await conn.execute(
                    "DELETE FROM marketplace_installs WHERE plugin_id = $1 AND user_id = $2",
                    plugin_id,
                    user_id,
                )
                # Optimized: Use correlated subquery (best practice: avoid N+1)
                await conn.execute(
                    """
                    UPDATE marketplace_plugins
                    SET installs = (
                        SELECT COUNT(*)
                        FROM marketplace_installs
                        WHERE plugin_id = marketplace_plugins.plugin_id
                    ),
                        updated_at = NOW()
                    WHERE plugin_id = $1
                    """,
                    plugin_id,
                )
                record = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
        await self._invalidate_caches(plugin_id)
        if record:
            return self._record_to_plugin(record)
        return None

    async def user_has_installed(self, plugin_id: str, user_id: str) -> bool:
        """Check if user has installed the plugin."""
        async with self.pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT 1 FROM marketplace_installs WHERE plugin_id = $1 AND user_id = $2",
                plugin_id,
                user_id,
            )
        return result is not None

    async def add_favorite(self, plugin_id: str, user_id: str) -> None:
        """Add plugin to favorites."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO marketplace_favorites (plugin_id, user_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                plugin_id,
                user_id,
            )
        await self._invalidate_caches(plugin_id)

    async def remove_favorite(self, plugin_id: str, user_id: str) -> None:
        """Remove plugin from favorites."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM marketplace_favorites WHERE plugin_id = $1 AND user_id = $2",
                plugin_id,
                user_id,
            )
        await self._invalidate_caches(plugin_id)

    async def create_review(
        self,
        review_id: str,
        plugin_id: str,
        user_id: str,
        user_name: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Create a new review."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                plugin = await conn.fetchrow(
                    "SELECT * FROM marketplace_plugins WHERE plugin_id = $1",
                    plugin_id,
                )
                if not plugin:
                    return None
                record = await conn.fetchrow(
                    """
                    INSERT INTO marketplace_reviews (
                        review_id, plugin_id, user_id, user_name, rating, comment, pros, cons
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                    """,
                    review_id,
                    plugin_id,
                    user_id,
                    user_name,
                    payload["rating"],
                    payload.get("comment"),
                    payload.get("pros"),
                    payload.get("cons"),
                )
                await conn.execute(
                    """
                    UPDATE marketplace_plugins
                    SET rating = sub.avg_rating,
                    ratings_count = sub.total_reviews,
                    updated_at = NOW()
                    FROM (
                        SELECT plugin_id,
                               AVG(rating) AS avg_rating,
                               COUNT(*) AS total_reviews
                        FROM marketplace_reviews
                        WHERE plugin_id = $1
                        GROUP BY plugin_id
                    ) AS sub
                    WHERE marketplace_plugins.plugin_id = sub.plugin_id
                    """,
                    plugin_id,
                )
        await self._invalidate_caches(plugin_id)
        if record:
            return self._record_to_review(record)
        return None

    async def list_reviews(
        self,
        plugin_id: str,
        page: int,
        page_size: int,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List reviews for a plugin."""
        offset = (page - 1) * page_size
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT *, COUNT(*) OVER() AS total_count
                FROM marketplace_reviews
                WHERE plugin_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                plugin_id,
                page_size,
                offset,
            )
        if not records:
            return [], 0
        total = records[0]["total_count"]
        return [self._record_to_review(record) for record in records], total

    async def get_plugin_stats(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin statistics with optimized single query

        Best practice: Use single query with CTE/aggregations instead of multiple queries
        """
        async with self.pool.acquire() as conn:
            # Optimized: Single query with CTE to get all stats at once
            result = await conn.fetchrow(
                """
                WITH plugin_data AS (
                    SELECT * FROM marketplace_plugins WHERE plugin_id = $1
                ),
                review_stats AS (
                    SELECT
                        COUNT(*) AS reviews_count,
                        AVG(rating) AS avg_rating,
                        AVG(rating) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS avg_rating_30d,
                        AVG(rating) FILTER (
                            WHERE created_at >= NOW() - INTERVAL '60 days'
                              AND created_at < NOW() - INTERVAL '30 days'
                        ) AS avg_rating_prev_30d
                    FROM marketplace_reviews
                    WHERE plugin_id = $1
                ),
                review_distribution AS (
                    SELECT json_object_agg(rating, count) FILTER (WHERE rating IS NOT NULL) AS rating_dist
                    FROM (
                        SELECT rating, COUNT(*) AS count
                        FROM marketplace_reviews
                        WHERE plugin_id = $1
                        GROUP BY rating
                    ) AS rating_counts
                ),
                counts AS (
                    SELECT
                        (SELECT COUNT(*) FROM marketplace_favorites WHERE plugin_id = $1) AS favorites_count,
                        (SELECT COUNT(*) FROM marketplace_installs WHERE plugin_id = $1) AS installs_active
                ),
                download_stats AS (
                    SELECT
                        COUNT(*) FILTER (WHERE installed_at >= NOW() - INTERVAL '30 days') AS downloads_30d,
                        COUNT(*) FILTER (WHERE installed_at >= NOW() - INTERVAL '60 days' AND installed_at < NOW() - INTERVAL '30 days') AS downloads_prev_30d
                    FROM marketplace_installs
                    WHERE plugin_id = $1
                )
                SELECT
                    p.*,
                    COALESCE(r.reviews_count, 0) AS reviews_count,
                    COALESCE(r.avg_rating, 0) AS avg_rating,
                    COALESCE(r.avg_rating_30d, 0) AS avg_rating_30d,
                    COALESCE(r.avg_rating_prev_30d, 0) AS avg_rating_prev_30d,
                    rd.rating_dist,
                    c.favorites_count,
                    c.installs_active,
                    d.downloads_30d,
                    d.downloads_prev_30d
                FROM plugin_data p
                CROSS JOIN review_stats r
                CROSS JOIN review_distribution rd
                CROSS JOIN counts c
                CROSS JOIN download_stats d
                """,
                plugin_id,
            )

            if not result:
                return None

            plugin = dict(result)

            # Build rating distribution
            rating_distribution = {i: 0 for i in range(1, 6)}
            if plugin.get("rating_dist"):
                import json

                dist = (
                    json.loads(plugin["rating_dist"])
                    if isinstance(plugin["rating_dist"], str)
                    else plugin["rating_dist"]
                )
                if isinstance(dist, dict):
                    for rating, count in dist.items():
                        rating_distribution[int(rating)] = count
            
            # Calculate trend
            downloads_30d = plugin["downloads_30d"]
            downloads_prev = plugin["downloads_prev_30d"]
            
            if downloads_30d > downloads_prev * 1.1:
                trend = "up"
            elif downloads_30d < downloads_prev * 0.9:
                trend = "down"
            else:
                trend = "stable"

            rating_30d = float(plugin.get("avg_rating_30d") or 0)
            rating_prev = float(plugin.get("avg_rating_prev_30d") or 0)
            if rating_prev <= 0:
                rating_trend = "stable"
            elif rating_30d > rating_prev + 0.1:
                rating_trend = "up"
            elif rating_30d < rating_prev - 0.1:
                rating_trend = "down"
            else:
                rating_trend = "stable"

            stats = {
                "plugin_id": plugin_id,
                "downloads_total": plugin["downloads"],
                "downloads_last_30_days": downloads_30d,
                "installs_active": plugin["installs_active"],
                "rating_average": float(plugin["avg_rating"] or plugin.get("rating") or 0),
                "rating_distribution": rating_distribution,
                "reviews_count": plugin["reviews_count"],
                "favorites_count": plugin["favorites_count"],
                "downloads_trend": trend,
                "rating_trend": rating_trend,
            }
            return stats

    async def get_category_counts(self) -> Dict[str, int]:
        """Get plugin counts by category."""
        if self.cache:
            cached = await self.cache.get(self.CATEGORY_CACHE_KEY)
            if cached:
                return json.loads(cached)
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT category, COUNT(*) AS count
                FROM marketplace_plugins
                WHERE status = 'approved'
                GROUP BY category
                """
            )
        counts = {row["category"]: row["count"] for row in rows}
        if self.cache:
            await self.cache.set(self.CATEGORY_CACHE_KEY, json.dumps(counts), ex=self.CACHE_TTL_SECONDS)
        return counts

    async def get_featured_plugins(self, limit: int) -> List[Dict[str, Any]]:
        """Get featured plugins."""
        cache_key = self.FEATURED_CACHE_KEY.format(limit=limit)
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT * FROM marketplace_plugins
                WHERE status = 'approved' AND featured = TRUE
                ORDER BY rating DESC, updated_at DESC
                LIMIT $1
                """,
                limit,
            )
        plugins = [self._record_to_plugin(record) for record in records]
        if self.cache:
            await self.cache.set(cache_key, json.dumps(plugins, default=str), ex=self.CACHE_TTL_SECONDS)
        return plugins

    async def get_trending_plugins(self, limit: int) -> List[Dict[str, Any]]:
        """Get trending plugins."""
        cache_key = self.TRENDING_CACHE_KEY.format(limit=limit)
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        async with self.pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT * FROM marketplace_plugins
                WHERE status = 'approved' AND visibility = 'public'
                ORDER BY downloads DESC, rating DESC
                LIMIT $1
                """,
                limit,
            )
        plugins = [self._record_to_plugin(record) for record in records]
        if self.cache:
            await self.cache.set(cache_key, json.dumps(plugins, default=str), ex=self.CACHE_TTL_SECONDS)
        return plugins

    async def add_complaint(
        self,
        complaint_id: str,
        plugin_id: str,
        user_id: str,
        reason: str,
        details: Optional[str],
    ) -> None:
        """Add a complaint against a plugin."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO marketplace_complaints (complaint_id, plugin_id, user_id, reason, details)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (complaint_id) DO NOTHING
                """,
                complaint_id,
                plugin_id,
                user_id,
                reason,
                details,
            )

    async def refresh_cached_views(self) -> None:
        """Refresh cached views."""
        if not self.cache:
            return
        await self.get_category_counts()  # refresh
        for limit in (5, 10):
            await self.get_featured_plugins(limit)
            await self.get_trending_plugins(limit)

    async def build_download_payload(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        """Build download payload."""
        artifact_path = plugin.get("artifact_path")
        presigned_url: Optional[str] = None
        if artifact_path and self._s3_available:
            try:
                client = self._get_s3_client()
                if client:
                    presigned_url = client.generate_presigned_url(
                        "get_object",
                        Params={
                            "Bucket": self.storage_config["bucket"],
                            "Key": artifact_path,
                        },
                        ExpiresIn=300,
                    )
            except (ClientError, BotoCoreError):  # pragma: no cover
                presigned_url = None
        return {
            "status": "ready",
            "plugin_id": plugin["plugin_id"],
            "download_url": presigned_url or plugin.get("download_url"),
            "message": ("Download link generated" if presigned_url else "Download will be implemented in production"),
            "files": ["manifest.json", "README.md", "plugin.py"],
        }

    def _record_to_plugin(self, record: AsyncpgRecord) -> Dict[str, Any]:
        screenshot_urls = self._ensure_list(record["screenshot_urls"])
        keywords = self._ensure_list(record["keywords"])
        supported_platforms = self._ensure_list(record["supported_platforms"])

        return {
            "id": record["plugin_id"],
            "plugin_id": record["plugin_id"],
            "name": record["name"],
            "description": record["description"],
            "category": record["category"],
            "version": record["version"],
            "author": record["owner_username"],
            "status": record["status"],
            "visibility": record["visibility"],
            "downloads": record["downloads"],
            "rating": float(record["rating"] or 0),
            "ratings_count": record["ratings_count"],
            "installs": record["installs"],
            "homepage": record["homepage"],
            "repository": record["repository"],
            "download_url": record["download_url"],
            "icon_url": record["icon_url"],
            "changelog": record["changelog"],
            "readme": record["readme"],
            "artifact_path": record["artifact_path"],
            "screenshot_urls": screenshot_urls,
            "keywords": keywords,
            "license": record["license"],
            "min_version": record["min_version"],
            "supported_platforms": supported_platforms,
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "published_at": record["published_at"],
            "featured": record["featured"],
            "verified": record["verified"],
            "owner_id": record["owner_id"],
            "owner_username": record["owner_username"],
        }

    def _record_to_review(self, record: AsyncpgRecord) -> Dict[str, Any]:
        return {
            "id": record["review_id"],
            "plugin_id": record["plugin_id"],
            "user_id": record["user_id"],
            "user_name": record["user_name"],
            "rating": record["rating"],
            "comment": record["comment"],
            "pros": record["pros"],
            "cons": record["cons"],
            "helpful_count": record["helpful_count"],
            "created_at": record["created_at"],
        }

    def _map_field_to_column(self, field: str) -> Optional[str]:
        mapping = {
            "version": "version",
            "description": "description",
            "changelog": "changelog",
            "homepage": "homepage",
            "repository": "repository",
            "keywords": "keywords",
            "icon_url": "icon_url",
            "screenshot_urls": "screenshot_urls",
            "readme": "readme",
            "status": "status",
            "visibility": "visibility",
            "featured": "featured",
            "verified": "verified",
            "published_at": "published_at",
            "artifact_path": "artifact_path",
        }
        return mapping.get(field)

    def _ensure_list(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [value]
        return list(value)

    async def _invalidate_caches(self, plugin_id: Optional[str] = None) -> None:
        if not self.cache:
            return
        keys = [self.CATEGORY_CACHE_KEY]
        for limit in (5, 10):
            keys.append(self.FEATURED_CACHE_KEY.format(limit=limit))
            keys.append(self.TRENDING_CACHE_KEY.format(limit=limit))
        await self.cache.delete(*keys)

    @property
    def _s3_available(self) -> bool:
        has_bucket = bool(self.storage_config.get("bucket"))
        has_credentials = bool(self.storage_config.get("access_key") or os.getenv("AWS_ACCESS_KEY_ID")) and bool(
            self.storage_config.get("secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
        )
        return has_bucket and has_credentials and (boto3 is not None or self._s3_client is not None)

    def _get_s3_client(self):
        if not self._s3_available:
            return None
        if self._s3_client is None:
            access_key = self.storage_config.get(
                "access_key") or os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = self.storage_config.get(
                "secret_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
            session = boto3.session.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=self.storage_config.get("region") or None,
            )
            endpoint_url = self.storage_config.get("endpoint") or None
            self._s3_client = session.client("s3", endpoint_url=endpoint_url)
        return self._s3_client

    async def _ensure_bucket(self) -> None:
        if self._bucket_verified:
            return
        bucket = self.storage_config.get("bucket")
        if not bucket:
            raise RuntimeError("S3 bucket is not configured")

        def _check_or_create() -> None:
            client = self._get_s3_client()
            if client is None:
                raise RuntimeError("S3 client is not available")
            try:
                client.head_bucket(Bucket=bucket)
                return
            except ClientError as exc:
                error_code = exc.response.get("Error", {}).get("Code")
                if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
            if not self.storage_config.get("create_bucket", True):
                raise RuntimeError(
                    f"S3 bucket '{bucket}' does not exist and auto-creation is disabled")
            create_kwargs: Dict[str, Any] = {"Bucket": bucket}
            region = self.storage_config.get("region")
            if region and region not in {"", "us-east-1"}:
                create_kwargs["CreateBucketConfiguration"] = {
                    "LocationConstraint": region}
            client.create_bucket(**create_kwargs)

        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(None, _check_or_create)
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to ensure bucket '{bucket}': {exc}") from exc

        self._bucket_verified = True

    def _build_object_key(self, plugin_id: str, filename: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "-", filename or "artifact.zip")
        safe_name = safe_name.strip("-") or "artifact.zip"
        return f"marketplace/{plugin_id}/{uuid.uuid4().hex}/{safe_name}"
