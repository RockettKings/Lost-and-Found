"""Store unread notifications for private messages and claims."""

import sqlalchemy as sa
from alembic import op

revision = "notifications"
down_revision = "private_messages"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claim_id", sa.Integer(), sa.ForeignKey("claims.id", ondelete="CASCADE")),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(type = 'message' AND message_id IS NOT NULL AND claim_id IS NULL) OR "
            "(type IN ('claim_submitted', 'claim_approved', 'claim_denied') "
            "AND claim_id IS NOT NULL AND message_id IS NULL)",
            name="notification_target",
        ),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade():
    op.drop_table("notifications")
