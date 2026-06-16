
"""create marketplace tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "3b54f8ac9d66"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_plugins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plugin_id", sa.Text(), nullable=False, unique=True),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("owner_username", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("visibility", sa.Text(), nullable=False, server_default=sa.text("'public'")),
        sa.Column("homepage", sa.Text()),
        sa.Column("repository", sa.Text()),
        sa.Column("download_url", sa.Text()),
        sa.Column("icon_url", sa.Text()),
        sa.Column("changelog", sa.Text()),
        sa.Column("readme", sa.Text()),
        sa.Column("artifact_path", sa.Text()),
        sa.Column("screenshot_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("license", sa.Text()),
        sa.Column("min_version", sa.Text()),
        sa.Column("supported_platforms", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rating", sa.Numeric(), nullable=False, server_default=sa.text("0")),
        sa.Column("ratings_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("downloads", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("installs", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "marketplace_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.Text(), nullable=False, unique=True),
        sa.Column("plugin_id", sa.Text(), sa.ForeignKey("marketplace_plugins.plugin_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("user_name", sa.Text()),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("pros", sa.Text()),
        sa.Column("cons", sa.Text()),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "marketplace_installs",
        sa.Column("plugin_id", sa.Text(), sa.ForeignKey("marketplace_plugins.plugin_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("plugin_id", "user_id"),
    )

    op.create_table(
        "marketplace_favorites",
        sa.Column("plugin_id", sa.Text(), sa.ForeignKey("marketplace_plugins.plugin_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("plugin_id", "user_id"),
    )

    op.create_table(
        "marketplace_complaints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("complaint_id", sa.Text(), nullable=False, unique=True),
        sa.Column("plugin_id", sa.Text(), sa.ForeignKey("marketplace_plugins.plugin_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_marketplace_plugins_owner", "marketplace_plugins", ["owner_id"])
    op.create_index("ix_marketplace_plugins_status", "marketplace_plugins", ["status"])
    op.create_index("ix_marketplace_reviews_plugin", "marketplace_reviews", ["plugin_id"])
    op.create_index("ix_marketplace_complaints_plugin", "marketplace_complaints", ["plugin_id"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_complaints_plugin", table_name="marketplace_complaints")
    op.drop_index("ix_marketplace_reviews_plugin", table_name="marketplace_reviews")
    op.drop_index("ix_marketplace_plugins_status", table_name="marketplace_plugins")
    op.drop_index("ix_marketplace_plugins_owner", table_name="marketplace_plugins")
    op.drop_table("marketplace_complaints")
    op.drop_table("marketplace_favorites")
    op.drop_table("marketplace_installs")
    op.drop_table("marketplace_reviews")
    op.drop_table("marketplace_plugins")

