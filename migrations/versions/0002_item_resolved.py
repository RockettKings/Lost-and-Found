"""Add a resolved flag to item posts.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08

"""
import sqlalchemy as sa
from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.add_column(sa.Column(
            "resolved", sa.Boolean(), nullable=False, server_default=sa.text("0"),
        ))


def downgrade():
    with op.batch_alter_table("items") as batch_op:
        batch_op.drop_column("resolved")
