"""Authentication and role tests, run through the real HTTP routes."""

import re
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

import jwt
import pytest
from fastapi import Depends
from helpers import HASH, PASSWORD, add_user, auth, code, sign_in
from pydantic import ValidationError
from sqlalchemy import select, update

from app.auth import tokens
from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.passwords import hash_password, verify_password
from app.auth.permissions import ROLE_PERMISSIONS, Permission, Role
from app.auth.scopes import (
    find_updatable_deliverable,
    find_visible_project,
    managed_project,
    visible_deliverables,
    visible_projects,
)
from app.auth.service import MAX_FAILED_LOGINS, ensure_another_admin
from app.cli import create_admin
from app.config import load_jwt_secret
from app.errors import ApiError
from app.models import (
    Deliverable,
    Department,
    Project,
    ProjectAssignment,
    Resource,
    User,
)
from app.schemas.users import UserCreate

START, END = date(2026, 1, 1), date(2026, 6, 30)


# --- Passwords -------------------------------------------------------------


def test_password_hashing():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second  # Different salts
    assert PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password(PASSWORD + " ", first)


@pytest.mark.parametrize("stored", ["", "plain", "scrypt$1$2", "md5$1$1$1$a$b"])
def test_malformed_hash_never_matches(stored):
    assert not verify_password(PASSWORD, stored)


@pytest.mark.parametrize("password", ["short", "a" * 12, "a" * 129, ""])
def test_weak_passwords_are_rejected(password):
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.co", full_name="A", role="admin", password=password)


# --- Login, logout and tokens ----------------------------------------------


def test_login_returns_user_without_hash(api, session):
    response = sign_in(api, add_user(session, "project_manager"))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "budgets:manage" in response.json()["user"]["permissions"]
    assert "password" not in response.text
    assert HASH not in response.text


def test_email_is_not_case_sensitive(api, session):
    add_user(session, "admin", "boss")
    body = {"email": "  BOSS@Example.com ", "password": PASSWORD}
    assert api.post("/auth/login", json=body).status_code == 200


def test_login_failures_look_identical(api, session):
    add_user(session, "admin", "real")
    add_user(session, "admin", "off", is_active=False)
    answers = [
        api.post("/auth/login", json={"email": f"{name}@example.com", "password": pw})
        for name, pw in (("real", "wrong"), ("off", PASSWORD), ("ghost", "wrong"))
    ]
    assert {answer.status_code for answer in answers} == {401}
    assert len({answer.text for answer in answers}) == 1


def test_repeated_failures_lock_the_account(api, session):
    user = add_user(session, "admin")
    for _ in range(MAX_FAILED_LOGINS):
        assert sign_in(api, user, "wrong").status_code == 401
    assert sign_in(api, user).status_code == 401  # Correct, but locked
    session.execute(
        update(User).values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
    )
    assert sign_in(api, user).status_code == 200


def test_success_resets_failure_count(api, session):
    user = add_user(session, "admin")
    for _ in range(MAX_FAILED_LOGINS - 1):
        sign_in(api, user, "wrong")
    assert sign_in(api, user).status_code == 200
    assert sign_in(api, user, "wrong").status_code == 401
    assert sign_in(api, user).status_code == 200


def test_logout_revokes_access_and_refresh_tokens(api, session):
    login = sign_in(api, add_user(session, "admin")).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    assert api.get("/auth/me", headers=headers).status_code == 200
    assert api.post("/auth/logout", headers=headers).status_code == 204
    assert code(api.get("/auth/me", headers=headers)) == "invalid_token"
    body = {"refresh_token": login["refresh_token"]}
    assert api.post("/auth/refresh", json=body).status_code == 401


def test_refresh_gives_a_working_access_token(api, session):
    login = sign_in(api, add_user(session, "admin")).json()
    body = {"refresh_token": login["refresh_token"]}
    token = api.post("/auth/refresh", json=body).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert api.get("/auth/me", headers=headers).status_code == 200


def test_token_types_cannot_be_swapped(api, session):
    login = sign_in(api, add_user(session, "admin")).json()
    headers = {"Authorization": f"Bearer {login['refresh_token']}"}
    assert api.get("/auth/me", headers=headers).status_code == 401
    body = {"refresh_token": login["access_token"]}
    assert api.post("/auth/refresh", json=body).status_code == 401


def test_expired_token_has_its_own_code(api, session, monkeypatch):
    user = add_user(session, "admin")
    monkeypatch.setitem(tokens.LIFETIMES, "access", timedelta(seconds=-1))
    token = tokens.create_token(user.id, 0, "access")
    response = api.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, code(response)) == (401, "token_expired")


def forge(user, key=None, algorithm="HS256", **changes):
    """Build a token, optionally signed or filled in wrongly."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(user.id),
        "ver": 0,
        "use": "access",
        "iss": "project-service",
        "aud": "project-service",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        **changes,
    }
    claims = {name: value for name, value in claims.items() if value is not None}
    key = load_jwt_secret() if key is None else key
    return jwt.encode(claims, key, algorithm=algorithm)


@pytest.mark.parametrize(
    "changes",
    [
        {"key": "x" * 40},
        {"key": "", "algorithm": "none"},
        {"iss": "other"},
        {"aud": "other"},
        {"ver": 99},
        {"ver": "abc"},
        {"sub": "999999"},
        {"sub": "abc"},
        {"exp": None},
        {"use": None},
        {"ver": None},
    ],
)
def test_forged_tokens_are_rejected(api, session, changes):
    user = add_user(session, "admin")
    good = {"Authorization": f"Bearer {forge(user)}"}
    assert api.get("/auth/me", headers=good).status_code == 200
    bad = {"Authorization": f"Bearer {forge(user, **changes)}"}
    assert api.get("/auth/me", headers=bad).status_code == 401


@pytest.mark.parametrize("header", ["", "Bearer", "Bearer x.y.z", "Basic YTpi"])
def test_malformed_headers_are_rejected(api, header):
    response = api.get("/auth/me", headers={"Authorization": header})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("secret", [None, "", "too-short"])
def test_missing_signing_key_stops_login(api, session, monkeypatch, secret):
    user = add_user(session, "admin")
    if secret is None:
        monkeypatch.delenv("JWT_SECRET")
    else:
        monkeypatch.setenv("JWT_SECRET", secret)
    response = sign_in(api, user)
    assert response.status_code == 500
    assert "JWT_SECRET" not in response.text


def test_change_password(api, session):
    user = add_user(session, "team_member")
    headers = auth(api, user)
    body = {"current_password": "wrong", "new_password": "Another good phrase"}
    url = "/auth/change-password"
    assert api.post(url, json=body, headers=headers).status_code == 400
    body["current_password"] = PASSWORD
    response = api.post(url, json=body, headers=headers)
    assert response.status_code == 200
    assert api.get("/auth/me", headers=headers).status_code == 401  # Old token
    new = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert api.get("/auth/me", headers=new).status_code == 200
    assert sign_in(api, user).status_code == 401
    assert sign_in(api, user, "Another good phrase").status_code == 200


# --- Every endpoint is protected -------------------------------------------

PUBLIC = {
    ("get", "/health"),
    ("get", "/health/ready"),
    ("post", "/auth/login"),
    ("post", "/auth/refresh"),
}


def all_endpoints(app):
    """List every (method, path) the application serves."""
    return {
        (method, path)
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    }


def test_every_endpoint_except_public_ones_requires_sign_in(api):
    endpoints = all_endpoints(api.app)
    assert PUBLIC < endpoints
    for method, path in sorted(endpoints - PUBLIC):
        url = re.sub(r"\{\w+_id\}", "1", path)
        response = api.request(method, url.replace("{key}", "x"))
        assert response.status_code == 401, (method, path)


# --- Role by endpoint ------------------------------------------------------

USER_BODY = {
    "email": "new@example.com",
    "full_name": "New",
    "role": "team_member",
    "password": "A perfectly fine one",
}
UPDATE_BODY = {name: USER_BODY[name] for name in ("email", "full_name", "role")}
DEPARTMENT_BODY = {"name": "New department"}

# (method, path, body, status for admin, manager and member)
MATRIX = [
    ("get", "/auth/me", None, 200, 200, 200),
    ("get", "/users", None, 200, 403, 403),
    ("post", "/users", USER_BODY, 201, 403, 403),
    ("get", "/users/{other}", None, 200, 403, 403),
    ("put", "/users/{other}", UPDATE_BODY, 200, 403, 403),
    (
        "post",
        "/users/{other}/reset-password",
        {"new_password": "A perfectly fine one"},
        204,
        403,
        403,
    ),
    ("delete", "/users/{other}", None, 204, 403, 403),
    ("get", "/departments", None, 200, 200, 200),
    ("get", "/departments/{department}", None, 200, 200, 200),
    ("post", "/departments", DEPARTMENT_BODY, 201, 403, 403),
    ("put", "/departments/{department}", DEPARTMENT_BODY, 200, 403, 403),
    ("delete", "/departments/{department}", None, 204, 403, 403),
    ("get", "/settings", None, 200, 403, 403),
    ("put", "/settings/budget_warning_percent", {"value": 70}, 200, 403, 403),
    ("post", "/auth/logout", None, 204, 204, 204),
]
CASES = [
    (role, method, path, body, status)
    for method, path, body, *statuses in MATRIX
    for role, status in zip(
        ("admin", "project_manager", "team_member"), statuses, strict=True
    )
]


@pytest.mark.parametrize(("role", "method", "path", "body", "status"), CASES)
def test_role_matrix(api, session, people, role, method, path, body, status):
    other = add_user(session, "team_member", "other")
    department = Department(name="Existing")
    session.add(department)
    session.flush()
    url = path.format(other=other.id, department=department.id)
    response = api.request(method, url, json=body, headers=people[role][1])
    assert response.status_code == status, response.text
    if status == 403:
        assert code(response) == "access_denied"


def test_denied_calls_change_nothing(api, session, people):
    other = add_user(session, "team_member", "other")
    for role in ("project_manager", "team_member"):
        headers = people[role][1]
        api.delete(f"/users/{other.id}", headers=headers)
        api.put(
            f"/users/{other.id}", json={**UPDATE_BODY, "role": "admin"}, headers=headers
        )
        api.post("/departments", json=DEPARTMENT_BODY, headers=headers)
    session.expire_all()
    assert session.get(User, other.id).role == "team_member"
    assert session.scalars(select(Department)).all() == []


def test_access_is_checked_before_the_body(api, people):
    response = api.post("/users", json={"bad": 1}, headers=people["team_member"][1])
    assert response.status_code == 403


def test_users_cannot_promote_themselves(api, session, people):
    user, headers = people["team_member"]
    body = {**UPDATE_BODY, "role": "admin"}
    url = f"/users/{user.id}"
    assert api.put(url, json=body, headers=headers).status_code == 403
    session.expire_all()
    assert session.get(User, user.id).role == "team_member"


# --- User administration rules ---------------------------------------------


def test_role_change_takes_effect_immediately(api, people):
    admin_headers = people["admin"][1]
    user, headers = people["project_manager"]
    body = {"email": user.email, "full_name": "P", "role": "team_member"}
    url = f"/users/{user.id}"
    assert api.put(url, json=body, headers=admin_headers).status_code == 200
    assert api.get("/auth/me", headers=headers).status_code == 401


def test_deactivated_and_deleted_users_lose_access(api, people):
    admin_headers = people["admin"][1]
    user, headers = people["team_member"]
    body = {
        "email": user.email,
        "full_name": "T",
        "role": "team_member",
        "is_active": False,
    }
    api.put(f"/users/{user.id}", json=body, headers=admin_headers)
    assert api.get("/auth/me", headers=headers).status_code == 401
    manager, manager_headers = people["project_manager"]
    api.delete(f"/users/{manager.id}", headers=admin_headers)
    assert api.get("/auth/me", headers=manager_headers).status_code == 401


def test_inactive_account_is_refused_even_with_a_current_token(api, session, people):
    user, headers = people["team_member"]
    session.execute(update(User).where(User.id == user.id).values(is_active=False))
    assert api.get("/auth/me", headers=headers).status_code == 401


def test_password_reset_signs_the_user_out(api, people):
    user, headers = people["team_member"]
    body = {"new_password": "Reset by the admin"}
    url = f"/users/{user.id}/reset-password"
    assert api.post(url, json=body, headers=people["admin"][1]).status_code == 204
    assert api.get("/auth/me", headers=headers).status_code == 401
    assert sign_in(api, user, "Reset by the admin").status_code == 200


def test_admin_cannot_lock_themselves_out(api, people):
    admin, headers = people["admin"]
    url = f"/users/{admin.id}"
    body = {"email": admin.email, "full_name": "A", "role": "team_member"}
    assert api.put(url, json=body, headers=headers).status_code == 409
    body = {**body, "role": "admin", "is_active": False}
    assert api.put(url, json=body, headers=headers).status_code == 409
    assert api.delete(url, headers=headers).status_code == 409


def test_admin_cannot_demote_themselves_when_others_exist(api, session, people):
    add_user(session, "admin", "second")
    admin, headers = people["admin"]
    body = {"email": admin.email, "full_name": "A", "role": "team_member"}
    url = f"/users/{admin.id}"
    assert api.put(url, json=body, headers=headers).status_code == 409
    assert api.delete(url, headers=headers).status_code == 409


def test_last_admin_is_protected(session):
    only = add_user(session, "admin")
    with pytest.raises(ApiError):
        ensure_another_admin(session, only)
    add_user(session, "admin", "inactive", is_active=False)
    with pytest.raises(ApiError):
        ensure_another_admin(session, only)
    add_user(session, "admin", "second")
    ensure_another_admin(session, only)


def test_conflicts_are_explained(api, session, people):
    admin, headers = people["admin"]
    duplicate = {**USER_BODY, "email": admin.email.upper()}
    response = api.post("/users", json=duplicate, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["error"]["message"]

    manager = people["project_manager"][0]
    department = Department(name="Used")
    session.add(department)
    session.flush()
    session.add(
        Project(
            code="P",
            name="P",
            department_id=department.id,
            manager_id=manager.id,
            start_date=START,
            end_date=END,
        )
    )
    session.flush()
    for url in (f"/users/{manager.id}", f"/departments/{department.id}"):
        response = api.delete(url, headers=headers)
        assert (response.status_code, code(response)) == (409, "conflict")


@pytest.mark.parametrize(
    "changes",
    [
        {"email": "not-an-email"},
        {"full_name": "   "},
        {"role": "superuser"},
        {"password": "short"},
        {"password_hash": "injected"},
        {"token_version": 5},
        {"full_name": "nul\x00byte"},
    ],
)
def test_invalid_user_input(api, people, changes):
    body = {**USER_BODY, **changes}
    response = api.post("/users", json=body, headers=people["admin"][1])
    assert response.status_code == 400
    assert "injected" not in response.text


def test_user_search_and_filter(api, session, people):
    headers = people["admin"][1]
    add_user(session, "team_member", "maria")
    add_user(session, "team_member", "gone", is_active=False)

    def names(query):
        items = api.get(f"/users?{query}", headers=headers).json()["items"]
        return {item["full_name"] for item in items}

    assert names("search=MARI") == {"maria"}
    assert names("search=%25") == set()  # A literal percent sign, not a wildcard
    assert names("is_active=false") == {"gone"}
    assert names("role=project_manager") == {"project_manager"}
    assert len(names("limit=2")) == 2
    assert api.get("/users?limit=1", headers=headers).json()["total"] == 5


def test_setting_must_exist_and_be_valid(api, people):
    headers = people["admin"][1]
    body = {"value": 5}
    assert api.put("/settings/nope", json=body, headers=headers).status_code == 404
    url = "/settings/budget_warning_percent"
    assert api.put(url, json={"value": -1}, headers=headers).status_code == 400


# --- Record-level rules for projects and deliverables ----------------------
# The project endpoints arrive in Phases 5 to 8. These routes exist only in
# this test, and use the same dependencies those endpoints will use.


@pytest.fixture()
def world(api, session, people):
    """Create two projects, and routes protected by the record-level rules."""
    department = Department(name="D")
    session.add(department)
    session.flush()

    def project(key, manager):
        record = Project(
            code=key,
            name=key,
            department_id=department.id,
            manager_id=manager.id,
            start_date=START,
            end_date=END,
        )
        session.add(record)
        session.flush()
        return record

    def resource(key, user=None):
        record = Resource(
            employee_code=key,
            full_name=key,
            email=f"r-{key}@example.com",
            department_id=department.id,
            job_title="Engineer",
            user_id=user.id if user else None,
        )
        session.add(record)
        session.flush()
        return record

    def deliverable(parent, key, owner):
        record = Deliverable(
            project_id=parent.id,
            name=key,
            owner_id=owner.id,
            start_date=START,
            due_date=END,
        )
        session.add(record)
        session.flush()
        return record

    rival = add_user(session, "project_manager", "rival")
    member = resource("M", people["team_member"][0])
    colleague = resource("C")
    mine = project("MINE", people["project_manager"][0])
    other = project("OTHER", rival)
    session.add(
        ProjectAssignment(
            project_id=mine.id,
            resource_id=member.id,
            allocation_percent=50,
            start_date=START,
            end_date=END,
        )
    )
    session.flush()

    @api.app.get("/t/projects")
    def list_projects(user: CurrentUser, db: SessionDep):
        return sorted(db.scalars(select(Project.code).where(visible_projects(user))))

    @api.app.get("/t/projects/{project_id}")
    def read_project(project_id: int, user: CurrentUser, db: SessionDep):
        return find_visible_project(db, user, project_id).code

    @api.app.put("/t/projects/{project_id}")
    def edit_project(
        found: Annotated[Project, Depends(managed_project(Permission.MANAGE_BUDGETS))],
    ):
        return found.code

    @api.app.get("/t/deliverables")
    def list_deliverables(user: CurrentUser, db: SessionDep):
        query = select(Deliverable.name).where(visible_deliverables(user))
        return sorted(db.scalars(query))

    @api.app.put("/t/deliverables/{deliverable_id}")
    def edit_deliverable(
        found: Annotated[Deliverable, Depends(find_updatable_deliverable)],
    ):
        return found.name

    return {
        "mine": mine.id,
        "other": other.id,
        "own": deliverable(mine, "own", member).id,
        "colleague": deliverable(mine, "colleague", colleague).id,
        "foreign": deliverable(other, "foreign", colleague).id,
    }


@pytest.mark.parametrize(
    ("role", "projects", "deliverables"),
    [
        ("admin", ["MINE", "OTHER"], ["colleague", "foreign", "own"]),
        ("project_manager", ["MINE"], ["colleague", "own"]),
        ("team_member", ["MINE"], ["own"]),
    ],
)
def test_lists_only_show_permitted_records(
    api, people, world, role, projects, deliverables
):
    headers = people[role][1]
    assert api.get("/t/projects", headers=headers).json() == projects
    assert api.get("/t/deliverables", headers=headers).json() == deliverables


@pytest.mark.parametrize(
    ("role", "method", "path", "status"),
    [
        ("admin", "get", "/t/projects/{other}", 200),
        ("admin", "put", "/t/projects/{other}", 200),
        ("admin", "put", "/t/deliverables/{foreign}", 200),
        ("project_manager", "get", "/t/projects/{mine}", 200),
        ("project_manager", "put", "/t/projects/{mine}", 200),
        ("project_manager", "get", "/t/projects/{other}", 404),
        ("project_manager", "put", "/t/projects/{other}", 404),
        ("project_manager", "put", "/t/deliverables/{colleague}", 200),
        ("project_manager", "put", "/t/deliverables/{foreign}", 404),
        ("team_member", "get", "/t/projects/{mine}", 200),
        ("team_member", "put", "/t/projects/{mine}", 403),
        ("team_member", "get", "/t/projects/{other}", 404),
        ("team_member", "put", "/t/projects/{other}", 403),
        ("team_member", "put", "/t/deliverables/{own}", 200),
        ("team_member", "put", "/t/deliverables/{colleague}", 404),
        ("team_member", "put", "/t/deliverables/{foreign}", 404),
    ],
)
def test_record_rules(api, people, world, role, method, path, status):
    url = path.format(**world)
    response = api.request(method, url, headers=people[role][1])
    assert response.status_code == status


def test_manager_can_view_but_not_manage_an_assigned_project(
    api, session, people, world
):
    user, headers = people["project_manager"]
    department_id = session.scalar(select(Department.id))
    resource = Resource(
        employee_code="PM",
        full_name="PM",
        email="pm@example.com",
        department_id=department_id,
        job_title="Manager",
        user_id=user.id,
    )
    session.add(resource)
    session.flush()
    session.add(
        ProjectAssignment(
            project_id=world["other"],
            resource_id=resource.id,
            allocation_percent=10,
            start_date=START,
            end_date=END,
        )
    )
    session.flush()
    url = f"/t/projects/{world['other']}"
    assert api.get(url, headers=headers).status_code == 200
    assert api.put(url, headers=headers).status_code == 403


def test_demoted_manager_loses_their_projects(api, session, people, world):
    user = people["project_manager"][0]
    session.execute(update(User).where(User.id == user.id).values(role="team_member"))
    session.expire_all()
    headers = auth(api, user)
    assert api.get("/t/projects", headers=headers).json() == []


# --- Permission list and first admin ---------------------------------------


def test_only_admin_holds_admin_permissions():
    admin_only = {
        Permission.MANAGE_USERS,
        Permission.MANAGE_DEPARTMENTS,
        Permission.MANAGE_SETTINGS,
        Permission.MANAGE_RESOURCES,
        Permission.CREATE_PROJECTS,
        Permission.DELETE_PROJECTS,
    }
    assert ROLE_PERMISSIONS[Role.ADMIN] == set(Permission)
    for role in (Role.PROJECT_MANAGER, Role.TEAM_MEMBER):
        assert not ROLE_PERMISSIONS[role] & admin_only
    assert ROLE_PERMISSIONS[Role.TEAM_MEMBER] == {Permission.UPDATE_DELIVERABLE_STATUS}


def test_command_line_creates_an_admin_who_can_sign_in(api, session):
    user = create_admin(session, "First@Example.com", "First", PASSWORD)
    assert (user.email, user.role) == ("first@example.com", "admin")
    assert sign_in(api, user).status_code == 200
    with pytest.raises(ValidationError):
        create_admin(session, "x@example.com", "X", "short")
