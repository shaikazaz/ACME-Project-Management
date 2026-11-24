"""Helpers shared by the API tests."""

from app.auth.passwords import hash_password
from app.auth.permissions import Role
from app.models import User

PASSWORD = "Correct horse battery"
HASH = hash_password(PASSWORD)
ROLES = [role.value for role in Role]


def add_user(session, role, name=None, **extra):
    """Insert an account."""
    name = name or role
    user = User(
        email=f"{name}@example.com",
        full_name=name,
        password_hash=HASH,
        role=role,
        **extra,
    )
    session.add(user)
    session.flush()
    return user


def sign_in(api, user, password=PASSWORD):
    """Sign in through the API."""
    body = {"email": user.email, "password": password}
    return api.post("/auth/login", json=body)


def auth(api, user):
    """Return the headers of a signed-in user."""
    response = sign_in(api, user)
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def code(response):
    """Return the error code of a response."""
    return response.json()["error"]["code"]
