"""Operator task tests."""

import json
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import operations
from app.auth.passwords import verify_password
from app.auth.shared import SHARED_ACCOUNTS
from app.models import Project, User

ADMIN = {
    "task": "create_admin",
    "email": "first.admin@example.com",
    "name": "First Admin",
    "password": "a long safe password",
}


@pytest.fixture()
def run(session, migrated_engine, monkeypatch):
    """Run tasks inside the test's transaction."""
    from function import handler

    monkeypatch.setattr(operations, "get_engine", session.connection)
    return lambda event: handler(event, None)


def test_migrating_again_changes_nothing(migrated_engine):
    from function import handler

    assert handler({"task": "migrate"}, None)["ok"] is True
    assert handler({"task": "migrate"}, None)["ok"] is True


def test_admin_is_created_once_with_a_hashed_password(run, session):
    assert run(ADMIN)["ok"] is True
    user = session.scalar(select(User).where(User.email == ADMIN["email"]))
    assert user.role == "admin"
    assert ADMIN["password"] not in user.password_hash
    again = run(ADMIN)
    assert again == {
        "ok": False,
        "message": "An account with this email already exists.",
    }


@pytest.mark.parametrize("change", [{"password": "short"}, {"email": "nobody"}])
def test_invalid_admins_are_refused_without_repeating_input(run, caplog, change):
    result = run({**ADMIN, **change})
    assert result["ok"] is False
    assert ADMIN["password"] not in json.dumps(result) + caplog.text
    assert "short" not in json.dumps(result) + caplog.text


def test_missing_options_and_unknown_tasks_are_refused(run):
    assert run({"task": "create_admin"})["ok"] is False
    assert run({"task": "drop"}) == {"ok": False, "message": "Unknown task."}


def test_shared_accounts_are_created_then_get_new_passwords(run, session):
    def task(password):
        passwords = dict.fromkeys(SHARED_ACCOUNTS, password)
        return run({"task": "set_shared_accounts", "passwords": passwords})

    assert task("a long first password")["ok"] is True
    query = select(User).where(User.email.in_(SHARED_ACCOUNTS))
    users = session.scalars(query).all()
    assert {user.email: (user.full_name, user.role) for user in users} == (
        SHARED_ACCOUNTS
    )
    assert task("a long second password")["ok"] is True
    session.expire_all()
    users = session.scalars(query).all()
    assert len(users) == 3
    for user in users:
        assert verify_password("a long second password", user.password_hash)
    assert task("short") == {
        "ok": False,
        "message": "A password is missing or not valid.",
    }
    assert run({"task": "set_shared_accounts"})["ok"] is False


def test_http_requests_cannot_run_tasks(monkeypatch):
    import function

    monkeypatch.setattr(function, "run_task", lambda _: pytest.fail("ran a task"))
    monkeypatch.setattr(function, "http_handler", lambda *_: {"statusCode": 404})
    event = {"task": "migrate", "requestContext": {"http": {}}}
    assert function.handler(event, None) == {"statusCode": 404}


def test_demo_data_is_added_once(session, migrated_engine, monkeypatch, people):
    from function import handler

    engine = SimpleNamespace(begin=lambda: nullcontext(session.connection()))
    monkeypatch.setattr(operations, "get_engine", lambda: engine)
    first = handler({"task": "add_demo_data"}, None)
    assert first["ok"] is True
    codes = session.scalars(select(Project.code).where(Project.code.like("DEMO-%")))
    assert len(codes.all()) == 12
    again = handler({"task": "add_demo_data"}, None)
    assert again["message"].startswith("Added 0 records")


def test_demo_data_needs_an_admin(session, migrated_engine, monkeypatch):
    from function import handler

    engine = SimpleNamespace(begin=lambda: nullcontext(session.connection()))
    monkeypatch.setattr(operations, "get_engine", lambda: engine)
    result = handler({"task": "add_demo_data"}, None)
    assert result == {"ok": False, "message": "Create an admin account first."}
