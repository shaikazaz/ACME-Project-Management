"""Deliverable, milestone and dependency tests through the real HTTP routes."""

import threading
from datetime import date, timedelta

import pytest
from helpers import add_user
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.dates import today
from app.errors import ApiError
from app.models import (
    Deliverable,
    DeliverableDependency,
    Department,
    Milestone,
    Project,
    Resource,
)
from app.schemas.deliverables import ProgressRequest
from app.services.deliverables import update_progress

START, DUE = "2026-01-01", "2026-06-30"
STAGES = ("Requirements", "Design", "Development", "Testing", "Deployment")


@pytest.fixture()
def world(session, people):
    """Create two managed projects, a third one, and an owner with a login."""
    department = Department(name="IT")
    session.add(department)
    session.flush()
    rival = add_user(session, "project_manager", "rival")

    def project(code, manager):
        row = Project(
            code=code,
            name=code,
            department_id=department.id,
            manager_id=manager.id if manager else None,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="Active",
        )
        session.add(row)
        session.flush()
        return row.id

    def resource(code, user=None):
        row = Resource(
            employee_code=code,
            full_name=f"Resource {code}",
            email=f"{code}@example.com",
            department_id=department.id,
            job_title="Engineer",
            user_id=user.id if user else None,
        )
        session.add(row)
        session.flush()
        return row.id

    manager = people["project_manager"][0]
    return {
        "mine": project("MINE", manager),
        "second": project("SECOND", manager),
        "other": project("OTHER", rival),
        "member": resource("M", people["team_member"][0]),
        "colleague": resource("C"),
    }


class Client:
    """Calls the API as one user."""

    def __init__(self, api, headers):
        self.api, self.headers = api, headers

    def call(self, method, url, body=None):
        return self.api.request(method, url, json=body, headers=self.headers)

    def ok(self, method, url, body=None, status=200):
        response = self.call(method, url, body)
        assert response.status_code == status, response.text
        return response.json() if response.content else None

    def add(self, project_id, name, **changes):
        body = {"name": name, "start_date": START, "due_date": DUE, **changes}
        return self.ok("post", f"/projects/{project_id}/deliverables", body, 201)

    def get(self, item):
        return self.ok("get", f"/deliverables/{item['id']}")

    def edit(self, item, **changes):
        keep = ("name", "start_date", "due_date", "status", "progress_percent")
        body = {key: item[key] for key in keep} | changes
        return self.call("put", f"/deliverables/{item['id']}", body)

    def progress(self, item, status, **changes):
        url = f"/deliverables/{item['id']}/progress"
        return self.call("patch", url, {"status": status, **changes})

    def link(self, before, after):
        url = f"/deliverables/{after['id']}/predecessors"
        return self.call("post", url, {"predecessor_id": before["id"]})

    def unlink(self, before, after):
        url = f"/deliverables/{after['id']}/predecessors/{before['id']}"
        return self.call("delete", url)


@pytest.fixture()
def clients(api, people):
    """Return one client per role."""
    return {role: Client(api, headers) for role, (_, headers) in people.items()}


@pytest.fixture()
def pm(clients):
    """Return the project manager's client."""
    return clients["project_manager"]


@pytest.fixture()
def chain(pm, world):
    """Create Requirements → Design → Development → Testing → Deployment."""
    items = {name: pm.add(world["mine"], name) for name in STAGES}
    for before, after in zip(STAGES, STAGES[1:], strict=False):
        assert pm.link(items[before], items[after]).status_code == 201
    return items


def fields(response):
    """Return the fields an error points at."""
    return [item["field"] for item in response.json()["error"]["details"]]


def message(response):
    """Return the message of an error."""
    return response.json()["error"]["message"]


def names(items):
    """Return the names of several records."""
    return [item["name"] for item in items]


# --- Create, read, update, delete ------------------------------------------


def test_crud(pm, world, session):
    milestone = pm.ok(
        "post",
        f"/projects/{world['mine']}/milestones",
        {"name": "Beta", "due_date": DUE},
        201,
    )
    created = pm.add(
        world["mine"],
        "API",
        description="Build it",
        owner_id=world["member"],
        milestone_id=milestone["id"],
        priority="Critical",
        estimated_hours="12.50",
    )
    assert created["project"]["code"] == "MINE"
    assert created["owner"] == {"id": world["member"], "name": "Resource M"}
    assert created["milestone"]["name"] == "Beta"
    assert (created["status"], created["effective_status"]) == ("Not Started",) * 2
    assert created["estimated_hours"] == 12.5

    changed = pm.edit(
        created,
        name="API v2",
        status="In Progress",
        progress_percent=40,
        actual_hours=3,
        due_date="2026-07-31",
    ).json()
    assert changed["owner"] is None
    session.expire_all()
    stored = session.get(Deliverable, created["id"])
    assert (stored.name, stored.due_date) == ("API v2", date(2026, 7, 31))
    assert (stored.progress_percent, stored.actual_hours) == (40, 3)

    pm.ok("delete", f"/deliverables/{created['id']}", status=204)
    assert pm.call("get", f"/deliverables/{created['id']}").status_code == 404


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"name": " "}, "body.name"),
        ({"name": "X" * 201}, "body.name"),
        ({"due_date": "2025-01-01"}, "body"),
        ({"due_date": None}, "body.due_date"),
        ({"status": "Done"}, "body.status"),
        ({"priority": "Urgent"}, "body.priority"),
        ({"progress_percent": 101}, "body.progress_percent"),
        ({"progress_percent": -1}, "body.progress_percent"),
        ({"progress_percent": 10}, "body"),
        ({"status": "In Progress", "progress_percent": 100}, "body"),
        ({"completion_date": "2026-02-01"}, "body"),
        (
            {"status": "Completed", "completion_date": "2099-01-01"},
            "body.completion_date",
        ),
        ({"status": "Completed", "completion_date": "2025-12-31"}, "completion_date"),
        ({"estimated_hours": -1}, "body.estimated_hours"),
        ({"actual_hours": "1.001"}, "body.actual_hours"),
        ({"actual_hours": 1_000_000}, "body.actual_hours"),
        ({"owner_id": 999999}, "owner_id"),
        ({"milestone_id": 999999}, "milestone_id"),
        ({"project_id": 1}, "body.project_id"),
    ],
)
def test_invalid_input(pm, world, session, changes, field):
    body = {"name": "X", "start_date": START, "due_date": DUE, **changes}
    response = pm.call("post", f"/projects/{world['mine']}/deliverables", body)
    assert response.status_code == 400, response.text
    assert field in fields(response)
    assert session.scalar(select(func.count()).select_from(Deliverable)) == 0


def test_duplicate_name_in_one_project(pm, world):
    pm.add(world["mine"], "Same")
    pm.add(world["second"], "Same")
    body = {"name": "Same", "start_date": START, "due_date": DUE}
    response = pm.call("post", f"/projects/{world['mine']}/deliverables", body)
    assert (response.status_code, fields(response)) == (409, ["name"])


# --- Completion and overdue ------------------------------------------------


def test_completion_is_tracked(pm, world):
    item = pm.add(world["mine"], "A")
    done = pm.progress(item, "Completed").json()
    assert done["progress_percent"] == 100
    assert done["completion_date"] == str(today())
    assert done["completed_late"] is True  # Due on 30 June 2026 or earlier

    again = pm.progress(item, "Completed", actual_hours=4).json()
    assert again["completion_date"] == done["completion_date"]
    early = pm.progress(item, "Completed", completion_date="2026-03-01").json()
    assert early["completed_late"] is False

    reopened = pm.progress(item, "In Progress", progress_percent=80).json()
    assert reopened["completion_date"] is None


@pytest.mark.parametrize(
    ("offset", "status", "overdue"),
    [
        (-1, "Not Started", True),
        (-10, "In Progress", True),
        (-1, "Blocked", True),
        (0, "In Progress", False),
        (1, "Not Started", False),
        (-5, "Completed", False),
    ],
)
def test_overdue(pm, world, offset, status, overdue):
    due = today() + timedelta(days=offset)
    item = pm.add(
        world["mine"], "A", start_date="2020-01-01", due_date=str(due), status=status
    )
    assert item["is_overdue"] is overdue
    assert item["days_overdue"] == (-offset if overdue else 0)
    page = pm.ok("get", "/deliverables?overdue=true")
    assert page["total"] == int(overdue)
    assert pm.ok("get", "/deliverables?overdue=false")["total"] == int(not overdue)


def test_cancelled_projects_are_not_overdue(pm, world, session):
    item = pm.add(world["mine"], "A", start_date="2020-01-01", due_date="2020-02-01")
    session.get(Project, world["mine"]).status = "Cancelled"
    session.flush()
    assert pm.get(item)["is_overdue"] is False


def test_project_progress_and_counts(pm, world, chain):
    pm.progress(chain["Requirements"], "Completed")
    pm.progress(chain["Design"], "In Progress", progress_percent=50)
    project = pm.ok("get", f"/projects/{world['mine']}")
    assert project["progress_percent"] == 30
    counts = project["deliverables_by_status"]
    assert (counts["Completed"], counts["In Progress"], counts["Blocked"]) == (1, 1, 3)
    assert counts["Overdue"] == 4


# --- The dependency workflow -----------------------------------------------


def effective(pm, chain):
    """Return every stage's effective status."""
    return [pm.get(chain[name])["effective_status"] for name in STAGES]


def test_testing_is_blocked_until_development_is_completed(pm, chain):
    assert effective(pm, chain) == ["Not Started"] + ["Blocked"] * 4
    for name in ("Requirements", "Design"):
        assert pm.progress(chain[name], "Completed").status_code == 200
    assert pm.progress(chain["Development"], "In Progress").status_code == 200

    testing = pm.get(chain["Testing"])
    assert (testing["status"], testing["effective_status"]) == (
        "Not Started",
        "Blocked",
    )
    assert names(testing["blocked_by"]) == ["Development"]
    for status in ("In Progress", "Completed"):
        response = pm.progress(chain["Testing"], status)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "blocked"
        assert "Development" in message(response)
        assert pm.edit(testing, status=status).status_code == 409

    pm.progress(chain["Development"], "Completed")
    assert effective(pm, chain) == ["Completed"] * 3 + ["Not Started", "Blocked"]
    assert pm.progress(chain["Testing"], "In Progress").status_code == 200
    pm.progress(chain["Testing"], "Completed")
    assert pm.progress(chain["Deployment"], "Completed").status_code == 200
    assert effective(pm, chain) == ["Completed"] * 5


def test_only_the_unfinished_predecessors_are_listed(pm, world):
    first, second, last = (pm.add(world["mine"], name) for name in "ABC")
    pm.link(first, last)
    pm.link(second, last)
    pm.progress(first, "Completed")
    assert names(pm.get(last)["blocked_by"]) == ["B"]
    assert names(pm.get(last)["predecessors"]) == ["A", "B"]
    assert names(pm.get(first)["successors"]) == ["C"]


def test_blocked_filter_includes_both_kinds(pm, world, chain):
    pm.add(world["mine"], "Manual", status="Blocked")
    page = pm.ok("get", "/deliverables?status=Blocked&sort=name")
    assert names(page["items"]) == [
        "Deployment",
        "Design",
        "Development",
        "Manual",
        "Testing",
    ]
    assert names(pm.ok("get", "/deliverables?status=Not Started")["items"]) == [
        "Requirements"
    ]


def test_manually_blocked_stays_blocked(pm, world):
    item = pm.add(world["mine"], "A", status="Blocked", progress_percent=20)
    assert item["effective_status"] == "Blocked"
    assert item["blocked_by"] == []


def test_started_work_becomes_blocked_by_a_new_dependency(pm, world):
    first, second = (pm.add(world["mine"], name) for name in "AB")
    pm.progress(second, "In Progress", progress_percent=10)
    assert pm.link(first, second).json()["effective_status"] == "Blocked"
    assert pm.unlink(first, second).status_code == 204
    assert pm.get(second)["effective_status"] == "In Progress"


def test_reopening_is_refused_while_later_work_is_completed(pm, chain):
    for name in ("Requirements", "Design"):
        pm.progress(chain[name], "Completed")
    response = pm.progress(chain["Requirements"], "In Progress")
    assert response.status_code == 409
    assert "Design" in message(response)
    pm.progress(chain["Design"], "Not Started")
    assert pm.progress(chain["Requirements"], "In Progress").status_code == 200
    assert pm.get(chain["Design"])["effective_status"] == "Blocked"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ("Deployment", "Requirements"),
        ("Design", "Requirements"),
        ("Testing", "Design"),
    ],
)
def test_circular_dependencies_are_rejected(pm, chain, session, before, after):
    response = pm.link(chain[before], chain[after])
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "circular_dependency"
    assert fields(response) == ["predecessor_id"]
    link = DeliverableDependency
    assert session.scalar(select(func.count()).select_from(link)) == 4


def test_invalid_dependencies(pm, world, chain):
    same = chain["Design"]
    assert pm.link(same, same).status_code == 400
    assert pm.link({"id": 999999}, same).status_code == 400
    assert pm.link(chain["Requirements"], same).status_code == 409  # Duplicate
    assert pm.unlink(chain["Testing"], same).status_code == 404
    done = pm.add(world["mine"], "Done", status="Completed")
    assert pm.link(same, done).status_code == 409


def test_delete_is_refused_while_others_depend_on_it(pm, chain):
    url = f"/deliverables/{chain['Design']['id']}"
    response = pm.call("delete", url)
    assert response.status_code == 409
    pm.unlink(chain["Design"], chain["Development"])
    assert pm.call("delete", url).status_code == 204
    assert pm.get(chain["Development"])["effective_status"] == "Not Started"


def test_chain_is_returned_in_order(pm, world, chain):
    pm.add(world["mine"], "Independent")
    pm.link(chain["Requirements"], chain["Testing"])  # A shortcut
    answer = pm.ok("get", f"/projects/{world['mine']}/dependencies")
    steps = {item["deliverable"]["name"]: item["step"] for item in answer["nodes"]}
    expected = {name: number for number, name in enumerate(STAGES, 1)}
    assert steps == {**expected, "Independent": 1}
    by_key = {item["key"]: item["deliverable"]["name"] for item in answer["nodes"]}
    links = {
        (by_key[item["predecessor"]], by_key[item["successor"]])
        for item in answer["links"]
    }
    assert links == {
        *zip(STAGES, STAGES[1:], strict=False),
        ("Requirements", "Testing"),
    }


@pytest.fixture()
def saved_pair(migrated_engine):
    """Save First → Second for tests that need separate transactions."""
    with Session(migrated_engine) as setup:
        department = Department(name="Race")
        setup.add(department)
        setup.flush()
        project = Project(
            code="RACE",
            name="Race",
            department_id=department.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 1),
        )
        setup.add(project)
        setup.flush()
        rows = [
            Deliverable(
                project_id=project.id,
                name=name,
                start_date=date(2026, 1, 1),
                due_date=date(2026, 2, 1),
            )
            for name in ("First", "Second")
        ]
        setup.add_all(rows)
        setup.flush()
        ids = [row.id for row in rows]
        setup.add(DeliverableDependency(predecessor_id=ids[0], successor_id=ids[1]))
        project_id, department_id = project.id, department.id
        setup.commit()
    yield ids
    with Session(migrated_engine) as cleanup:
        cleanup.execute(delete(Project).where(Project.id == project_id))
        cleanup.execute(delete(Department).where(Department.id == department_id))
        cleanup.commit()


def set_status(engine, row_id, status):
    """Change a status in its own transaction."""
    with Session(engine) as own:
        row = own.get(Deliverable, row_id)
        update_progress(own, row, ProgressRequest(status=status))


def test_simultaneous_changes_keep_the_chain_consistent(migrated_engine, saved_pair):
    first, second = saved_pair

    def change(row_id, status):
        with Session(migrated_engine) as own:
            row = own.get(Deliverable, row_id)
            barrier.wait(5)
            try:
                update_progress(own, row, ProgressRequest(status=status))
                outcomes.append("saved")
            except ApiError:
                outcomes.append("refused")

    for _ in range(5):
        set_status(migrated_engine, second, "Not Started")
        set_status(migrated_engine, first, "Completed")
        outcomes, barrier = [], threading.Barrier(2)
        threads = [
            threading.Thread(target=change, args=args)
            for args in ((first, "In Progress"), (second, "Completed"))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sorted(outcomes) == ["refused", "saved"]


def test_outdated_copy_is_read_again_before_saving(migrated_engine, saved_pair):
    first, second = saved_pair
    with Session(migrated_engine) as slow:
        outdated = slow.get(Deliverable, first)
        assert outdated.status == "Not Started"
        # Meanwhile someone else completes both.
        set_status(migrated_engine, first, "Completed")
        set_status(migrated_engine, second, "Completed")
        with pytest.raises(ApiError):
            update_progress(slow, outdated, ProgressRequest(status="In Progress"))


# --- Dependencies between projects -----------------------------------------


def test_dependency_between_managed_projects(pm, world):
    first, second = pm.add(world["mine"], "A"), pm.add(world["second"], "B")
    assert pm.link(first, second).status_code == 201
    blocked = pm.get(second)
    assert blocked["effective_status"] == "Blocked"
    assert blocked["blocked_by"][0]["project_code"] == "MINE"
    answer = pm.ok("get", f"/projects/{world['second']}/dependencies")
    external = [item for item in answer["nodes"] if item["is_external"]]
    assert names(item["deliverable"] for item in external) == ["A"]


def test_manager_cannot_link_to_invisible_work(clients, pm, world):
    foreign = clients["admin"].add(world["other"], "Secret")
    own = pm.add(world["mine"], "Own")
    assert pm.link(foreign, own).status_code == 400
    assert pm.link(own, foreign).status_code == 404


def test_invisible_work_is_hidden(clients, pm, world):
    admin = clients["admin"]
    foreign, own = admin.add(world["other"], "Secret"), pm.add(world["mine"], "Own")
    assert admin.link(foreign, own).status_code == 201
    own = pm.get(own)
    assert own["effective_status"] == "Blocked"
    assert own["blocked_by"][0]["id"] is None
    answers = (
        pm.call("get", f"/deliverables/{own['id']}"),
        pm.call("get", "/deliverables"),
        pm.call("get", f"/projects/{world['mine']}/dependencies"),
        pm.progress(own, "In Progress"),
    )
    for answer in answers:
        assert "Secret" not in answer.text
        assert "OTHER" not in answer.text


def test_project_other_projects_wait_for_is_kept(clients, pm, world, session):
    pm.link(pm.add(world["mine"], "A"), pm.add(world["second"], "B"))
    session.get(Project, world["mine"]).status = "Cancelled"
    session.flush()
    url = f"/projects/{world['mine']}?confirm_code=MINE"
    response = clients["admin"].call("delete", url)
    assert response.status_code == 409
    assert "other projects" in message(response)


# --- Closed projects -------------------------------------------------------


def project_body(session, project_id, **changes):
    """Build an update request for an existing project."""
    row = session.get(Project, project_id)
    return {
        "code": row.code,
        "name": row.name,
        "department_id": row.department_id,
        "manager_id": row.manager_id,
        "start_date": str(row.start_date),
        "end_date": str(row.end_date),
        **changes,
    }


def test_project_cannot_be_completed_with_unfinished_work(pm, world, session):
    item = pm.add(world["mine"], "A")
    done = {"status": "Completed", "actual_completion_date": "2026-06-01"}
    body = project_body(session, world["mine"], **done)
    url = f"/projects/{world['mine']}"
    response = pm.call("put", url, body)
    assert (response.status_code, fields(response)) == (409, ["status"])
    pm.progress(item, "Completed")
    assert pm.call("put", url, body).status_code == 200


@pytest.mark.parametrize("status", ["Completed", "Cancelled"])
def test_closed_projects_accept_no_changes(pm, world, session, status):
    first, second = (pm.add(world["mine"], name) for name in "AB")
    pm.link(first, second)
    row = session.get(Project, world["mine"])
    row.status = status
    if status == "Completed":
        row.actual_completion_date = date(2026, 6, 1)
    session.flush()
    new = {"name": "C", "start_date": START, "due_date": DUE}
    milestone = {"name": "M", "due_date": DUE}
    answers = [
        pm.call("post", f"/projects/{world['mine']}/deliverables", new),
        pm.call("post", f"/projects/{world['mine']}/milestones", milestone),
        pm.edit(first, name="Changed"),
        pm.progress(first, "In Progress"),
        pm.link(second, first),
        pm.unlink(first, second),
        pm.call("delete", f"/deliverables/{second['id']}"),
    ]
    assert {answer.status_code for answer in answers} == {409}
    found = pm.get(first)
    assert (found["can_edit"], found["can_update"]) == (False, False)


# --- Milestones ------------------------------------------------------------


def test_milestone_crud_and_counts(pm, world, session):
    url = f"/projects/{world['mine']}/milestones"
    row = pm.ok("post", url, {"name": "Beta", "due_date": "2026-03-01"}, 201)
    assert row["is_overdue"] is True
    first = pm.add(world["mine"], "A", milestone_id=row["id"])
    pm.add(world["mine"], "B", milestone_id=row["id"], status="Completed")
    listed = pm.ok("get", url)["items"][0]
    assert (listed["deliverable_count"], listed["completed_count"]) == (2, 1)

    done = {"name": "Beta", "due_date": DUE, "completed_date": "2026-03-05"}
    response = pm.call("put", f"{url}/{row['id']}", done)
    assert (response.status_code, fields(response)) == (409, ["completed_date"])
    pm.edit(first, status="Completed", milestone_id=row["id"])
    assert pm.ok("put", f"{url}/{row['id']}", done)["is_overdue"] is False

    # Completed milestones accept no unfinished work.
    assert pm.progress(first, "In Progress").status_code == 409
    body = {"name": "C", "start_date": START, "due_date": DUE}
    body["milestone_id"] = row["id"]
    deliverables = f"/projects/{world['mine']}/deliverables"
    assert pm.call("post", deliverables, body).status_code == 409

    pm.ok("delete", f"{url}/{row['id']}", status=204)
    assert pm.get(first)["milestone"] is None
    assert session.scalar(select(func.count()).select_from(Milestone)) == 0


def test_milestone_of_another_project(pm, world):
    url = f"/projects/{world['second']}/milestones"
    row = pm.ok("post", url, {"name": "M", "due_date": DUE}, 201)
    body = {"name": "X", "start_date": START, "due_date": DUE}
    body["milestone_id"] = row["id"]
    response = pm.call("post", f"/projects/{world['mine']}/deliverables", body)
    assert (response.status_code, fields(response)) == (400, ["milestone_id"])
    wrong = f"/projects/{world['mine']}/milestones/{row['id']}"
    assert pm.call("delete", wrong).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [{"name": ""}, {"due_date": None}, {"completed_date": "2099-01-01"}],
)
def test_invalid_milestones(pm, world, changes):
    body = {"name": "M", "due_date": DUE, **changes}
    url = f"/projects/{world['mine']}/milestones"
    assert pm.call("post", url, body).status_code == 400


def test_duplicate_milestone(pm, world):
    url = f"/projects/{world['mine']}/milestones"
    body = {"name": "M", "due_date": DUE}
    pm.ok("post", url, body, 201)
    response = pm.call("post", url, body)
    assert (response.status_code, fields(response)) == (409, ["name"])


# --- Search ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", "CAB"),
        ("search=alpha", "A"),
        ("search=%25", ""),
        ("priority=High&priority=Low", "CB"),
        ("project_id={second}", "C"),
        ("owner_id={member}", "A"),
        ("status=In Progress", "B"),
        ("due_from=2026-05-01", "AB"),
        ("due_to=2026-05-01", "CA"),
        ("sort=name&order=desc", "CBA"),
        ("sort=priority", "CAB"),
        ("sort=progress&order=desc&limit=1", "B"),
        ("sort=name&limit=1&offset=1", "B"),
    ],
)
def test_search(pm, world, query, expected):
    pm.add(
        world["mine"],
        "A",
        description="Alpha",
        owner_id=world["member"],
        due_date="2026-05-01",
    )
    pm.add(
        world["mine"], "B", priority="High", status="In Progress", progress_percent=5
    )
    pm.add(world["second"], "C", priority="Low", due_date="2026-02-01")
    page = pm.ok("get", f"/deliverables?{query.format(**world)}")
    assert "".join(names(page["items"])) == expected


@pytest.mark.parametrize(
    "query", ["status=Nope", "sort=id", "overdue=maybe", "limit=0", "due_to=x"]
)
def test_invalid_filters(pm, query):
    assert pm.call("get", f"/deliverables?{query}").status_code == 400


# --- Roles -----------------------------------------------------------------


@pytest.fixture()
def owned(clients, world):
    """Create work for each access situation."""
    admin = clients["admin"]
    return {
        "own": admin.add(world["mine"], "Own", owner_id=world["member"]),
        "colleague": admin.add(world["mine"], "Colleague", owner_id=world["colleague"]),
        "foreign": admin.add(world["other"], "Foreign"),
    }


@pytest.mark.parametrize(
    ("role", "visible", "target", "read", "edit", "progress", "remove"),
    [
        ("admin", 3, "foreign", 200, 200, 200, 204),
        ("project_manager", 2, "colleague", 200, 200, 200, 204),
        ("project_manager", 2, "foreign", 404, 404, 404, 404),
        ("team_member", 1, "own", 200, 403, 200, 403),
        ("team_member", 1, "colleague", 404, 403, 404, 403),
        ("team_member", 1, "foreign", 404, 403, 404, 403),
    ],
)
def test_role_access(
    clients, owned, role, visible, target, read, edit, progress, remove
):
    client, item = clients[role], owned[target]
    assert client.ok("get", "/deliverables")["total"] == visible
    url = f"/deliverables/{item['id']}"
    assert client.call("get", url).status_code == read
    assert client.edit(item, name="Changed").status_code == edit
    assert client.progress(item, "In Progress").status_code == progress
    assert client.call("delete", url).status_code == remove


def test_team_member_is_refused_management(clients, owned, world):
    member = clients["team_member"]
    project = f"/projects/{world['mine']}"
    answers = [
        member.call("post", f"{project}/deliverables", {}),
        member.call("post", f"{project}/milestones", {}),
        member.call("get", f"{project}/dependencies"),
        member.link(owned["colleague"], owned["own"]),
        member.unlink(owned["colleague"], owned["own"]),
    ]
    assert {answer.status_code for answer in answers} == {403}
    assert member.call("get", f"{project}/milestones").status_code == 200
    other = f"/projects/{world['other']}/milestones"
    assert member.call("get", other).status_code == 404


def test_manager_only_updates_own_work_in_other_projects(
    clients, pm, people, session, world
):
    """A manager may own work in a project that someone else manages."""
    session.get(Resource, world["colleague"]).user_id = people["project_manager"][0].id
    session.flush()
    item = clients["admin"].add(world["other"], "Help", owner_id=world["colleague"])
    blocker = pm.add(world["mine"], "Blocker")
    assert pm.call("get", f"/deliverables/{item['id']}").status_code == 200
    assert pm.progress(item, "In Progress").status_code == 200
    assert pm.edit(item, name="Changed").status_code == 403
    assert pm.call("delete", f"/deliverables/{item['id']}").status_code == 403
    assert pm.link(blocker, item).status_code == 403
    assert pm.unlink(blocker, item).status_code == 403


def test_progress_update_cannot_change_other_fields(clients, owned):
    for name, value in (("name", "Hacked"), ("owner_id", None), ("due_date", DUE)):
        response = clients["team_member"].progress(
            owned["own"], "In Progress", **{name: value}
        )
        assert response.status_code == 400


def test_team_member_sees_what_blocks_their_work(clients, owned):
    clients["admin"].link(owned["colleague"], owned["own"])
    member = clients["team_member"]
    found = member.get(owned["own"])
    assert names(found["blocked_by"]) == ["Colleague"]
    assert (found["can_edit"], found["can_update"]) == (False, True)
    assert member.progress(owned["own"], "In Progress").status_code == 409


def test_options_depend_on_role(clients, owned, world):
    def owners(role, query=""):
        answer = clients[role].ok("get", f"/deliverables/options{query}")
        return names(answer["owners"])

    query = f"?project_id={world['mine']}"
    assert owners("project_manager", query) == ["Resource C", "Resource M"]
    assert owners("team_member", query) == ["Resource M"]
    other = f"/deliverables/options?project_id={world['other']}"
    assert clients["team_member"].call("get", other).status_code == 404
