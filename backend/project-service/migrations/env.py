"""Alembic environment: runs migrations with the service's own connection."""

from alembic import context
from sqlalchemy import text

from app.database import get_engine
from app.models import Base

# Any fixed number: makes concurrent migration runs wait for each other.
MIGRATION_LOCK_ID = 728401


def run_migrations() -> None:
    """Apply migrations in one transaction, so a failure changes nothing."""
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:id)"), {"id": MIGRATION_LOCK_ID}
            )
            context.run_migrations()


run_migrations()
