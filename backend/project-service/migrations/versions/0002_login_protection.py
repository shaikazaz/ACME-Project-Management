"""Add columns that limit repeated failed sign-ins.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the columns. Existing accounts keep their data."""
    op.add_column(
        "users",
        sa.Column(
            "failed_login_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove the columns. Only temporary lock information is lost."""
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
