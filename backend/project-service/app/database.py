"""PostgreSQL engine and session management."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import load_database_settings

# Aurora can pause when idle and needs several seconds to resume.
CONNECT_TIMEOUT_SECONDS = 20


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared engine, created once per Lambda container.

    Returns:
        A pooled SQLAlchemy engine. One Lambda container handles one request at
        a time, so one connection is enough.
    """
    settings = load_database_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.user,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.name,
    )
    return create_engine(
        url,
        pool_size=1,
        max_overflow=1,
        pool_pre_ping=True,
        hide_parameters=True,  # Keep personal data and hashes out of logs
        connect_args={
            "connect_timeout": CONNECT_TIMEOUT_SECONDS,
            "sslmode": "require" if settings.require_ssl else "prefer",
        },
    )


def get_session() -> Iterator[Session]:
    """Provide a database session for one request (FastAPI dependency).

    Yields:
        A session that is rolled back on error and always closed.
    """
    with Session(get_engine()) as session:
        yield session


def ping(session: Session) -> None:
    """Run a trivial query to prove the database is reachable.

    Args:
        session: The session to check.
    """
    session.execute(text("SELECT 1"))
