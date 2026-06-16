
"""create security audit table"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "7ad4c6f40f3b"
down_revision = "5e6cbcc5f1d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_index("ix_security_audit_actor", "security_audit_log", ["actor"])
    op.create_index("ix_security_audit_action", "security_audit_log", ["action"])
    op.create_index("ix_security_audit_timestamp", "security_audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_timestamp", table_name="security_audit_log")
    op.drop_index("ix_security_audit_action", table_name="security_audit_log")
    op.drop_index("ix_security_audit_actor", table_name="security_audit_log")
    op.drop_table("security_audit_log")

