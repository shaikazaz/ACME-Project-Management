"""Add the setting that converts allocation percentages to hours.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Insert the setting unless it already exists."""
    op.execute(
        """
        INSERT INTO app_settings (key, value, description)
        VALUES ('full_time_hours_per_week', 40, 'Weekly hours of a 100% allocation')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    """Remove the setting. No business data is lost."""
    op.execute("DELETE FROM app_settings WHERE key = 'full_time_hours_per_week'")
