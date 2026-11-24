"""Tests for the health endpoints, shared error format and Lambda routing."""

import json
import os

import pytest
from sqlalchemy.exc import OperationalError

from app import database
from app.config import load_database_settings
from app.database import get_session


def lambda_event(path):
    """Build a Lambda Function URL event (payload format 2.0)."""
    return {
        "version": "2.0",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.test"},
        "requestContext": {
            "http": {"method": "GET", "path": path, "sourceIp": "127.0.0.1"}
        },
        "isBase64Encoded": False,
    }


class FakeSession:
    """Session stand-in that succeeds or raises."""

    def __init__(self, error=None):
        self.error = error

    def execute(self, _):
        if self.error:
            raise self.error


def test_live_does_not_need_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "project-service"}


def test_ready_when_database_responds(client):
    client.app.dependency_overrides[get_session] = lambda: FakeSession()
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"


def test_ready_hides_connection_details_when_database_is_down(client):
    error = OperationalError("SELECT 1", {}, Exception("host=secret-host"))
    client.app.dependency_overrides[get_session] = lambda: FakeSession(error)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    assert "secret-host" not in response.text


def test_unexpected_error_is_generic(client):
    client.app.dependency_overrides[get_session] = lambda: FakeSession(
        RuntimeError("internal detail")
    )
    response = client.get("/health/ready")
    assert response.status_code == 500
    assert "internal detail" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "status", "code"),
    [
        ("get", "/nope", 404, "not_found"),
        ("post", "/health", 405, "method_not_allowed"),
        ("get", "/docs", 404, "not_found"),
        ("get", "/openapi.json", 404, "not_found"),
    ],
)
def test_errors_share_one_format(client, method, path, status, code):
    response = client.request(method, path)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_invalid_input_returns_400_without_echoing_values(client):
    @client.app.get("/validate")
    def validate(number: int):
        return number

    response = client.get("/validate", params={"number": "my-secret"})
    assert response.status_code == 400
    assert response.json()["error"]["details"][0]["field"] == "query.number"
    assert "my-secret" not in response.text


@pytest.mark.parametrize("path", ["/health", "/api/project-service/health"])
def test_lambda_routes_with_and_without_prefix(path):
    from function import handler

    response = handler(lambda_event(path), None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["status"] == "ok"


@pytest.mark.parametrize(
    ("is_local", "require_ssl"), [("true", False), ("false", True), (None, True)]
)
def test_ssl_is_required_unless_local(monkeypatch, is_local, require_ssl):
    monkeypatch.delenv("IS_LOCAL", raising=False)
    if is_local is not None:
        monkeypatch.setenv("IS_LOCAL", is_local)
    assert load_database_settings().require_ssl is require_ssl


def test_password_is_not_in_settings_repr(monkeypatch):
    monkeypatch.setenv("POSTGRES_PASS", "hidden-value")
    assert "hidden-value" not in repr(load_database_settings())


@pytest.mark.skipif(not os.getenv("POSTGRES_PASS"), reason="POSTGRES_PASS is not set")
def test_ready_against_real_postgres(client, monkeypatch):
    monkeypatch.setenv("IS_LOCAL", "true")
    database.get_engine.cache_clear()
    response = client.get("/health/ready")
    database.get_engine().dispose()
    database.get_engine.cache_clear()
    assert response.status_code == 200
