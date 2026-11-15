"""Add optional unique display names and bios without changing existing accounts."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # Add nullable columns directly: rebuilding users would conflict with item FKs.
    op.add_column("users", sa.Column(
        "display_name", sa.String(80, collation="NOCASE"),
        sa.CheckConstraint(
            "display_name IS NULL OR (length(display_name) BETWEEN 1 AND 80 "
            "AND display_name = trim(display_name))", name="display_name_length",
        ), nullable=True,
    ))
    op.add_column("users", sa.Column(
        "bio", sa.String(500),
        sa.CheckConstraint("bio IS NULL OR length(bio) <= 500", name="bio_length"),
        nullable=True,
    ))
    # Multiple NULLs are allowed; chosen names must be unique (ASCII case-insensitive).
    op.create_index("uq_users_display_name", "users", ["display_name"], unique=True)


def downgrade():
    # Reverting removes profile data, but keeps accounts and posts.
    op.drop_index("uq_users_display_name", table_name="users")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
