import hashlib
import os
import secrets
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

import asyncpg

from src.modules.tenant_management.domain.models import TenantRegistrationRequest
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger


class TenantManagementService:
    """Service for tenant management."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

        # Stripe (if available)
        self.stripe_available = False
        try:
            import stripe

            stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
            if stripe.api_key:
                self.stripe = stripe
                self.stripe_available = True
        except (ImportError, Exception):
            logger.warning("Stripe not available")

    async def create_tenant(self, registration: TenantRegistrationRequest) -> Dict[str, Any]:
        """Create new tenant."""
        tenant_id = uuid.uuid4()

        async with self.db.acquire() as conn:
            # 1. Create tenant
            await conn.execute(
                """
                INSERT INTO tenants (
                    id,
                    company_name,
                    plan,
                    status,
                    created_at,
                    trial_ends_at,
                    max_users,
                    max_api_calls_month,
                    max_storage_gb
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                tenant_id,
                registration.company_name,
                registration.plan,
                "trial",
                datetime.now(),
                datetime.now() + timedelta(days=14),
                *self._get_plan_limits(registration.plan),
            )

            # 2. Create admin user
            admin_id = uuid.uuid4()
            temp_password = self._generate_password()
            password_hash = self._hash_password(temp_password)

            await conn.execute(
                """
                INSERT INTO users (
                    id,
                    tenant_id,
                    email,
                    name,
                    password_hash,
                    role,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                admin_id,
                tenant_id,
                registration.admin_email,
                registration.admin_name,
                password_hash,
                "admin",
                datetime.now(),
            )

        # 3. Initialize resources
        await self._initialize_tenant_resources(tenant_id)

        # 4. Create Stripe customer (if available)
        stripe_info = {}
        if self.stripe_available:
            stripe_info = await self._create_stripe_subscription(tenant_id, registration)

        logger.info(
            "Tenant created",
            extra={
                "tenant_id": str(tenant_id),
                "admin_email": registration.admin_email,
            },
        )

        return {
            "tenant_id": str(tenant_id),
            "company_name": registration.company_name,
            "admin_email": registration.admin_email,
            "plan": registration.plan,
            "status": "trial",
            "trial_ends_at": (datetime.now() + timedelta(days=14)).isoformat(),
            "temporary_password": temp_password,
            "login_url": f"https://app.1c-ai.com/login?tenant={tenant_id}",
            "stripe": stripe_info,
        }

    def _get_plan_limits(self, plan: str) -> tuple:
        """Get plan limits."""
        limits = {
            "starter": (5, 10000, 5),
            "professional": (20, 50000, 50),
            "enterprise": (9999, 999999999, 1000),
        }
        return limits.get(plan, limits["starter"])

    async def _initialize_tenant_resources(self, tenant_id: uuid.UUID):
        """Initialize tenant resources."""
        logger.info("Initializing resources for tenant",
                    extra={"tenant_id": str(tenant_id)})

    async def _create_stripe_subscription(self, tenant_id: uuid.UUID, registration: TenantRegistrationRequest) -> Dict:
        """Create Stripe customer and subscription."""
        try:
            customer = self.stripe.Customer.create(
                email=registration.admin_email,
                name=registration.company_name,
                metadata={"tenant_id": str(tenant_id)},
            )

            price_id = self._get_stripe_price_id(registration.plan)

            subscription = self.stripe.Subscription.create(
                customer=customer.id, items=[{"price": price_id}], trial_period_days=14
            )

            async with self.db.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE tenants
                    SET stripe_customer_id = $1,
                        stripe_subscription_id = $2
                    WHERE id = $3
                """,
                    customer.id,
                    subscription.id,
                    tenant_id,
                )

            return {
                "customer_id": customer.id,
                "subscription_id": subscription.id,
                "status": subscription.status,
            }

        except Exception as e:
            logger.error(
                "Stripe error",
                extra={"error": str(e), "error_type": type(e).__name__},
                exc_info=True,
            )
            return {"error": str(e)}

    def _get_stripe_price_id(self, plan: str) -> str:
        """Get Stripe Price ID for plan."""
        price_ids = {
            "starter": os.getenv("STRIPE_PRICE_STARTER", "price_starter"),
            "professional": os.getenv("STRIPE_PRICE_PRO", "price_pro"),
            "enterprise": os.getenv("STRIPE_PRICE_ENT", "price_ent"),
        }
        return price_ids.get(plan, price_ids["starter"])

    def _generate_password(self) -> str:
        """Generate temporary password."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16))

    def _hash_password(self, password: str) -> str:
        """Hash password."""
        return hashlib.sha256(password.encode()).hexdigest()

    async def get_tenant_usage(self, tenant_id: str) -> Dict[str, Any] | None:
        """Get tenant usage metrics."""
        async with self.db.acquire() as conn:
            usage = await conn.fetchrow(
                "SELECT * FROM tenant_usage_summary WHERE tenant_id = $1",
                uuid.UUID(tenant_id),
            )

            if not usage:
                return None

            return dict(usage)
