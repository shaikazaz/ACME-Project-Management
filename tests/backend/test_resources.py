"""Resource, assignment and workload tests through the real HTTP routes."""

import random
from datetime import timedelta
from decimal import Decimal

import pytest
from helpers import add_user
from sqlalchemy import func, select

from app.dates import today
from app.models import (
    AppSetting,
    Deliverable,
    Department,
    Project,
    ProjectAssignment,
    Resource,
)
from app.services.resources import with_workload
from app.services.workload import Period, workload_periods

NOW = today()


def day(offset):
    """Return the date a number of days from today."""
    return NOW + timedelta(days=offset)


@pytest.fixture()
def world(session, people):
    """Create departments and projects for each access situation."""
    departments = [Department(name="IT"), Department(name="Finance")]
    session.add_all(departments)
    session.flush()
    rival = add_user(session, "project_manager", "rival")
    manager = people["project_manager"][0]
    ids = {row.name: row.id for row in departments}
    for code, owner in (("A", manager), ("B", manager), ("OTHER", rival)):
        row = Project(
            code=code,
            name=f"Project {code}",
            department_id=ids["IT"],
            manager_id=owner.id,
            start_date=day(-30),
            end_date=day(300),
            status="Active",
        )
        session.add(row)
        session.flush()
        ids[code] = row.id
    return ids


class Client:
    """Calls the API as one user."""

    def __init__(self, api, headers, world):
        self.api, self.headers, self.world = api, headers, world

    def call(self, method, url, body=None):
        return self.api.request(method, url, json=body, headers=self.headers)

    def ok(self, method, url, body=None, status=200):
        response = self.call(method, url, body)
        assert response.status_code == status, response.text
        return response.json() if response.content else None

    def person(self, code="E1", **changes):
        return self.ok("post", "/resources", self.body(code, **changes), 201)

    def body(self, code="E1", **changes):
        return {
            "employee_code": code,
            "full_name": f"Person {code}",
            "email": f"{code}@example.com",
            "department_id": self.world["IT"],
            "job_title": "Engineer",
            **changes,
        }

    def get(self, person, query=""):
        return self.ok("get", f"/resources/{person['id']}{query}")

    def assign(self, project, person, percent, start=-10, end=10, **changes):
        body = {
            "resource_id": person["id"],
            "allocation_percent": percent,
            "start_date": str(day(start)),
            "end_date": str(day(end)),
            **changes,
        }
        return self.call("post", f"/projects/{self.world[project]}/assignments", body)


@pytest.fixture()
def clients(api, people, world):
    """Return one client per role."""
    return {role: Client(api, headers, world) for role, (_, headers) in people.items()}


@pytest.fixture()
def admin(clients):
    """Return the admin's client."""
    return clients["admin"]


@pytest.fixture()
def pm(clients):
    """Return the project manager's client."""
    return clients["project_manager"]


def fields(response):
    """Return the fields an error points at."""
    return [item["field"] for item in response.json()["error"]["details"]]


# --- The workshop scenarios ------------------------------------------------


@pytest.mark.parametrize(
    ("capacity", "first", "second", "total", "over", "utilization", "remaining"),
    [
        (100, 50, 30, 80, False, 80, 20),  # Scenario 1
        (100, 70, 50, 120, True, 120, -20),  # Scenario 2
        (80, 60, 30, 90, True, 112.5, -10),  # Scenario 3
        (80, 50, 30, 80, False, 100, 0),  # Exactly full is not over
        (100, 60, 50, 110, True, 110, -10),
        (100, "33.33", "66.67", 100, False, 100, 0),  # Exact decimals
        (100, "33.34", "66.67", 100.01, True, 100, -0.01),
        (0, 10, 10, 20, True, None, -20),
    ],
)
def test_scenarios(
    admin, pm, capacity, first, second, total, over, utilization, remaining
):
    person = admin.person(capacity_percent=capacity)
    assert pm.assign("A", person, first).status_code == 201
    response = pm.assign("B", person, second)
    assert response.status_code == 201

    def check(load):
        assert load["current_percent"] == load["peak_percent"] == total
        assert load["capacity_percent"] == capacity
        assert load["is_over_allocated"] is load["is_over_allocated_now"] is over
        assert load["utilization_percent"] == utilization
        assert load["remaining_percent"] == pytest.approx(remaining)

    check(response.json()["workload"])
    check(pm.get(person)["workload"])
    check(pm.ok("get", "/resources")["items"][0]["workload"])
    url = f"/projects/{pm.world['A']}/assignments"
    check(pm.ok("get", url)["items"][0]["workload"])
    report = pm.ok("get", "/resources/workload")
    assert report["over_allocated_count"] == int(over)
    assert pm.ok("get", "/resources?over_allocated=true")["total"] == int(over)
    assert pm.ok("get", "/resources?over_allocated=false")["total"] == int(not over)


def test_unassigned_resource_has_no_load(admin):
    load = admin.person()["workload"]
    assert (load["peak_percent"], load["utilization_percent"]) == (0, 0)
    assert load["remaining_percent"] == 100
    empty = admin.person("E2", capacity_percent=0)["workload"]
    assert (empty["utilization_percent"], empty["is_over_allocated"]) == (0, False)


# --- Dates -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("first", "second", "current", "peak"),
    [
        ((-10, 10), (-5, 5), 120, 120),
        ((-10, 5), (6, 20), 70, 70),  # One after the other
        ((-10, 5), (5, 20), 70, 120),  # They share one day
        ((-20, -11), (-10, 10), 50, 50),  # The first has ended
        ((-10, -1), (1, 10), 0, 50),  # Nothing today
        ((-10, 0), (0, 10), 120, 120),  # Both include today
        ((5, 10), (7, 20), 0, 120),  # Both in the future
    ],
)
def test_only_overlapping_assignments_add_up(admin, pm, first, second, current, peak):
    person = admin.person()
    pm.assign("A", person, 70, *first)
    pm.assign("B", person, 50, *second)
    load = pm.get(person)["workload"]
    assert (load["current_percent"], load["peak_percent"]) == (current, peak)
    assert load["is_over_allocated_now"] is (current > 100)
    assert load["is_over_allocated"] is (peak > 100)


@pytest.mark.parametrize(
    ("start", "end", "peak"),
    [(0, 4, 70), (0, 5, 120), (5, 5, 120), (6, 20, 50), (21, 30, 0), (-30, 30, 120)],
)
def test_peak_depends_on_the_period(admin, pm, start, end, peak):
    person = admin.person()
    pm.assign("A", person, 70, -10, 5)
    pm.assign("B", person, 50, 5, 20)
    query = f"?period_from={day(start)}&period_to={day(end)}"
    assert pm.get(person, query)["workload"]["peak_percent"] == peak
    report = pm.ok("get", f"/resources/workload{query}")
    assert report["over_allocated_count"] == int(peak > 100)


def test_period_must_be_in_order(pm):
    query = f"?period_from={day(1)}&period_to={day(0)}"
    for url in ("/resources", "/resources/workload"):
        assert pm.call("get", url + query).status_code == 400


def test_periods_show_the_load_over_time(admin, pm):
    person = admin.person()
    pm.assign("A", person, 70, -10, 5)
    pm.assign("B", person, 50, 4, 8)
    periods = [
        (item["start_date"], item["end_date"], item["total_percent"])
        for item in pm.get(person)["periods"]
    ]
    assert periods == [
        (str(day(0)), str(day(3)), 70),
        (str(day(4)), str(day(5)), 120),
        (str(day(6)), str(day(8)), 50),
    ]
    over = [item["is_over_allocated"] for item in pm.get(person)["periods"]]
    assert over == [False, True, False]


def test_peak_matches_a_day_by_day_count(session, world):
    """Compare the SQL with counting every single day, on random data."""
    rng = random.Random(7)
    people, projects = [], []
    for number in range(12):
        status = "Cancelled" if number == 0 else "Active"
        project = Project(
            code=f"R{number}",
            name="R",
            department_id=world["IT"],
            start_date=day(0),
            end_date=day(1),
            status=status,
        )
        person = Resource(
            employee_code=f"R{number}",
            full_name="R",
            email=f"r{number}@example.com",
            department_id=world["IT"],
            job_title="R",
        )
        session.add_all([project, person])
        projects.append(project)
        people.append(person)
    session.flush()
    spans = {person.id: [] for person in people}
    for person in people:
        for project in rng.sample(projects, rng.randint(0, 8)):
            first = rng.randint(-40, 40)
            last = first + rng.randint(0, 30)
            percent = Decimal(rng.randint(1, 10000)) / 100
            session.add(
                ProjectAssignment(
                    project_id=project.id,
                    resource_id=person.id,
                    allocation_percent=percent,
                    start_date=day(first),
                    end_date=day(last),
                )
            )
            if project.status == "Active":
                spans[person.id].append((first, last, percent))
    session.flush()

    def total(person_id, offset):
        parts = spans[person_id]
        return sum((p for a, b, p in parts if a <= offset <= b), Decimal(0))

    for start, end in ((-50, 90), (0, 90), (-10, 10), (5, 5), (80, 90)):
        query, _ = with_workload(Period(day(start), day(end)))
        rows = session.execute(query.where(Resource.id.in_(spans))).all()
        assert len(rows) == len(people)
        for resource, current, peak in rows:
            days = range(start, end + 1)
            assert peak == max(total(resource.id, offset) for offset in days)
            assert current == total(resource.id, 0)

    for person_id, parts in spans.items():
        dated = [(day(a), day(b), p) for a, b, p in parts]
        periods = workload_periods(dated, Decimal(100), day(0))
        for offset in range(0, 90):
            found = [
                item.total_percent
                for item in periods
                if item.start_date <= day(offset) <= item.end_date
            ]
            assert sum(found) == pytest.approx(float(total(person_id, offset)))
            assert len(found) <= 1


# --- Which projects count --------------------------------------------------


@pytest.mark.parametrize(
    ("status", "peak"),
    [("Planned", 70), ("Active", 70), ("On Hold", 70), ("Completed", 0)]
    + [("Cancelled", 0)],
)
def test_closed_projects_release_people(admin, pm, session, status, peak):
    person = admin.person()
    pm.assign("A", person, 70)
    row = session.get(Project, pm.world["A"])
    row.status = status
    row.actual_completion_date = NOW if status == "Completed" else None
    session.flush()
    found = pm.get(person)
    assert found["workload"]["peak_percent"] == peak
    assert found["assignments"][0]["counts"] is (peak > 0)
    assert bool(found["periods"]) is (peak > 0)


# --- Hours -----------------------------------------------------------------


def test_hours_follow_the_setting(admin, pm, session):
    person = admin.person(capacity_percent=80)
    pm.assign("A", person, 50)
    load = pm.get(person)["workload"]
    assert (load["capacity_hours"], load["peak_hours"]) == (32, 20)
    url = "/settings/full_time_hours_per_week"
    admin.ok("put", url, {"value": 37.5})
    load = pm.get(person)["workload"]
    assert (load["capacity_hours"], load["peak_hours"]) == (30, 18.75)
    session.expire_all()
    assert session.get(AppSetting, "full_time_hours_per_week").value == Decimal("37.5")


# --- Resource CRUD ---------------------------------------------------------


def test_crud(admin, session, people):
    account = people["team_member"][0]
    created = admin.person(
        "emp-1",
        skills=["Python", "SQL", "python "],
        capacity_percent="62.50",
        availability="On Leave",
        user_id=account.id,
    )
    assert created["employee_code"] == "EMP-1"
    assert created["skills"] == ["Python", "SQL"]
    assert created["user"]["id"] == account.id
    assert created["department"]["name"] == "IT"
    assert admin.get(created) == created

    changes = admin.body(
        "EMP-1", full_name="Renamed", department_id=admin.world["Finance"]
    )
    updated = admin.ok("put", f"/resources/{created['id']}", changes)
    assert (updated["full_name"], updated["user"]) == ("Renamed", None)
    session.expire_all()
    stored = session.get(Resource, created["id"])
    assert (stored.capacity_percent, stored.skills) == (100, [])

    admin.ok("delete", f"/resources/{created['id']}", status=204)
    assert admin.call("get", f"/resources/{created['id']}").status_code == 404


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"employee_code": "has space"}, "body.employee_code"),
        ({"full_name": "  "}, "body.full_name"),
        ({"email": "nope"}, "body.email"),
        ({"job_title": ""}, "body.job_title"),
        ({"capacity_percent": -1}, "body.capacity_percent"),
        ({"capacity_percent": 100.01}, "body.capacity_percent"),
        ({"capacity_percent": "NaN"}, "body.capacity_percent"),
        ({"availability": "Busy"}, "body.availability"),
        ({"skills": [""]}, "body.skills.0"),
        ({"skills": ["x"] * 21}, "body.skills"),
        ({"department_id": 999999}, "department_id"),
        ({"user_id": 999999}, "user_id"),
        ({"workload": 1}, "body.workload"),
    ],
)
def test_invalid_resources(admin, session, changes, field):
    response = admin.call("post", "/resources", admin.body(**changes))
    assert response.status_code == 400, response.text
    assert field in fields(response)
    assert session.scalar(select(func.count()).select_from(Resource)) == 0


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"employee_code": "e1"}, "employee_code"),
        ({"email": "E1@EXAMPLE.COM"}, "email"),
        ({"user_id": True}, "user_id"),
    ],
)
def test_duplicates(admin, people, changes, field):
    account = people["team_member"][0].id
    admin.person("E1", user_id=account)
    if "user_id" in changes:
        changes = {"user_id": account}
    response = admin.call("post", "/resources", admin.body("E2", **changes))
    assert (response.status_code, fields(response)) == (409, [field])


def test_resource_in_use_is_kept(admin, pm, session):
    person = admin.person()
    pm.assign("A", person, 10)
    url = f"/resources/{person['id']}"
    response = admin.call("delete", url)
    assert response.status_code == 409
    assert "assignments" in response.json()["error"]["message"]
    page = pm.ok("get", f"/projects/{pm.world['A']}/assignments")
    item = page["items"][0]
    pm.ok("delete", f"/projects/{pm.world['A']}/assignments/{item['id']}", status=204)
    session.add(
        Deliverable(
            project_id=pm.world["A"],
            name="D",
            owner_id=person["id"],
            start_date=NOW,
            due_date=NOW,
        )
    )
    session.flush()
    response = admin.call("delete", url)
    assert response.status_code == 409
    assert "deliverables" in response.json()["error"]["message"]


# --- Assignments -----------------------------------------------------------


def test_assignment_crud(admin, pm, session):
    person = admin.person()
    created = pm.assign("A", person, "37.50", project_role="Tester").json()
    assert (created["allocation_percent"], created["allocation_hours"]) == (37.5, 15)
    assert created["project_role"] == "Tester"
    url = f"/projects/{pm.world['A']}/assignments"
    body = {
        "resource_id": person["id"],
        "allocation_percent": 60,
        "start_date": str(day(0)),
        "end_date": str(day(3)),
    }
    updated = pm.ok("put", f"{url}/{created['id']}", body)
    assert updated["workload"]["peak_percent"] == 60
    session.expire_all()
    stored = session.get(ProjectAssignment, created["id"])
    assert (stored.allocation_percent, stored.end_date) == (60, day(3))
    pm.ok("delete", f"{url}/{created['id']}", status=204)
    assert pm.ok("get", url)["total"] == 0
    assert pm.get(person)["workload"]["peak_percent"] == 0


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"allocation_percent": 0}, "body.allocation_percent"),
        ({"allocation_percent": -5}, "body.allocation_percent"),
        ({"allocation_percent": 100.01}, "body.allocation_percent"),
        ({"allocation_percent": "1.001"}, "body.allocation_percent"),
        ({"end_date": "2020-01-01"}, "body"),
        ({"start_date": None}, "body.start_date"),
        ({"project_role": "X" * 121}, "body.project_role"),
        ({"resource_id": 999999}, "resource_id"),
    ],
)
def test_invalid_assignments(admin, pm, session, changes, field):
    response = pm.assign("A", admin.person(), 50, **changes)
    assert response.status_code == 400, response.text
    assert field in fields(response)
    assert session.scalar(select(func.count()).select_from(ProjectAssignment)) == 0


def test_one_assignment_per_project(admin, pm):
    person = admin.person()
    pm.assign("A", person, 50)
    response = pm.assign("A", person, 20, 50, 60)
    assert (response.status_code, fields(response)) == (409, ["resource_id"])


def test_assignment_cannot_move_to_another_person(admin, pm):
    first, second = admin.person("E1"), admin.person("E2")
    created = pm.assign("A", first, 50).json()
    body = {
        "resource_id": second["id"],
        "allocation_percent": 50,
        "start_date": str(NOW),
        "end_date": str(NOW),
    }
    url = f"/projects/{pm.world['A']}/assignments/{created['id']}"
    response = pm.call("put", url, body)
    assert (response.status_code, fields(response)) == (400, ["resource_id"])


def test_assignment_belongs_to_its_project(admin, pm):
    created = pm.assign("A", admin.person(), 50).json()
    url = f"/projects/{pm.world['B']}/assignments/{created['id']}"
    assert pm.call("delete", url).status_code == 404


@pytest.mark.parametrize(
    ("availability", "status", "cover"),
    [("Available", 201, False), ("On Leave", 201, True), ("Unavailable", 409, False)],
)
def test_availability(admin, pm, availability, status, cover):
    person = admin.person(availability=availability)
    assert pm.assign("A", person, 50).status_code == status
    assert pm.get(person)["needs_cover"] is cover
    assert pm.ok("get", "/resources/workload")["needs_cover_count"] == int(cover)


def test_becoming_unavailable_is_flagged(admin, pm):
    person = admin.person()
    pm.assign("A", person, 50)
    body = admin.body(availability="Unavailable")
    assert admin.ok("put", f"/resources/{person['id']}", body)["needs_cover"] is True


def test_lowering_capacity_is_detected(admin, pm):
    person = admin.person()
    pm.assign("A", person, 70)
    body = admin.body(capacity_percent=50)
    updated = admin.ok("put", f"/resources/{person['id']}", body)
    assert updated["workload"]["is_over_allocated"] is True


def test_closed_projects_accept_no_changes(admin, pm, session):
    person = admin.person()
    created = pm.assign("A", person, 50).json()
    session.get(Project, pm.world["A"]).status = "Cancelled"
    session.flush()
    url = f"/projects/{pm.world['A']}/assignments/{created['id']}"
    body = {
        "resource_id": person["id"],
        "allocation_percent": 5,
        "start_date": str(NOW),
        "end_date": str(NOW),
    }
    assert pm.assign("A", admin.person("E2"), 5).status_code == 409
    assert pm.call("put", url, body).status_code == 409
    assert pm.call("delete", url).status_code == 409


# --- Report ----------------------------------------------------------------


def test_report(admin, pm):
    finance = {"department_id": admin.world["Finance"]}
    people = {
        "over": admin.person("E1", capacity_percent=80),
        "full": admin.person("E2", **finance),
        "part": admin.person("E3", **finance),
        "none": admin.person("E4"),
        "zero": admin.person("E5", capacity_percent=0),
    }
    pm.assign("A", people["over"], 60)
    pm.assign("B", people["over"], 30)
    pm.assign("A", people["full"], 100)
    pm.assign("A", people["part"], 25)
    report = pm.ok("get", "/resources/workload")
    assert report["resource_count"] == 5
    assert report["over_allocated_count"] == 1
    assert report["fully_allocated_count"] == 1
    assert report["partly_allocated_count"] == 1
    assert report["unallocated_count"] == 2
    assert (report["capacity_percent"], report["peak_percent"]) == (380, 215)
    assert report["utilization_percent"] == 56.6
    assert report["period_from"] == str(NOW)
    rows = {row["department"]["name"]: row for row in report["departments"]}
    assert list(rows) == ["Finance", "IT"]
    assert (rows["Finance"]["peak_percent"], rows["IT"]["peak_percent"]) == (125, 90)
    assert rows["IT"]["utilization_percent"] == 50
    assert rows["IT"]["over_allocated_count"] == 1


def test_empty_report(pm):
    report = pm.ok("get", "/resources/workload")
    assert (report["resource_count"], report["utilization_percent"]) == (0, None)


# --- Search ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", "ABC"),
        ("search=anna", "A"),
        ("search=DESIGN", "B"),
        ("search=postgres", "C"),
        ("search=b@", "B"),
        ("search=%25", ""),
        ("department_id={Finance}", "B"),
        ("availability=On Leave", "C"),
        ("availability=On Leave&availability=Available", "ABC"),
        ("skill=python", "AC"),
        ("skill=pyth", ""),
        ("over_allocated=true", "C"),
        ("over_allocated=false", "AB"),
        ("sort=name&order=desc", "CBA"),
        ("sort=capacity", "CAB"),
        ("sort=peak&order=desc", "ACB"),
        ("sort=utilization&order=desc", "CAB"),
        ("sort=current&order=desc&limit=1", "A"),
        ("sort=department", "BAC"),
        ("sort=code&limit=1&offset=1", "B"),
    ],
)
def test_search(admin, pm, query, expected):
    anna = admin.person("A", full_name="Anna", skills=["Python"])
    admin.person(
        "B",
        full_name="Ben",
        job_title="Designer",
        department_id=admin.world["Finance"],
    )
    carl = admin.person(
        "C",
        full_name="Carl",
        skills=["PYTHON", "Postgres"],
        availability="On Leave",
        capacity_percent=20,
    )
    pm.assign("A", anna, 60)
    pm.assign("A", carl, 40)
    page = pm.ok("get", f"/resources?{query.format(**admin.world)}")
    assert "".join(item["employee_code"] for item in page["items"]) == expected


@pytest.mark.parametrize(
    "query",
    ["availability=Busy", "sort=email", "over_allocated=x", "limit=0", "period_to=x"],
)
def test_invalid_filters(pm, query):
    assert pm.call("get", f"/resources?{query}").status_code == 400


# --- Roles -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("role", "view", "manage", "assign", "foreign"),
    [
        ("admin", 200, 201, 201, 201),
        ("project_manager", 200, 403, 201, 404),
        ("team_member", 403, 403, 403, 403),
    ],
)
def test_roles(admin, clients, role, view, manage, assign, foreign):
    person, client = admin.person(), clients[role]
    url = f"/resources/{person['id']}"
    assignments = f"/projects/{admin.world['A']}/assignments"
    for path in (
        "/resources",
        url,
        "/resources/options",
        "/resources/workload",
        assignments,
    ):
        assert client.call("get", path).status_code == view
    new = admin.body("E2")
    assert client.call("post", "/resources", new).status_code == manage
    expected = 200 if manage == 201 else manage
    changed = admin.body("E1", job_title="Changed")
    assert client.call("put", url, changed).status_code == expected
    assert client.assign("A", person, 10).status_code == assign
    assert client.assign("OTHER", person, 10).status_code == foreign
    if manage == 403:
        assert client.call("delete", url).status_code == 403
        assert client.call("post", "/resources", {}).status_code == 403
    if assign == 403:
        for method in ("put", "delete"):
            answer = client.call(method, f"{assignments}/1", {})
            assert answer.status_code == 403


def test_hidden_projects_count_but_are_not_revealed(admin, pm):
    person = admin.person()
    pm.assign("A", person, 70)
    admin.assign("OTHER", person, 50, project_role="Secret role")
    found = pm.get(person)
    assert found["workload"]["peak_percent"] == 120
    hidden = [item for item in found["assignments"] if item["project_id"] is None]
    assert [item["project_name"] for item in hidden] == ["Another project"]
    assert hidden[0]["allocation_percent"] == 50
    text = str(found)
    assert "OTHER" not in text
    assert "Secret role" not in text


def test_options_depend_on_role(admin, pm, people):
    admin.person(skills=["SQL", "java"], user_id=people["team_member"][0].id)
    assert pm.ok("get", "/resources/options")["users"] == []
    options = admin.ok("get", "/resources/options")
    assert options["skills"] == ["java", "SQL"]
    names = {item["name"].split(" ")[0] for item in options["users"]}
    assert names == {"admin", "project_manager", "rival"}


def test_assignment_gives_the_team_member_access(admin, pm, clients, people):
    member = clients["team_member"]
    person = admin.person(user_id=people["team_member"][0].id)
    url = f"/projects/{pm.world['A']}"
    assert member.call("get", url).status_code == 404
    created = pm.assign("A", person, 50).json()
    assert member.call("get", url).status_code == 200
    pm.ok("delete", f"{url}/assignments/{created['id']}", status=204)
    assert member.call("get", url).status_code == 404
