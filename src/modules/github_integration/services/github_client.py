"""
GitHub API Client
Handles all interactions with GitHub API with retry logic and error handling
"""
import asyncio
import hashlib
import hmac
import os
from typing import Any, Dict, List, Optional

import httpx

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.github_integration.domain.models import PRFile

logger = StructuredLogger(__name__).logger


class GitHubClient:
    """GitHub API client with retry logic and error handling"""

    def __init__(
        self,
        github_token: Optional[str] = None,
        webhook_secret: Optional[str] = None,
    ):
        """
        Initialize GitHub client

        Args:
            github_token: GitHub API token (defaults to GITHUB_TOKEN env var)
            webhook_secret: Webhook secret for signature verification
        """
        self.github_token = github_token or os.getenv("GITHUB_TOKEN", "")
        self.webhook_secret = webhook_secret or os.getenv("GITHUB_WEBHOOK_SECRET", "")

        if not self.github_token:
            logger.warning("GITHUB_TOKEN not set - GitHub integration disabled")

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature

        Args:
            payload: Raw webhook payload
            signature: X-Hub-Signature-256 header value

        Returns:
            True if signature is valid, False otherwise
        """
        if not self.webhook_secret:
            logger.warning("Webhook secret not configured - skipping verification")
            return True  # Allow in development

        mac = hmac.new(self.webhook_secret.encode(),
                       msg=payload, digestmod=hashlib.sha256)
        expected_signature = "sha256=" + mac.hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    async def fetch_pr_files(self, repo_full_name: str, pr_number: int, max_retries: int = 3) -> List[PRFile]:
        """
        Fetch changed files from a Pull Request

        Args:
            repo_full_name: Repository full name (owner/repo)
            pr_number: Pull request number
            max_retries: Maximum retry attempts

        Returns:
            List of PRFile objects

        Raises:
            ValueError: If input validation fails
        """
        # Input validation
        if not repo_full_name or not isinstance(repo_full_name, str):
            raise ValueError(f"Invalid repo_full_name: {repo_full_name}")
        if not isinstance(pr_number, int) or pr_number <= 0:
            raise ValueError(f"Invalid pr_number: {pr_number}")

        # Sanitize repo name (prevent path traversal)
        repo_full_name = repo_full_name.replace("..", "").replace("//", "/")

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"

        # Fetch files with retry logic
        files_data = await self._make_request_with_retry("GET", url, headers=headers, max_retries=max_retries)

        if not files_data:
            return []

        # Convert to PRFile objects and download content for .bsl files
        pr_files = []
        for file_data in files_data:
            # Only process .bsl files
            if not file_data.get("filename", "").endswith(".bsl"):
                continue

            # Download raw content
            raw_url = file_data.get("raw_url")
            if not raw_url:
                logger.warning(
                    f"No raw_url for file {file_data.get('filename')}",
                    extra={"repo": repo_full_name, "pr_number": pr_number},
                )
                continue

            content = await self._download_file_content(raw_url, headers)
            if content is None:
                continue

            try:
                pr_file = PRFile(
                    filename=file_data.get("filename", ""),
                    status=file_data.get("status", "modified"),
                    additions=file_data.get("additions", 0),
                    deletions=file_data.get("deletions", 0),
                    changes=file_data.get("changes", 0),
                    patch=file_data.get("patch"),
                    raw_url=raw_url,
                )
                # Add content as extra attribute (not in Pydantic model)
                pr_file.content = content  # type: ignore
                pr_files.append(pr_file)
            except Exception as e:
                logger.error(
                    f"Failed to create PRFile object: {e}",
                    extra={
                        "filename": file_data.get("filename"),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )

        return pr_files

    async def post_review(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[List[Dict[str, Any]]] = None,
        max_retries: int = 3,
    ) -> bool:
        """
        Post a review to a Pull Request

        Args:
            repo_full_name: Repository full name (owner/repo)
            pr_number: Pull request number
            body: Review summary body
            event: Review event (APPROVE, REQUEST_CHANGES, COMMENT)
            comments: List of line comments
            max_retries: Maximum retry attempts

        Returns:
            True if successful, False otherwise
        """
        # Input validation
        if not repo_full_name or not isinstance(repo_full_name, str):
            logger.warning(
                "Invalid repo_full_name in post_review",
                extra={"repo_full_name_type": type(repo_full_name).__name__},
            )
            return False

        if not isinstance(pr_number, int) or pr_number <= 0:
            logger.warning(
                "Invalid pr_number in post_review",
                extra={"pr_number": pr_number},
            )
            return False

        # Sanitize repo name
        repo_full_name = repo_full_name.replace("..", "").replace("//", "/")

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"

        review_body = {
            "body": body,
            "event": event,
            "comments": comments or [],
        }

        result = await self._make_request_with_retry(
            "POST", url, headers=headers, json=review_body, max_retries=max_retries
        )

        return result is not None

    async def post_comment(
        self,
        repo: str,
        pr_number: int,
        comment: str,
        max_retries: int = 3,
    ) -> bool:
        """
        Post a single comment to a Pull Request

        Args:
            repo: Repository full name (owner/repo)
            pr_number: Pull request number
            comment: Comment body
            max_retries: Maximum retry attempts

        Returns:
            True if successful, False otherwise
        """
        # Input validation
        if not isinstance(repo, str) or not repo.strip():
            logger.warning("Invalid repo in post_comment")
            return False

        if not isinstance(pr_number, int) or pr_number <= 0:
            logger.warning("Invalid pr_number in post_comment")
            return False

        if not isinstance(comment, str) or not comment.strip():
            logger.warning("Invalid comment in post_comment")
            return False

        # Limit comment length (GitHub's limit)
        max_comment_length = 65536
        if len(comment) > max_comment_length:
            logger.warning(
                "Comment too long, truncating",
                extra={"comment_length": len(
                    comment), "max_length": max_comment_length},
            )
            comment = comment[:max_comment_length]

        # Sanitize repo name
        repo = repo.replace("..", "").replace("//", "/")

        if not self.github_token:
            logger.warning("Skip PR comment: GITHUB_TOKEN not configured")
            return False

        url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        result = await self._make_request_with_retry(
            "POST", url, headers=headers, json={"body": comment}, max_retries=max_retries
        )

        return result is not None

    async def _make_request_with_retry(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
    ) -> Optional[Any]:
        """
        Make HTTP request with exponential backoff retry logic

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers
            json: JSON body (for POST/PUT)
            max_retries: Maximum retry attempts

        Returns:
            Response JSON data or None on failure
        """
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                    response = await client.request(method, url, headers=headers, json=json)
                    response.raise_for_status()

                    if attempt > 0:
                        logger.info(
                            f"Request succeeded on attempt {attempt + 1}",
                            extra={"url": url, "method": method,
                                "attempt": attempt + 1},
                        )

                    # Return JSON for successful requests
                    if method == "GET" or response.status_code in (200, 201):
                        try:
                            return response.json()
                        except Exception:
                            return True  # Success but no JSON

                    return True

            except httpx.HTTPStatusError as exc:
                is_retryable = exc.response.status_code >= 500

                if attempt == max_retries - 1 or not is_retryable:
                    logger.error(
                        f"HTTP error: {exc.response.status_code}",
                        extra={
                            "url": url,
                            "method": method,
                            "status_code": exc.response.status_code,
                            "response_text": exc.response.text[:500],
                            "attempt": attempt + 1,
                        },
                    )
                    return None

                delay = base_delay * (2**attempt)
                logger.warning(
                    f"HTTP error, retrying in {delay}s (attempt {attempt + 1}/{max_retries})",
                    extra={
                        "url": url,
                        "method": method,
                        "status_code": exc.response.status_code,
                        "attempt": attempt + 1,
                        "delay": delay,
                    },
                )
                await asyncio.sleep(delay)

            except httpx.RequestError as exc:
                if attempt == max_retries - 1:
                    logger.error(
                        f"Request error: {exc}",
                        extra={
                            "url": url,
                            "method": method,
                            "error_type": type(exc).__name__,
                            "attempt": attempt + 1,
                        },
                        exc_info=True,
                    )
                    return None

                delay = base_delay * (2**attempt)
                logger.warning(
                    f"Request error, retrying in {delay}s: {exc}",
                    extra={
                        "url": url,
                        "method": method,
                        "error_type": type(exc).__name__,
                        "attempt": attempt + 1,
                        "delay": delay,
                    },
                )
                await asyncio.sleep(delay)

        return None

    async def _download_file_content(self, url: str, headers: Dict[str, str]) -> Optional[str]:
        """
        Download file content from URL

        Args:
            url: File URL
            headers: Request headers

        Returns:
            File content as string or None on failure
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except Exception as exc:
            logger.error(
                f"Failed to download file: {exc}",
                extra={"url": url, "error_type": type(exc).__name__},
            )
            return None
