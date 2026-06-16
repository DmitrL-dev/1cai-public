"""
Webhook Handler Service
Processes GitHub webhook events
"""
from typing import Any, Dict

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.github_integration.domain.models import PullRequestEvent

logger = StructuredLogger(__name__).logger


class WebhookHandler:
    """Handles GitHub webhook events"""

    async def handle_pull_request_event(self, event_data: Dict[str, Any]) -> PullRequestEvent:
        """
        Process Pull Request webhook event

        Args:
            event_data: Raw webhook payload

        Returns:
            Validated PullRequestEvent object

        Raises:
            ValueError: If event data is invalid
        """
        # Input validation
        if not isinstance(event_data, dict):
            logger.warning(
                "Invalid event_data type",
                extra={"event_data_type": type(event_data).__name__},
            )
            raise ValueError("Invalid event data format")

        # Extract required fields
        action = event_data.get("action")
        if not action:
            raise ValueError("Missing 'action' field in event data")

        pr_data = event_data.get("pull_request", {})
        if not pr_data:
            raise ValueError("Missing 'pull_request' field in event data")

        repo_data = event_data.get("repository", {})
        if not repo_data:
            raise ValueError("Missing 'repository' field in event data")

        sender_data = event_data.get("sender", {})

        # Build PullRequestEvent (Pydantic will validate)
        try:
            pr_event = PullRequestEvent(
                action=action,
                number=pr_data.get("number"),
                repository_full_name=repo_data.get("full_name", ""),
                repository_owner=repo_data.get("owner", {}).get("login", ""),
                repository_name=repo_data.get("name", ""),
                pr_title=pr_data.get("title", ""),
                pr_body=pr_data.get("body"),
                pr_url=pr_data.get("html_url", ""),
                head_sha=pr_data.get("head", {}).get("sha", ""),
                base_ref=pr_data.get("base", {}).get("ref", ""),
                head_ref=pr_data.get("head", {}).get("ref", ""),
                sender_login=sender_data.get("login", ""),
            )

            logger.info(
                "PR event parsed successfully",
                extra={
                    "action": pr_event.action,
                    "pr_number": pr_event.number,
                    "repo": pr_event.repository_full_name,
                },
            )

            return pr_event

        except Exception as e:
            logger.error(
                f"Failed to parse PR event: {e}",
                extra={"error_type": type(e).__name__},
                exc_info=True,
            )
            raise ValueError(f"Invalid PR event data: {e}")

    def should_process_event(self, pr_event: PullRequestEvent) -> bool:
        """
        Determine if PR event should be processed

        Args:
            pr_event: Validated PR event

        Returns:
            True if event should be processed, False otherwise
        """
        # Only process these actions
        processable_actions = {"opened", "synchronize", "reopened"}

        if pr_event.action not in processable_actions:
            logger.info(
                f"Skipping PR event with action '{pr_event.action}'",
                extra={"action": pr_event.action, "pr_number": pr_event.number},
            )
            return False

        return True
