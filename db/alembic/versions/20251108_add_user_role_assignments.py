
"""add user role assignments table"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9c17d7f6f87b"
down_revision = "7ad4c6f40f3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_role_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("current_role", sa.Text(), nullable=False),
        sa.Column("previous_role", sa.Text(), nullable=True),
        sa.Column("assigned_by", sa.Text(), nullable=False),
        sa.Column("assigned_user_id", sa.Text(), nullable=False, index=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("user_role_assignments")

