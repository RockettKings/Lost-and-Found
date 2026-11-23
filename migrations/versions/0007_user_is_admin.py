"""Add an admin flag to users.

Revision ID: 0007
Revises: notifications
Create Date: 2026-11-10

"""
import sqlalchemy as sa
from alembic import op


revision = "0007"
down_revision = "notifications"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN, not batch mode: batch mode rebuilds the users table, which
    # SQLite refuses while items rows reference users through the foreign key.
    op.add_column("users", sa.Column(
        "is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0"),
    ))


def downgrade():
    # Plain DROP COLUMN for the same reason as upgrade: a batch rebuild fails once
    # items reference users.
    op.drop_column("users", "is_admin")
