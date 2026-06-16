"""
Wiki Service - Database Models (SQLAlchemy)
Supports Versioning, Soft Deletes, Namespaces, Blueprints, and Comments
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid():
    return str(uuid.uuid4())


class WikiNamespace(Base):
    __tablename__ = "wiki_namespaces"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    path = Column(
        String, unique=True, nullable=False, index=True
    )  # e.g., "project/module"
    parent_id = Column(String, ForeignKey("wiki_namespaces.id"), nullable=True)
    is_private = Column(Boolean, default=False)

    pages = relationship("WikiPage", back_populates="namespace")
    children = relationship("WikiNamespace")


class WikiBlueprint(Base):
    """Templates for creating new pages"""

    __tablename__ = "wiki_blueprints"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    content_template = Column(Text, nullable=False)  # Markdown with placeholders
    metadata_schema = Column(JSON, nullable=True)  # JSON schema for required metadata


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id = Column(String, primary_key=True, default=generate_uuid)
    namespace_id = Column(String, ForeignKey("wiki_namespaces.id"), nullable=False)
    slug = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)

    # Versioning
    current_revision_id = Column(String, ForeignKey("wiki_revisions.id"), nullable=True)
    version = Column(Integer, default=1, nullable=False)  # Optimistic locking

    # Soft Delete
    is_deleted = Column(Boolean, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Blueprint info
    blueprint_id = Column(String, ForeignKey("wiki_blueprints.id"), nullable=True)

    namespace = relationship("WikiNamespace", back_populates="pages")
    revisions = relationship(
        "WikiRevision", foreign_keys="[WikiRevision.page_id]", back_populates="page"
    )
    current_revision = relationship(
        "WikiRevision", foreign_keys=[current_revision_id], post_update=True
    )
    comments = relationship("WikiComment", back_populates="page")

    __table_args__ = (
        UniqueConstraint("namespace_id", "slug", name="uix_namespace_slug"),
    )


class WikiRevision(Base):
    __tablename__ = "wiki_revisions"

    id = Column(String, primary_key=True, default=generate_uuid)
    page_id = Column(String, ForeignKey("wiki_pages.id"), nullable=False)
    version = Column(Integer, nullable=False)

    content = Column(Text, nullable=False)  # Markdown content
    commit_message = Column(String, nullable=True)

    author_id = Column(String, nullable=False)  # Link to User
    created_at = Column(DateTime, default=datetime.utcnow)

    page = relationship("WikiPage", foreign_keys=[page_id], back_populates="revisions")


class WikiComment(Base):
    __tablename__ = "wiki_comments"

    id = Column(String, primary_key=True, default=generate_uuid)
    page_id = Column(String, ForeignKey("wiki_pages.id"), nullable=False)
    author_id = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)
    parent_id = Column(String, ForeignKey("wiki_comments.id"), nullable=True)

    page = relationship("WikiPage", back_populates="comments")
    children = relationship("WikiComment")


class WikiAuditLog(Base):
    __tablename__ = "wiki_audit_log"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # CREATE, UPDATE, DELETE, RESTORE
    entity_type = Column(String, nullable=False)  # PAGE, NAMESPACE
    entity_id = Column(String, nullable=False)
    details = Column(Text, nullable=True)  # JSON details
    created_at = Column(DateTime, default=datetime.utcnow)
