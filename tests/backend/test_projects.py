"""Project tests through the real HTTP routes and a real database."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from helpers import add_user
from sqlalchemy import func, select

from app.models import (
    Deliverable,
    Department,
    Expense,
    ExpenseCategory,
    Project,
    ProjectAssignment,
    Resource,
    User,
)

START, END = "2026-01-01", "2026-06-30"


@pytest.fixture()
def departments(session):
    """Create two departments."""
    rows = [Department(name="IT"), Department(name="Finance")]
    session.add_all(rows)
    session.flush()
    return {row.name: row.id for row in rows}


@pytest.fixture()
def body(departments):
    """Return a valid project request."""
    return {
        "code": "CRM-1",
        "name": "CRM rollout",
        "description": "Replace the old CRM",
        "department_id": departments["IT"],
        "start_date": START,
        "end_date": END,
        "status": "Active",
        "priority": "High",
        "planned_budget": "125000.50",
    }


@pytest.fixture()
def admin(people):
    """Return the admin's headers."""
    return people["admin"][1]


def create(api, headers, body, **changes):
    """Create a project and return it."""
    response = api.post("/projects", json={**body, **changes}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def fields(response):
    """Return the fields an error points at."""
    return [item["field"] for item in response.json()["error"]["details"]]


# --- Create, read, update --------------------------------------------------


def test_create_read_and_update(api, session, admin, body, people):
    manager = people["project_manager"][0]
    created = create(api, admin, {**body, "code": "crm-1"}, manager_id=manager.id)
    assert created["code"] == "CRM-1"
    assert created["department"]["name"] == "IT"
    assert created["manager"] == {"id": manager.id, "name": "project_manager"}
    assert created["planned_budget"] == "125000.50"
    assert created["progress_percent"] == 0

    url = f"/projects/{created['id']}"
    assert api.get(url, headers=admin).json() == created

    changes = {
        **body,
        "name": "Renamed",
        "status": "On Hold",
        "priority": "Low",
        "end_date": "2026-12-31",
        "planned_budget": 10,
    }
    updated = api.put(url, json=changes, headers=admin).json()
    assert (updated["name"], updated["status"]) == ("Renamed", "On Hold")
    assert updated["manager"] is None
    session.expire_all()
    stored = session.get(Project, created["id"])
    assert stored.end_date == date(2026, 12, 31)
    assert stored.planned_budget == Decimal(10)


def test_completing_and_reopening(api, admin, body):
    url = f"/projects/{create(api, admin, body)['id']}"
    done = {**body, "status": "Completed", "actual_completion_date": "2026-05-01"}
    assert api.put(url, json=done, headers=admin).json()["progress_percent"] == 100
    reopened = api.put(url, json=body, headers=admin).json()
    assert reopened["actual_completion_date"] is None
    assert reopened["progress_percent"] == 0


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"code": ""}, "body.code"),
        ({"code": "has space"}, "body.code"),
        ({"code": "X" * 31}, "body.code"),
        ({"name": "   "}, "body.name"),
        ({"name": "X" * 201}, "body.name"),
        ({"start_date": None}, "body.start_date"),
        ({"start_date": "not-a-date"}, "body.start_date"),
        ({"start_date": "1900-01-01"}, "body.start_date"),
        ({"end_date": "2025-01-01"}, "body"),
        ({"status": "Finished"}, "body.status"),
        ({"priority": "Urgent"}, "body.priority"),
        ({"planned_budget": -1}, "body.planned_budget"),
        ({"planned_budget": "1.001"}, "body.planned_budget"),
        ({"planned_budget": "abc"}, "body.planned_budget"),
        ({"planned_budget": "NaN"}, "body.planned_budget"),
        ({"status": "Completed"}, "body"),
        ({"actual_completion_date": "2026-05-01"}, "body"),
        (
            {"status": "Completed", "actual_completion_date": "2025-12-31"},
            "body",
        ),
        (
            {
                "status": "Completed",
                "actual_completion_date": str(date.today() + timedelta(days=5)),
            },
            "body.actual_completion_date",
        ),
        ({"progress_percent": 50}, "body.progress_percent"),
        ({"department_id": 999999}, "department_id"),
        ({"manager_id": 999999}, "manager_id"),
    ],
)
def test_invalid_input(api, session, admin, body, changes, field):
    response = api.post("/projects", json={**body, **changes}, headers=admin)
    assert response.status_code == 400
    assert field in fields(response)
    assert session.scalar(select(func.count()).select_from(Project)) == 0


def test_duplicate_code_is_rejected(api, admin, body):
    create(api, admin, body)
    response = api.post("/projects", json={**body, "code": "crm-1"}, headers=admin)
    assert response.status_code == 409
    assert fields(response) == ["code"]


def test_manager_must_be_able_to_manage(api, session, admin, body, people):
    inactive = add_user(session, "project_manager", "gone", is_active=False)
    for user in (people["team_member"][0], inactive):
        response = api.post(
            "/projects", json={**body, "manager_id": user.id}, headers=admin
        )
        assert (response.status_code, fields(response)) == (400, ["manager_id"])


def test_existing_manager_can_stay_after_leaving(api, session, admin, body):
    manager = add_user(session, "project_manager", "leaver")
    project = create(api, admin, body, manager_id=manager.id)
    session.get(User, manager.id).is_active = False
    session.flush()
    changes = {**body, "manager_id": manager.id, "name": "Still editable"}
    url = f"/projects/{project['id']}"
    assert api.put(url, json=changes, headers=admin).status_code == 200


def test_unknown_project(api, admin, body):
    for method in ("get", "put", "delete"):
        sent = {"json": body} if method == "put" else {}
        response = api.request(method, "/projects/999999", headers=admin, **sent)
        assert response.status_code == 404
    assert api.get("/projects/abc", headers=admin).status_code == 400


# --- Progress --------------------------------------------------------------


@pytest.mark.parametrize(
    ("work", "expected"),
    [
        ([(0, 10), (100, 30)], 75),  # Weighted by estimated hours
        ([(0, 0), (100, 30)], 50),  # An estimate is missing: plain average
        ([(33, 0), (33, 0), (34, 0)], 33.3),
    ],
)
def test_progress_is_calculated(api, session, admin, body, work, expected):
    project = create(api, admin, body)
    for number, (progress, hours) in enumerate(work):
        session.add(
            Deliverable(
                project_id=project["id"],
                name=str(number),
                start_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
                progress_percent=progress,
                estimated_hours=hours,
            )
        )
    session.flush()
    found = api.get(f"/projects/{project['id']}", headers=admin).json()
    assert found["progress_percent"] == expected
    assert found["deliverable_count"] == len(work)
    assert (
        api.get("/projects", headers=admin).json()["items"][0]["progress_percent"]
        == expected
    )


# --- Delete ----------------------------------------------------------------


def test_delete_needs_the_right_code(api, admin, body):
    project = create(api, admin, body, status="Planned")
    url = f"/projects/{project['id']}"
    for code in ("", "WRONG"):
        response = api.delete(f"{url}?confirm_code={code}", headers=admin)
        assert (response.status_code, fields(response)) == (400, ["confirm_code"])
    assert api.delete(f"{url}?confirm_code=crm-1", headers=admin).status_code == 204
    assert api.get(url, headers=admin).status_code == 404


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("Planned", 204),
        ("Cancelled", 204),
        ("Active", 409),
        ("On Hold", 409),
        ("Completed", 409),
    ],
)
def test_delete_depends_on_status(api, admin, body, status, expected):
    done = {"actual_completion_date": "2026-05-01"} if status == "Completed" else {}
    project = create(api, admin, body, status=status, **done)
    assert project["can_delete"] is (expected == 204)
    url = f"/projects/{project['id']}?confirm_code=CRM-1"
    assert api.delete(url, headers=admin).status_code == expected


def test_project_with_expenses_is_kept(api, session, admin, body):
    project = create(api, admin, body, status="Cancelled")
    session.add(
        Expense(
            project_id=project["id"],
            category_id=session.scalars(select(ExpenseCategory.id)).first(),
            amount=5,
            expense_date=date(2026, 2, 1),
        )
    )
    session.flush()
    url = f"/projects/{project['id']}?confirm_code=CRM-1"
    response = api.delete(url, headers=admin)
    assert response.status_code == 409
    assert "expenses" in response.json()["error"]["message"]
    assert api.get(f"/projects/{project['id']}", headers=admin).status_code == 200


# --- Search, filter, sort --------------------------------------------------


@pytest.fixture()
def catalog(api, session, admin, body, departments):
    """Create three different projects."""
    manager = add_user(session, "project_manager", "mia")
    create(api, admin, body, code="A", name="Alpha", manager_id=manager.id)
    create(
        api,
        admin,
        body,
        code="B",
        name="beta 100%",
        department_id=departments["Finance"],
        status="Planned",
        priority="Critical",
        start_date="2026-03-01",
        end_date="2026-09-30",
    )
    create(
        api,
        admin,
        body,
        code="C",
        name="Gamma",
        description="Payroll",
        status="On Hold",
        priority="Low",
        end_date="2026-03-31",
    )
    return {"manager": manager.id, **departments}


@pytest.mark.parametrize(
    ("query", "codes"),
    [
        ("", "CAB"),
        ("search=ALPHA", "A"),
        ("search=payroll", "C"),
        ("search=%25", "B"),
        ("search=_", ""),
        ("status=Active", "A"),
        ("status=Active&status=Planned", "AB"),
        ("priority=Critical&priority=Low", "CB"),
        ("department_id={Finance}", "B"),
        ("manager_id={manager}", "A"),
        ("start_from=2026-02-01", "B"),
        ("start_to=2026-02-01", "CA"),
        ("end_from=2026-06-30", "AB"),
        ("end_to=2026-06-30", "CA"),
        ("status=Active&priority=Low", ""),
        ("sort=name", "ABC"),
        ("sort=name&order=desc", "CBA"),
        ("sort=priority&order=desc", "BAC"),
        ("sort=code&limit=1&offset=1", "B"),
    ],
)
def test_search_filter_and_sort(api, admin, catalog, query, codes):
    response = api.get(f"/projects?{query.format(**catalog)}", headers=admin)
    assert "".join(item["code"] for item in response.json()["items"]) == codes


def test_total_counts_all_pages(api, admin, catalog):
    page = api.get("/projects?limit=1", headers=admin).json()
    assert (len(page["items"]), page["total"]) == (1, 3)


@pytest.mark.parametrize(
    "query",
    [
        "status=Nope",
        "sort=planned_budget",
        "sort=id;drop",
        "limit=0",
        "limit=101",
        "offset=-1",
        "end_from=x",
    ],
)
def test_invalid_filters(api, admin, query):
    assert api.get(f"/projects?{query}", headers=admin).status_code == 400


# --- Roles -----------------------------------------------------------------


@pytest.fixture()
def owned(api, session, admin, body, people, departments):
    """Create one project for the manager and member, and one unrelated."""
    resource = Resource(
        employee_code="M",
        full_name="M",
        email="m@example.com",
        department_id=departments["IT"],
        job_title="Dev",
        user_id=people["team_member"][0].id,
    )
    session.add(resource)
    session.flush()
    manager = people["project_manager"][0]
    mine = create(api, admin, body, code="MINE", manager_id=manager.id)
    other = create(api, admin, body, code="OTHER")
    session.add(
        ProjectAssignment(
            project_id=mine["id"],
            resource_id=resource.id,
            allocation_percent=50,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )
    )
    session.flush()
    return {"mine": mine["id"], "other": other["id"], "manager": manager.id}


@pytest.mark.parametrize(
    ("role", "create_status", "mine", "other", "edit_mine", "edit_other", "remove"),
    [
        ("admin", 201, 200, 200, 200, 200, 409),
        ("project_manager", 403, 200, 404, 200, 404, 403),
        ("team_member", 403, 200, 404, 403, 403, 403),
    ],
)
def test_roles(
    api,
    people,
    body,
    owned,
    role,
    create_status,
    mine,
    other,
    edit_mine,
    edit_other,
    remove,
):
    headers = people[role][1]
    request = {**body, "code": "MINE", "manager_id": owned["manager"]}
    url_mine, url_other = (f"/projects/{owned[key]}" for key in ("mine", "other"))
    new = {**body, "code": "NEW"}
    assert api.post("/projects", json=new, headers=headers).status_code == create_status
    assert api.get(url_mine, headers=headers).status_code == mine
    assert api.get(url_other, headers=headers).status_code == other
    assert api.put(url_mine, json=request, headers=headers).status_code == edit_mine
    sent = {**body, "code": "OTHER"}
    assert api.put(url_other, json=sent, headers=headers).status_code == edit_other
    delete_url = f"{url_mine}?confirm_code=MINE"
    assert api.delete(delete_url, headers=headers).status_code == remove


@pytest.mark.parametrize("role", ["project_manager", "team_member"])
def test_lists_hide_other_projects(api, people, owned, role):
    page = api.get("/projects?search=OTHER", headers=people[role][1]).json()
    assert page == {"items": [], "total": 0}


def test_budget_is_hidden_from_team_members(api, people, owned):
    for role, visible in (("project_manager", True), ("team_member", False)):
        headers = people[role][1]
        single = api.get(f"/projects/{owned['mine']}", headers=headers).json()
        listed = api.get("/projects", headers=headers).json()["items"][0]
        for found in (single, listed):
            assert (found["planned_budget"] is not None) is visible
            assert found["can_edit"] is visible
            assert found["can_delete"] is False


@pytest.mark.parametrize("field", ["code", "department_id", "manager_id"])
def test_manager_cannot_change_admin_fields(
    api,
    people,
    body,
    owned,
    departments,
    field,
):
    request = {**body, "code": "MINE", "manager_id": owned["manager"]}
    request[field] = {
        "code": "STOLEN",
        "department_id": departments["Finance"],
        "manager_id": None,
    }[field]
    url = f"/projects/{owned['mine']}"
    response = api.put(url, json=request, headers=people["project_manager"][1])
    assert response.status_code == 403


def test_options_depend_on_role(api, session, people, owned):
    add_user(session, "project_manager", "unrelated")
    add_user(session, "project_manager", "left", is_active=False)

    def managers(role):
        answer = api.get("/projects/options", headers=people[role][1]).json()
        assert answer["departments"][0]["name"] == "Finance"
        return {item["name"] for item in answer["managers"]}

    assert managers("admin") == {"admin", "project_manager", "unrelated"}
    assert managers("team_member") == {"project_manager"}


@pytest.mark.parametrize("role", ["project_manager", "team_member"])
def test_creation_is_refused_before_the_body_is_checked(api, people, role):
    response = api.post("/projects", json={}, headers=people[role][1])
    assert response.status_code == 403
