"""
GitHub Integration Domain Models
Pydantic models for GitHub webhook events and responses
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class PRFile(BaseModel):
    """Model for a changed file in a Pull Request"""

    filename: str = Field(..., description="File path")
    status: str = Field(..., description="File status: added, modified, removed")
    additions: int = Field(default=0, description="Number of lines added")
    deletions: int = Field(default=0, description="Number of lines deleted")
    changes: int = Field(default=0, description="Total number of changes")
    patch: Optional[str] = Field(None, description="Diff patch content")
    raw_url: Optional[str] = Field(None, description="URL to raw file content")

    @validator("filename")
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty and has reasonable length"""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        if len(v) > 500:
            raise ValueError("Filename too long (max 500 characters)")
        return v.strip()


class PullRequestEvent(BaseModel):
    """Model for GitHub Pull Request webhook event"""

    action: str = Field(...,
                        description="PR action: opened, synchronize, reopened, etc.")
    number: int = Field(..., description="Pull request number")
    repository_full_name: str = Field(...,
                                      description="Repository full name (owner/repo)")
    repository_owner: str = Field(..., description="Repository owner")
    repository_name: str = Field(..., description="Repository name")
    pr_title: str = Field(..., description="Pull request title")
    pr_body: Optional[str] = Field(None, description="Pull request description")
    pr_url: str = Field(..., description="Pull request URL")
    head_sha: str = Field(..., description="HEAD commit SHA")
    base_ref: str = Field(..., description="Base branch reference")
    head_ref: str = Field(..., description="HEAD branch reference")
    sender_login: str = Field(..., description="Event sender GitHub login")

    @validator("action")
    def validate_action(cls, v: str) -> str:
        """Validate PR action is one of the expected values"""
        valid_actions = {"opened", "synchronize", "reopened", "edited", "closed"}
        if v not in valid_actions:
            raise ValueError(f"Invalid action: {v}. Must be one of {valid_actions}")
        return v

    @validator("number")
    def validate_number(cls, v: int) -> int:
        """Validate PR number is positive"""
        if v <= 0:
            raise ValueError("PR number must be positive")
        return v

    @validator("repository_full_name")
    def validate_repo_name(cls, v: str) -> str:
        """Validate repository full name format"""
        if "/" not in v:
            raise ValueError("Repository full name must be in format 'owner/repo'")
        parts = v.split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("Invalid repository full name format")
        return v


class ReviewComment(BaseModel):
    """Model for a code review comment"""

    path: str = Field(..., description="File path")
    line: Optional[int] = Field(None, description="Line number (for line comments)")
    body: str = Field(..., description="Comment body in Markdown")
    severity: str = Field(default="info", description="Severity: error, warning, info")
    position: Optional[int] = Field(
        None, description="Position in diff (for GitHub API)")

    @validator("body")
    def validate_body(cls, v: str) -> str:
        """Validate comment body is not empty"""
        if not v or not v.strip():
            raise ValueError("Comment body cannot be empty")
        if len(v) > 65536:  # GitHub's limit
            raise ValueError("Comment body too long (max 65536 characters)")
        return v.strip()

    @validator("severity")
    def validate_severity(cls, v: str) -> str:
        """Validate severity level"""
        valid_severities = {"error", "warning", "info"}
        if v not in valid_severities:
            raise ValueError(
                f"Invalid severity: {v}. Must be one of {valid_severities}")
        return v


class ReviewResult(BaseModel):
    """Model for complete code review result"""

    event: str = Field(default="COMMENT",
                       description="Review event: APPROVE, REQUEST_CHANGES, COMMENT")
    body: str = Field(..., description="Overall review summary")
    comments: List[ReviewComment] = Field(
        default_factory=list, description="Line-by-line comments")
    files_reviewed: int = Field(default=0, description="Number of files reviewed")
    issues_found: int = Field(default=0, description="Total issues found")
    timestamp: datetime = Field(default_factory=datetime.utcnow,
                                description="Review timestamp")

    @validator("event")
    def validate_event(cls, v: str) -> str:
        """Validate review event type"""
        valid_events = {"APPROVE", "REQUEST_CHANGES", "COMMENT"}
        if v not in valid_events:
            raise ValueError(f"Invalid event: {v}. Must be one of {valid_events}")
        return v

    @validator("body")
    def validate_body(cls, v: str) -> str:
        """Validate review body is not empty"""
        if not v or not v.strip():
            raise ValueError("Review body cannot be empty")
        return v.strip()


class WebhookPayload(BaseModel):
    """Model for raw GitHub webhook payload"""

    action: str
    pull_request: Dict[str, Any]
    repository: Dict[str, Any]
    sender: Dict[str, Any]

    class Config:
        extra = "allow"  # Allow additional fields from GitHub


class GitHubAPIError(BaseModel):
    """Model for GitHub API error response"""

    message: str
    documentation_url: Optional[str] = None
    status: int = Field(default=500)
    errors: Optional[List[Dict[str, Any]]] = None
