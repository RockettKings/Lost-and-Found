"""Add unique usernames.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-10

"""
import sqlalchemy as sa
from alembic import op


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _backfill_usernames(connection):
    """Name existing accounts user<id>. Usernames are public, so they must not be
    derived from the private email address. Ids are unique, so these names are too,
    and sign-up reserves the user<number> pattern so nobody can claim one."""
    connection.execute(sa.text("UPDATE users SET username = 'user' || id"))


def upgrade():
    # Plain ADD COLUMN: batch mode would rebuild users, which SQLite refuses while
    # items reference it. The app requires a username for every new account.
    op.add_column("users", sa.Column("username", sa.String(20), nullable=True))
    _backfill_usernames(op.get_bind())
    # Unique on lower(username) so "Nick" and "nick" cannot both exist.
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)


def downgrade():
    op.drop_index("uq_users_username_lower", table_name="users")
    op.drop_column("users", "username")
