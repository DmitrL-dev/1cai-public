
"""add user roles and permissions tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5e6cbcc5f1d9"
down_revision = "3b54f8ac9d66"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text(), nullable=False, index=True),
        sa.Column("role", sa.Text(), nullable=False, index=True),
        sa.Column("assigned_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "role", name="uq_user_roles_user_role"),
    )

    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text(), nullable=False, index=True),
        sa.Column("permission", sa.Text(), nullable=False, index=True),
        sa.Column("assigned_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "permission", name="uq_user_permissions_user_permission"),
    )


def downgrade() -> None:
    op.drop_table("user_permissions")
    op.drop_table("user_roles")

