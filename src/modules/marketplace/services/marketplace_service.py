import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile

from src.db.marketplace_repository import MarketplaceRepository
from src.modules.marketplace.domain.models import (
    PluginStatus,
    PluginVisibility,
)
from src.security import CurrentUser, get_audit_logger
from src.utils.structured_logging import StructuredLogger

logger = StructuredLogger(__name__).logger
audit_logger = get_audit_logger()

MAX_ARTIFACT_SIZE_BYTES = int(
    os.getenv("MARKETPLACE_MAX_ARTIFACT_SIZE_MB", "25")) * 1024 * 1024


class MarketplaceService:
    """
    Service for managing marketplace plugins and reviews.
    Encapsulates business logic and repository interactions.
    """

    def __init__(self, repo: MarketplaceRepository):
        self.repo = repo

    async def submit_plugin(self, plugin_data: Dict[str, Any], user: CurrentUser) -> Dict[str, Any]:
        """Submit a new plugin."""
        sanitized_name = plugin_data["name"].strip()[:200]
        if not sanitized_name:
            raise ValueError("Plugin name cannot be empty")

        plugin_id = f"plugin_{uuid.uuid4().hex}"
        payload = plugin_data.copy()
        payload["status"] = PluginStatus.PENDING.value
        payload.setdefault("visibility", PluginVisibility.PUBLIC.value)
        payload["name"] = sanitized_name

        owner_username = (user.username or user.user_id).strip()[:100]

        persisted = await self.repo.create_plugin(
            plugin_id=plugin_id,
            owner_id=user.user_id,
            owner_username=owner_username,
            payload=payload,
            download_url=f"/marketplace/plugins/{plugin_id}/download",
        )

        logger.info(
            "Plugin submitted",
            extra={
                "plugin_id": plugin_id,
                "plugin_name": sanitized_name,
                "user_id": user.user_id,
            },
        )
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.submit",
            target=plugin_id,
            metadata={"name": sanitized_name, "status": PluginStatus.PENDING.value},
        )

        return persisted

    async def search_plugins(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        author: Optional[str] = None,
        sort_by: str = "rating",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Search plugins."""
        return await self.repo.search_plugins(
            query_text=query,
            category=category,
            author=author,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )

    async def get_plugin(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin by ID."""
        return await self.repo.get_plugin(plugin_id)

    async def update_plugin(
        self, plugin_id: str, update_data: Dict[str, Any], user: CurrentUser
    ) -> Optional[Dict[str, Any]]:
        """Update plugin."""
        plugin = await self.repo.get_plugin(plugin_id)
        if not plugin:
            return None

        if not self._check_authorization(user, plugin):
            raise PermissionError("You don't have permission to update this plugin")

        if "version" in update_data and update_data["version"] != plugin.get("version"):
            update_data["status"] = PluginStatus.PENDING.value

        updated = await self.repo.update_plugin(plugin_id, update_data)

        logger.info("Plugin updated: %s by user %s", plugin_id, user.user_id)
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.update",
            target=plugin_id,
            metadata={"fields": list(update_data.keys())},
        )
        return updated

    async def upload_artifact(self, plugin_id: str, file: UploadFile, user: CurrentUser) -> Dict[str, Any]:
        """Upload plugin artifact."""
        plugin = await self.repo.get_plugin(plugin_id)
        if not plugin:
            raise ValueError("Plugin not found")

        if not self._check_authorization(user, plugin):
            raise PermissionError("You don't have permission to update this plugin")

        data = await file.read()
        try:
            await file.close()
        except Exception:
            pass

        if not data:
            raise ValueError("Uploaded file is empty")
        if len(data) > MAX_ARTIFACT_SIZE_BYTES:
            max_mb = MAX_ARTIFACT_SIZE_BYTES // (1024 * 1024)
            raise ValueError(f"Artifact exceeds maximum size of {max_mb} MB")

        updated = await self.repo.store_artifact(
            plugin_id=plugin_id,
            data=data,
            filename=file.filename or f"{plugin_id}.zip",
            content_type=file.content_type,
        )

        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.artifact.upload",
            target=plugin_id,
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": len(data),
            },
        )
        return updated

    async def delete_plugin(self, plugin_id: str, user: CurrentUser) -> Optional[Dict[str, Any]]:
        """Soft delete plugin."""
        plugin = await self.repo.get_plugin(plugin_id)
        if not plugin:
            return None

        if not self._check_authorization(user, plugin):
            raise PermissionError("You don't have permission to delete this plugin")

        removed = await self.repo.soft_delete_plugin(plugin_id)

        logger.info("Plugin removed: %s by user %s", plugin_id, user.user_id)
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.delete",
            target=plugin_id,
            metadata={"status": removed.get("status") if removed else "removed"},
        )
        return removed

    async def record_install(self, plugin_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Record plugin installation."""
        updated = await self.repo.record_install(plugin_id, user_id)
        if updated:
            logger.info("Plugin installed: %s by user %s", plugin_id, user_id)
        return updated

    async def remove_install(self, plugin_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Remove plugin installation record."""
        updated = await self.repo.remove_install(plugin_id, user_id)
        if updated:
            logger.info("Plugin uninstalled: %s by user %s", plugin_id, user_id)
        return updated

    async def get_stats(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Get plugin statistics."""
        return await self.repo.get_plugin_stats(plugin_id)

    async def create_review(self, plugin_id: str, review_data: Dict[str, Any], user: CurrentUser) -> Dict[str, Any]:
        """Create a review."""
        plugin = await self.repo.get_plugin(plugin_id)
        if not plugin:
            raise ValueError("Plugin not found")

        if not await self.repo.user_has_installed(plugin_id, user.user_id):
            raise PermissionError("You must install the plugin before leaving a review")

        review_id = f"review_{uuid.uuid4().hex}"
        display_name = user.full_name or user.username
        if not display_name and len(user.user_id) >= 4:
            display_name = f"User {user.user_id[-4:]}"

        stored = await self.repo.create_review(
            review_id=review_id,
            plugin_id=plugin_id,
            user_id=user.user_id,
            user_name=display_name,
            payload=review_data,
        )

        logger.info(
            "Review submitted: %s for plugin %s by user %s",
            review_id,
            plugin_id,
            user.user_id,
        )
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.review.create",
            target=plugin_id,
            metadata={"review_id": review_id, "rating": review_data.get("rating")},
        )
        return stored

    async def list_reviews(
        self, plugin_id: str, page: int = 1, page_size: int = 10
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List reviews for a plugin."""
        return await self.repo.list_reviews(plugin_id, page, page_size)

    async def build_download_payload(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        """Build download payload."""
        plugin = await self.repo.get_plugin(plugin_id)
        if not plugin:
            return None
        return await self.repo.build_download_payload(plugin)

    async def get_category_counts(self) -> Dict[str, int]:
        """Get plugin counts by category."""
        return await self.repo.get_category_counts()

    async def get_featured(self, limit: int = 6) -> List[Dict[str, Any]]:
        """Get featured plugins."""
        return await self.repo.get_featured_plugins(limit)

    async def get_trending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending plugins."""
        return await self.repo.get_trending_plugins(limit)

    async def add_favorite(self, plugin_id: str, user_id: str) -> None:
        """Add to favorites."""
        await self.repo.add_favorite(plugin_id, user_id)
        logger.info("Plugin %s added to favorites by user %s", plugin_id, user_id)

    async def remove_favorite(self, plugin_id: str, user_id: str) -> None:
        """Remove from favorites."""
        await self.repo.remove_favorite(plugin_id, user_id)
        logger.info("Plugin %s removed from favorites by user %s", plugin_id, user_id)

    async def report_plugin(self, plugin_id: str, reason: str, details: Optional[str], user: CurrentUser) -> None:
        """Report a plugin."""
        complaint_id = f"complaint_{uuid.uuid4().hex}"
        await self.repo.add_complaint(
            complaint_id=complaint_id,
            plugin_id=plugin_id,
            user_id=user.user_id,
            reason=reason,
            details=details,
        )
        logger.warning("Plugin %s reported by user %s: %s",
                       plugin_id, user.user_id, reason)
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.report",
            target=plugin_id,
            metadata={"reason": reason},
        )

    # Admin actions
    async def approve_plugin(self, plugin_id: str, user: CurrentUser) -> None:
        """Approve plugin."""
        await self.repo.update_plugin(
            plugin_id,
            {
                "status": PluginStatus.APPROVED.value,
                "published_at": datetime.utcnow(),
            },
        )
        logger.info("Plugin approved by %s: %s", user.user_id, plugin_id)
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.approve",
            target=plugin_id,
            metadata={"status": PluginStatus.APPROVED.value},
        )

    async def reject_plugin(self, plugin_id: str, reason: str, user: CurrentUser) -> None:
        """Reject plugin."""
        await self.repo.update_plugin(
            plugin_id,
            {
                "status": PluginStatus.REJECTED.value,
            },
        )
        logger.info(
            "Plugin rejected by %s: %s (reason: %s)",
            user.user_id,
            plugin_id,
            reason,
        )
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.reject",
            target=plugin_id,
            metadata={"reason": reason},
        )

    async def set_featured(self, plugin_id: str, featured: bool, user: CurrentUser) -> None:
        """Set featured status."""
        await self.repo.update_plugin(plugin_id, {"featured": featured})
        logger.info(
            "Plugin %s featured=%s by %s",
            plugin_id,
            featured,
            user.user_id,
        )
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.feature",
            target=plugin_id,
            metadata={"featured": featured},
        )

    async def set_verified(self, plugin_id: str, verified: bool, user: CurrentUser) -> None:
        """Set verified status."""
        await self.repo.update_plugin(plugin_id, {"verified": verified})
        logger.info(
            "Plugin %s verified=%s by %s",
            plugin_id,
            verified,
            user.user_id,
        )
        audit_logger.log_action(
            actor=user.user_id,
            action="marketplace.plugin.verify",
            target=plugin_id,
            metadata={"verified": verified},
        )

    def _check_authorization(self, user: CurrentUser, plugin: Dict[str, Any]) -> bool:
        return plugin.get("owner_id") == user.user_id or user.has_role("admin", "moderator")
