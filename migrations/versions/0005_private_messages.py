"""Store private messages, optionally associated with a post."""

import sqlalchemy as sa
from alembic import op

revision = "private_messages"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.String(2000), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("sender_id <> recipient_id", name="message_distinct_users"),
        sa.CheckConstraint("length(trim(text)) BETWEEN 1 AND 2000", name="message_text_length"),
    )
    op.create_index("ix_messages_recipient_id", "messages", ["recipient_id"])


def downgrade():
    op.drop_table("messages")
