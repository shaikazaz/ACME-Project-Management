"""Shared test setup.

Tests live outside backend/ so they are not packaged into the Lambda, and the
CI Bandit scan of backend/ does not flag their assert statements.

Database tests run in a temporary database that is created and dropped here.
They never touch the development database. They are skipped unless
POSTGRES_PASS is set.
"""

import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy.orm import Session

SERVICE_DIR = Path(__file__).resolve().parents[2] / "backend" / "project-service"
sys.path.insert(0, str(SERVICE_DIR))


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    """Give every test its own signing key."""
    monkeypatch.setenv("JWT_SECRET", uuid4().hex + uuid4().hex)


@pytest.fixture()
def client():
    """Return a test client that reports server errors as responses."""
    from app.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def migrated_engine():
    """Create a temporary database, migrate it, and drop it afterwards."""
    if not os.getenv("POSTGRES_PASS"):
        pytest.skip("POSTGRES_PASS is not set")
    from alembic import command
    from alembic.config import Config

    from app.database import get_engine

    name = f"acme_test_{uuid4().hex}"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("IS_LOCAL", "true")
        admin = psycopg.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.environ["POSTGRES_PASS"],
            dbname=os.getenv("POSTGRES_NAME", "postgres"),
            autocommit=True,
        )
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            patch.setenv("POSTGRES_NAME", name)
            get_engine.cache_clear()
            command.upgrade(Config(str(SERVICE_DIR / "alembic.ini")), "head")
            yield get_engine()
        finally:
            get_engine().dispose()
            get_engine.cache_clear()
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )
            admin.close()


@pytest.fixture()
def session(migrated_engine):
    """Return a session whose changes are always rolled back."""
    with migrated_engine.connect() as connection:
        outer = connection.begin()
        with Session(
            connection, join_transaction_mode="create_savepoint"
        ) as db_session:
            yield db_session
        outer.rollback()


@pytest.fixture()
def api(migrated_engine, session):
    """Return a client whose requests share the test's rolled-back transaction."""
    from app.database import get_session
    from app.main import create_app

    def request_session():
        with Session(
            session.connection(), join_transaction_mode="create_savepoint"
        ) as own:
            yield own

    app = create_app()
    app.dependency_overrides[get_session] = request_session
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def people(api, session):
    """Create one user per role, and return (user, headers) by role."""
    from helpers import ROLES, add_user, auth

    users = {role: add_user(session, role) for role in ROLES}
    return {role: (user, auth(api, user)) for role, user in users.items()}
