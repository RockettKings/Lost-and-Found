"""Add an admin flag to users.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10

"""
import sqlalchemy as sa
from alembic import op


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN, not batch mode: batch mode rebuilds the users table, which
    # SQLite refuses while items rows reference users through the foreign key.
    op.add_column("users", sa.Column(
        "is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0"),
    ))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_admin")
