from typing import Any, Dict, List

from src.infrastructure.logging.structured_logging import StructuredLogger
from src.modules.github_integration.services.github_client import GitHubClient

logger = StructuredLogger(__name__).logger


class ReviewService:
    """Orchestrates code review process"""

    def __init__(self, github_client: GitHubClient):
        """
        Initialize review service

        Args:
            github_client: GitHub API client
        """
        self.github_client = github_client
        self._ai_reviewer = None

    @property
    def ai_reviewer(self) -> Any:
        if self._ai_reviewer is None:
            from src.ai.agents.code_review.ai_reviewer import AICodeReviewer
            self._ai_reviewer = AICodeReviewer()
        return self._ai_reviewer

    async def review_pull_request(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """
        Review a Pull Request

        Args:
            repo_full_name: Repository full name (owner/repo)
            pr_number: Pull request number

        Returns:
            Review result dictionary
        """
        logger.info(
            "Starting PR review",
            extra={"repo": repo_full_name, "pr_number": pr_number},
        )

        # Fetch PR files
        pr_files = await self.github_client.fetch_pr_files(repo_full_name, pr_number)

        if not pr_files:
            logger.warning(
                "No .bsl files found in PR",
                extra={"repo": repo_full_name, "pr_number": pr_number},
            )
            return {
                "status": "skipped",
                "reason": "No .bsl files to review",
                "pr_number": pr_number,
            }

        # Convert PRFile objects to format expected by AI reviewer
        files_for_review = []
        for pr_file in pr_files:
            files_for_review.append(
                {
                    "filename": pr_file.filename,
                    "content": getattr(pr_file, "content", ""),
                    "status": pr_file.status,
                    "additions": pr_file.additions,
                    "deletions": pr_file.deletions,
                }
            )

        # Perform AI review
        try:
            review_result = await self.ai_reviewer.review_pull_request(files_for_review)
        except Exception as e:
            logger.error(
                f"AI review failed: {e}",
                extra={
                    "repo": repo_full_name,
                    "pr_number": pr_number,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return {
                "status": "error",
                "reason": f"AI review failed: {str(e)}",
                "pr_number": pr_number,
            }

        # Post review to GitHub
        if self.github_client.github_token:
            await self._post_review_to_github(repo_full_name, pr_number, review_result)

        return {
            "status": "success",
            "pr_number": pr_number,
            "review_status": review_result.get("overall_status"),
            "issues_found": review_result.get("metrics", {}).get("total_issues", 0),
        }

    async def review_code(self, code: str, filename: str) -> Dict[str, Any]:
        """
        Review a single code snippet (for manual/testing purposes)

        Args:
            code: Code content
            filename: File name

        Returns:
            Review result dictionary
        """
        logger.info(
            "Starting manual code review",
            extra={"filename": filename, "code_length": len(code)},
        )

        try:
            review_result = await self.ai_reviewer.review_code(code, filename)
            return review_result
        except Exception as e:
            logger.error(
                f"Manual review failed: {e}",
                extra={"filename": filename, "error_type": type(e).__name__},
                exc_info=True,
            )
            raise

    async def _post_review_to_github(self, repo_full_name: str, pr_number: int, review_result: Dict[str, Any]) -> None:
        """
        Post review to GitHub

        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            review_result: AI review result
        """
        # Format comments for GitHub
        comments = self._format_comments_for_github(
            review_result.get("file_reviews", []))

        # Determine review event type
        overall_status = review_result.get("overall_status", "COMMENTED")
        event_mapping = {
            "APPROVED": "APPROVE",
            "CHANGES_REQUESTED": "REQUEST_CHANGES",
            "COMMENTED": "COMMENT",
        }
        event = event_mapping.get(overall_status, "COMMENT")

        # Post review
        success = await self.github_client.post_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            body=review_result.get("summary", "Code review completed"),
            event=event,
            comments=comments,
        )

        if success:
            logger.info(
                "Review posted successfully",
                extra={"repo": repo_full_name, "pr_number": pr_number},
            )
        else:
            logger.error(
                "Failed to post review",
                extra={"repo": repo_full_name, "pr_number": pr_number},
            )

    def _format_comments_for_github(self, file_reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format review comments for GitHub API

        Args:
            file_reviews: List of file review results

        Returns:
            List of formatted comments
        """
        comments = []

        for file_review in file_reviews:
            filename = file_review.get("filename", "")

            # Collect all issues
            all_issues = []
            for category in ["security", "performance", "best_practices"]:
                all_issues.extend(file_review.get("issues", {}).get(category, []))

            # Format each issue as a comment
            for issue in all_issues:
                comment_body = self._format_issue_comment(issue)

                comments.append(
                    {
                        "path": filename,
                        "line": issue.get("line", 1),
                        "body": comment_body,
                    }
                )

        return comments

    def _format_issue_comment(self, issue: Dict[str, Any]) -> str:
        """
        Format a single issue as a Markdown comment

        Args:
            issue: Issue dictionary

        Returns:
            Formatted Markdown comment
        """
        severity_emoji = {
            "CRITICAL": "🔴",
            "HIGH": "🟠",
            "MEDIUM": "🟡",
            "LOW": "🟢",
        }

        emoji = severity_emoji.get(issue.get("severity", "LOW"), "🔵")

        comment = f"{emoji} **{issue.get('type', 'Issue')}** ({issue.get('severity', 'LOW')})\n\n"
        comment += f"{issue.get('message', '')}\n"

        if issue.get("description"):
            comment += f"\n**Почему это проблема:**\n{issue['description']}\n"

        if issue.get("recommendation"):
            comment += f"\n**Рекомендация:**\n{issue['recommendation']}\n"

        if issue.get("performance_impact"):
            comment += f"\n**Performance Impact:** {issue['performance_impact']}\n"

        if issue.get("cwe_id"):
            comment += f"\n**CWE:** {issue['cwe_id']}\n"

        if issue.get("standard"):
            comment += f"\n📚 **Стандарт:** {issue['standard']}\n"

        return comment
