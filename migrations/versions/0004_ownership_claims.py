"""Add ownership questions and private claims, preserving existing users/posts."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("items", sa.Column("ownership_questions", sa.JSON(none_as_null=True), nullable=True))
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), sa.ForeignKey("items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimant_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ownership_answers", sa.JSON(), nullable=False),
        sa.Column("supporting_details", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')", name="claim_status"),
        sa.CheckConstraint("supporting_details IS NULL OR length(supporting_details) <= 2000",
                           name="claim_details_length"),
    )
    op.create_index("ix_claims_item_id", "claims", ["item_id"])
    op.create_index("ix_claims_claimant_id", "claims", ["claimant_id"])
    op.create_index("uq_claim_pending_user_item", "claims", ["item_id", "claimant_id"],
                    unique=True, sqlite_where=sa.text("status = 'pending'"))
    op.create_index("uq_claim_approved_item", "claims", ["item_id"],
                    unique=True, sqlite_where=sa.text("status = 'approved'"))


def downgrade():
    # This removes claim history; existing accounts and posts remain.
    op.drop_table("claims")
    op.drop_column("items", "ownership_questions")
