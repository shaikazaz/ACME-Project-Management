"""Treat expense category names as equal when only upper or lower case differs.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

INDEX = "uq_expense_categories_name_lower"


def upgrade() -> None:
    """Add the index. It fails without changes if such duplicates exist."""
    op.create_index(INDEX, "expense_categories", [sa.text("lower(name)")], unique=True)


def downgrade() -> None:
    """Remove the index. No data is lost."""
    op.drop_index(INDEX, table_name="expense_categories")
