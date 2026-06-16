"""
Wiki Database Models
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# Domain Models (Pydantic) - independent of specific ORM for now to keep architecture clean
# In a real implementation, these would map to SQLAlchemy models


class WikiPageCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9-_/]+$")
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    namespace: str = "default"
    commit_message: str = "Initial creation"


class WikiPageUpdate(BaseModel):
    content: str
    version: int = Field(..., description="Optimistic locking version")
    commit_message: str = "Update"


class WikiRevision(BaseModel):
    id: str
    page_id: str
    version: int
    content: str
    author_id: str
    created_at: datetime
    commit_message: str


class WikiPage(BaseModel):
    id: str
    slug: str
    namespace: str
    title: str
    current_revision_id: str
    version: int
    created_at: datetime
    updated_at: datetime
    locked_by: Optional[str] = None
    lock_expires_at: Optional[datetime] = None

    # Computed fields
    html_content: Optional[str] = None  # Rendered content
