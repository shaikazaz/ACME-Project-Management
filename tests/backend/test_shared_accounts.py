"""Tests of the shared demo accounts' limits."""

import pytest
from helpers import HASH, PASSWORD, add_user, auth, code, sign_in
from sqlalchemy import select

from app.auth.shared import HIDDEN_EMAIL, READ_METHODS, SHARED_ACCOUNTS
from app.models import Department, Resource, User

LIMITED = "demo_account_limited"


@pytest.fixture()
def shared(api, session):
    """Create the shared accounts and return (user, headers) by role."""
    people = {}
    for email, (name, role) in SHARED_ACCOUNTS.items():
        user = User(email=email, full_name=name, role=role, password_hash=HASH)
        session.add(user)
        session.flush()
        people[role] = (user, auth(api, user))
    return people


def protected_changes():
    """Return every request, except sign-out and edits of project work."""
    from app.main import PROTECTED_ROUTERS

    work = ("/projects", "/deliverables/", "/expenses/")
    for router in PROTECTED_ROUTERS:
        for route in router.routes:
            for method in set(route.methods) - set(READ_METHODS):
                edits_work = method != "DELETE" and route.path.startswith(work)
                if not edits_work and route.path != "/auth/logout":
                    yield method, route.path


@pytest.mark.parametrize(("method", "path"), sorted(protected_changes()))
def test_protected_changes_are_refused(api, shared, method, path):
    headers = shared["admin"][1]
    url = path
    for name in ("deliverable", "project", "user", "resource", "department"):
        url = url.replace(f"{{{name}_id}}", "1")
    while "{" in url:
        url = url[: url.index("{")] + "1" + url[url.index("}") + 1 :]
    response = api.request(method, url, headers=headers, json={})
    # 400 and 404 mean the request was already refused before the limit.
    assert response.status_code in (400, 403, 404)
    assert response.status_code != 403 or code(response) == LIMITED


def test_protected_changes_cover_every_router():
    paths = {path for _, path in protected_changes()}
    assert {"/users", "/settings/{key}", "/departments", "/resources"} <= paths
    assert "/auth/change-password" in paths
    assert "/expense-categories" in paths


def test_passwords_and_accounts_are_refused_with_valid_input(api, shared, session):
    user, headers = shared["admin"]
    body = {"current_password": PASSWORD, "new_password": "another long password"}
    response = api.post("/auth/change-password", headers=headers, json=body)
    assert code(response) == LIMITED
    other = add_user(session, "admin", "owner")
    for method, url, json in (
        ("POST", f"/users/{other.id}/reset-password", {"new_password": "x" * 14}),
        ("DELETE", f"/users/{other.id}", None),
        (
            "POST",
            "/users",
            {
                "email": "new@acme.test",
                "full_name": "New",
                "role": "admin",
                "password": "another long password",
            },
        ),
        ("POST", "/departments", {"name": "New department"}),
    ):
        response = api.request(method, url, headers=headers, json=json)
        assert (response.status_code, code(response)) == (403, LIMITED), url
    assert sign_in(api, user).status_code == 200
    assert not session.scalar(select(User.id).where(User.email == "new@acme.test"))


def test_project_work_can_be_added_and_edited_but_not_deleted(api, shared, session):
    manager, _ = shared["project_manager"]
    headers = shared["admin"][1]
    department = Department(name="Demo department")
    session.add(department)
    session.flush()
    body = {
        "code": "SHARED-1",
        "name": "Shared project",
        "description": "",
        "department_id": department.id,
        "manager_id": manager.id,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "status": "Active",
        "priority": "High",
        "planned_budget": "1000",
    }
    created = api.post("/projects", headers=headers, json=body)
    assert created.status_code == 201, created.text
    url = f"/projects/{created.json()['id']}"
    edited = api.put(url, headers=headers, json={**body, "name": "Edited"})
    assert edited.status_code == 200, edited.text
    assert code(api.delete(url, headers=headers)) == LIMITED
    assert api.get(url, headers=headers).status_code == 200


def test_roles_still_apply(api, shared):
    headers = shared["team_member"][1]
    assert api.get("/users", headers=headers).status_code == 403
    assert code(api.post("/projects", headers=headers, json={})) != LIMITED


def test_signing_out_keeps_other_visitors_signed_in(api, shared):
    _, headers = shared["admin"]
    assert api.post("/auth/logout", headers=headers).status_code == 204
    assert api.get("/auth/me", headers=headers).status_code == 200


def test_wrong_passwords_do_not_lock_visitors_out(api, shared):
    user, _ = shared["admin"]
    for _ in range(7):
        assert sign_in(api, user, "wrong password 1").status_code == 401
    assert sign_in(api, user).status_code == 200


def test_real_emails_are_hidden(api, shared, session):
    headers = shared["admin"][1]
    real = add_user(session, "admin", "real.person")
    department = Department(name="Demo department")
    session.add(department)
    session.flush()
    for name, email in (("Real", "real@example.com"), ("Fake", "fake@acme.test")):
        session.add(
            Resource(
                employee_code=name,
                full_name=name,
                email=email,
                department_id=department.id,
                job_title="Analyst",
            )
        )
    session.flush()
    users = api.get("/users", headers=headers).json()
    assert {item["email"] for item in users["items"]} == set(SHARED_ACCOUNTS)
    assert api.get("/users?search=real", headers=headers).json()["total"] == 0
    assert api.get(f"/users/{real.id}", headers=headers).status_code == 404
    items = api.get("/resources", headers=headers).json()["items"]
    emails = {item["full_name"]: item["email"] for item in items}
    assert emails == {"Real": HIDDEN_EMAIL, "Fake": "fake@acme.test"}
    found = api.get("/resources?search=example.com", headers=headers).json()
    assert found["total"] == 0
    assert api.get("/resources/options", headers=headers).json()["users"] == []


def test_other_accounts_are_not_limited(api, people):
    headers = people["admin"][1]
    body = {"name": "New department"}
    response = api.post("/departments", headers=headers, json=body)
    assert response.status_code == 201
    emails = [
        item["email"] for item in api.get("/users", headers=headers).json()["items"]
    ]
    assert "admin@example.com" in emails
