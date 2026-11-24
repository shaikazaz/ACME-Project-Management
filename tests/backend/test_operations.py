"""Operator task tests."""

import json

import pytest
from sqlalchemy import select

from app import operations
from app.models import User

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


def test_http_requests_cannot_run_tasks(monkeypatch):
    import function

    monkeypatch.setattr(function, "run_task", lambda _: pytest.fail("ran a task"))
    monkeypatch.setattr(function, "http_handler", lambda *_: {"statusCode": 404})
    event = {"task": "migrate", "requestContext": {"http": {}}}
    assert function.handler(event, None) == {"statusCode": 404}
