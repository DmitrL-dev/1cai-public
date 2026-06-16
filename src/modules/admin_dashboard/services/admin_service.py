from datetime import datetime
from typing import Dict

import asyncpg
from fastapi import HTTPException

from src.monitoring.performance_monitor import performance_monitor
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class AdminDashboardService:
    """Сервис для административной панели."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def get_platform_stats(self) -> Dict:
        """Получает агрегированную статистику по всей платформе.

        Собирает данные о тенантах, пользователях, выручке (MRR/ARR) и использовании ресурсов.

        Returns:
            Dict: Словарь с метриками платформы.
        """
        async with self.db.acquire() as conn:
            tenants_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'trial') as trial,
                    COUNT(*) FILTER (WHERE status = 'active') as active,
                    COUNT(*) FILTER (WHERE status = 'suspended') as suspended,
                    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as new_last_30d
                FROM tenants
            """
            )

            users_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total,
                    COUNT(DISTINCT tenant_id) as active_tenants,
                    COUNT(*) FILTER (WHERE last_login_at >= NOW() - INTERVAL '7 days') as active_7d
                FROM users
            """
            )

            revenue_stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_subscriptions,
                    COUNT(*) FILTER (WHERE plan = 'starter') as starter_count,
                    COUNT(*) FILTER (WHERE plan = 'professional') as pro_count,
                    COUNT(*) FILTER (WHERE plan = 'enterprise') as ent_count
                FROM tenants
                WHERE status = 'active'
            """
            )

            mrr = (
                revenue_stats["starter_count"] * 99
                + revenue_stats["pro_count"] * 299
                + revenue_stats["ent_count"] * 999
            )

            usage_stats = await conn.fetchrow(
                """
                SELECT
                    SUM(api_calls) as total_api_calls,
                    SUM(ai_tokens_used) as total_tokens,
                    AVG(storage_used_mb) as avg_storage_mb
                FROM usage_tracking
                WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
            """
            )

        return {
            "tenants": dict(tenants_stats),
            "users": dict(users_stats),
            "revenue": {
                "mrr": mrr,
                "arr": mrr * 12,
                "by_plan": {
                    "starter": revenue_stats["starter_count"],
                    "professional": revenue_stats["pro_count"],
                    "enterprise": revenue_stats["ent_count"],
                },
            },
            "usage": dict(usage_stats) if usage_stats["total_api_calls"] else {},
            "performance": performance_monitor.get_metrics(),
            "generated_at": datetime.now().isoformat(),
        }

    async def get_tenant_details(self, tenant_id: str) -> Dict:
        """Получает полную информацию о конкретном тенанте.

        Включает список пользователей, историю использования и биллинг.

        Args:
            tenant_id: ID тенанта.

        Returns:
            Dict: Структура с данными тенанта.

        Raises:
            HTTPException: Если тенант не найден (404).
        """
        async with self.db.acquire() as conn:
            tenant = await conn.fetchrow("SELECT * FROM tenants WHERE id = $1", tenant_id)

            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found")

            users = await conn.fetch(
                """
                SELECT id, email, name, role, last_login_at
                FROM users
                WHERE tenant_id = $1
            """,
                tenant_id,
            )

            usage = await conn.fetch(
                """
                SELECT date, api_calls, ai_tokens_used, storage_used_mb
                FROM usage_tracking
                WHERE tenant_id = $1
                  AND date >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY date DESC
            """,
                tenant_id,
            )

            billing = await conn.fetch(
                """
                SELECT event_type, amount_cents, currency, created_at
                FROM billing_events
                WHERE tenant_id = $1
                ORDER BY created_at DESC
                LIMIT 20
            """,
                tenant_id,
            )

        return {
            "tenant": dict(tenant),
            "users": [dict(u) for u in users],
            "usage_history": [dict(u) for u in usage],
            "billing_history": [dict(b) for b in billing],
        }
