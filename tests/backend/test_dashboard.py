"""Risk and dashboard tests through the real HTTP routes."""

import random
from datetime import timedelta
from decimal import Decimal

import pytest
from helpers import add_user
from sqlalchemy import select

from app.dates import today
from app.models import (
    AppSetting,
    Deliverable,
    DeliverableDependency,
    Department,
    Expense,
    ExpenseCategory,
    Milestone,
    Project,
    ProjectAssignment,
    Resource,
)
from app.services.risk import expected_progress, forecast_end

NOW = today()
STATUSES = ("Planned", "Active", "On Hold", "Completed", "Cancelled")
OPEN = STATUSES[:3]


def day(offset):
    """Return the date a number of days from today."""
    return NOW + timedelta(days=offset)


class World:
    """Creates records directly in the database."""

    def __init__(self, session, people):
        self.session = session
        self.manager = people["project_manager"][0]
        self.rival = add_user(session, "project_manager", "rival")
        self.department = self.save(Department(name="IT"))
        self.category = session.scalars(select(ExpenseCategory)).first()
        self.count = 0

    def save(self, row):
        self.session.add(row)
        self.session.flush()
        return row

    def next(self):
        self.count += 1
        return f"N{self.count:03}"

    def project(self, start=-10, end=89, **changes):
        code = self.next()
        values = {
            "code": code,
            "name": f"Project {code}",
            "department_id": self.department.id,
            "manager_id": self.manager.id,
            "start_date": day(start),
            "end_date": day(end),
            "status": "Active",
            "planned_budget": 1000,
            **changes,
        }
        if values["status"] == "Completed":
            values["actual_completion_date"] = max(values["start_date"], NOW)
        return self.save(Project(**values))

    def work(self, project, progress=100, due=50, start=-400, **changes):
        status = {0: "Not Started", 100: "Completed"}.get(progress, "In Progress")
        values = {
            "name": self.next(),
            "status": status,
            "progress_percent": progress,
            "start_date": day(start),
            "due_date": day(due),
            **changes,
        }
        if values["status"] == "Completed":
            values["completion_date"] = NOW
        return self.save(Deliverable(project_id=project.id, **values))

    def link(self, before, after):
        self.save(
            DeliverableDependency(predecessor_id=before.id, successor_id=after.id)
        )

    def spend(self, project, amount):
        self.save(
            Expense(
                project_id=project.id,
                category_id=self.category.id,
                amount=amount,
                expense_date=NOW,
                description="X",
            )
        )

    def person(self, capacity=100, **changes):
        code = self.next()
        values = {
            "employee_code": code,
            "full_name": f"Person {code}",
            "email": f"{code}@example.com",
            "department_id": self.department.id,
            "job_title": "X",
            "capacity_percent": capacity,
            **changes,
        }
        return self.save(Resource(**values))

    def assign(self, project, person, percent, start=-5, end=5):
        self.save(
            ProjectAssignment(
                project_id=project.id,
                resource_id=person.id,
                allocation_percent=percent,
                start_date=day(start),
                end_date=day(end),
            )
        )

    def set(self, key, value):
        self.session.get(AppSetting, key).value = Decimal(value)
        self.session.flush()


@pytest.fixture()
def world(session, people):
    """Return a record creator."""
    return World(session, people)


@pytest.fixture()
def get(api, people):
    """Return a function that reads as a role."""

    def read(url, role="project_manager", status=200):
        response = api.get(url, headers=people[role][1])
        assert response.status_code == status, response.text
        return response.json()

    return read


def risk(get, project):
    """Return a project's risk level and reasons by code."""
    found = get(f"/projects/{project.id}")["risk"]
    return found["level"], {row["code"]: row for row in found["reasons"]}


# --- Single rules, each on both sides of its limit -------------------------


def test_healthy_project_is_low(get, world):
    project = world.project()
    world.work(project)
    level, reasons = risk(get, project)
    assert (level, reasons) == ("Low", {})


@pytest.mark.parametrize(
    ("end", "late"), [(1, False), (0, False), (-1, True), (-30, True)]
)
@pytest.mark.parametrize("status", OPEN)
def test_deadline_passed(get, world, end, late, status):
    project = world.project(-100, end, status=status)
    world.work(project)
    level, reasons = risk(get, project)
    assert ("deadline_passed" in reasons) is late
    assert level == ("High" if late else "Low")
    if late:
        days = "1 day" if end == -1 else f"{-end} days"
        message = f"The deadline passed {days} ago."
        assert reasons["deadline_passed"]["message"] == message


@pytest.mark.parametrize(
    ("progress", "severity"),
    [(50, None), (36, None), (35, "Medium"), (21, "Medium"), (20, "High"), (0, "High")],
)
def test_behind_schedule(get, world, progress, severity):
    # 50 of 100 days have passed, so 50% is expected. The limit is 15%.
    project = world.project(-50, 49)
    world.work(project, progress)
    level, reasons = risk(get, project)
    found = reasons.get("behind_schedule")
    assert (found and found["severity"]) == severity
    assert level == (severity or "Low")
    if found:
        assert "50.0% was expected" in found["message"]


def test_behind_schedule_limit_is_configurable(get, world):
    project = world.project(-50, 49)
    world.work(project, 40)
    assert risk(get, project)[0] == "Low"
    world.set("schedule_lag_percent", 10)
    assert risk(get, project)[1]["behind_schedule"]["severity"] == "Medium"
    world.set("schedule_lag_percent", 5)
    assert risk(get, project)[1]["behind_schedule"]["severity"] == "High"


def test_zero_lag_does_not_flag_work_that_is_on_time(get, world):
    project = world.project(-50, 49)
    world.work(project, 50)
    world.set("schedule_lag_percent", 0)
    assert risk(get, project)[0] == "Low"


def test_future_projects_are_not_behind(get, world):
    assert risk(get, world.project(10, 50, status="Planned"))[0] == "Low"


@pytest.mark.parametrize(
    ("due", "status", "priority", "severity"),
    [
        (0, "In Progress", "High", None),
        (-1, "In Progress", "High", "Medium"),
        (-1, "Not Started", "Low", "Medium"),
        (-1, "In Progress", "Critical", "High"),
        (-1, "Completed", "Critical", None),
    ],
)
def test_overdue_deliverables(get, world, due, status, priority, severity):
    project = world.project()
    progress = {"Not Started": 0, "Completed": 100}.get(status, 50)
    world.work(project, progress, due, priority=priority)
    level, reasons = risk(get, project)
    found = reasons.get("overdue_deliverables")
    assert (found and found["severity"]) == severity
    assert level == (severity or "Low")


def test_overdue_message_counts_critical_work(get, world):
    project = world.project()
    world.work(project, 50, -1)
    world.work(project, 50, -1, priority="Critical")
    found = risk(get, project)[1]["overdue_deliverables"]
    assert found["message"] == "2 deliverables are overdue, 1 of them critical."


@pytest.mark.parametrize(("priority", "blocked"), [("Critical", True), ("High", False)])
@pytest.mark.parametrize("by_dependency", [True, False])
def test_critical_blocked(get, world, priority, blocked, by_dependency):
    project = world.project(0, 100)
    if by_dependency:
        item = world.work(project, 0, priority=priority, name="Core")
        world.link(world.work(project, 0), item)
    else:
        world.work(project, 0, priority=priority, name="Core", status="Blocked")
    level, reasons = risk(get, project)
    assert ("critical_blocked" in reasons) is blocked
    assert level == ("High" if blocked else "Low")
    if blocked:
        message = "Critical work is blocked: Core."
        assert reasons["critical_blocked"]["message"] == message


def test_unblocking_clears_the_risk(get, world, session):
    project = world.project(0, 100)
    before, after = world.work(project, 0), world.work(project, 0, priority="Critical")
    world.link(before, after)
    assert risk(get, project)[0] == "High"
    before.status, before.progress_percent = "Completed", 100
    before.completion_date = NOW
    session.flush()
    assert risk(get, project)[0] == "Low"


@pytest.mark.parametrize(
    ("planned", "spent", "code", "severity"),
    [
        (1000, "799.99", None, None),
        (1000, 800, "budget_warning", "Medium"),
        (1000, 1000, "budget_warning", "Medium"),
        (1000, "1000.01", "over_budget", "High"),
        (0, "0.01", "over_budget", "High"),
    ],
)
def test_budget(get, world, planned, spent, code, severity):
    project = world.project(planned_budget=planned)
    world.work(project)
    world.spend(project, Decimal(spent))
    level, reasons = risk(get, project)
    assert set(reasons) == ({code} if code else set())
    assert level == (severity or "Low")


@pytest.mark.parametrize(
    ("capacity", "here", "there", "dates", "over"),
    [
        (100, 50, 50, (-5, 5), False),
        (100, 50, 51, (-5, 5), True),
        (80, 60, 30, (-5, 5), True),
        (100, 70, 50, (6, 9), False),  # Over only if they overlapped
        (100, 70, 50, (5, 9), True),  # One shared day
        (100, 70, 50, (-9, -1), False),  # Already ended
    ],
)
def test_over_allocation(get, world, capacity, here, there, dates, over):
    project, other = world.project(), world.project()
    world.work(project)
    person = world.person(capacity)
    world.assign(project, person, here)
    world.assign(other, person, there, *dates)
    level, reasons = risk(get, project)
    assert ("over_allocated" in reasons) is over
    assert level == ("Medium" if over else "Low")


def test_over_allocation_after_leaving_does_not_count(get, world):
    """Another project's later overload is not this project's risk."""
    project, second, third = (world.project() for _ in range(3))
    for row in (project, second, third):
        world.work(row)
    person = world.person()
    world.assign(project, person, 50, -5, 5)
    world.assign(second, person, 70, 10, 20)
    world.assign(third, person, 70, 10, 20)
    assert risk(get, project)[0] == "Low"
    assert risk(get, second)[0] == risk(get, third)[0] == "Medium"


def test_closed_projects_do_not_overload_people(get, world):
    project = world.project()
    world.work(project)
    person = world.person()
    world.assign(project, person, 70)
    world.assign(world.project(status="Cancelled"), person, 70)
    assert risk(get, project)[0] == "Low"


# --- Levels ----------------------------------------------------------------


def test_every_reason_is_returned_most_severe_first(get, world):
    project = world.project(-50, 49, planned_budget=100)
    world.spend(project, 90)
    world.work(project, 0, -1, priority="Critical", status="Blocked")
    person = world.person(10)
    world.assign(project, person, 20)
    found = get(f"/projects/{project.id}")["risk"]
    assert found["level"] == "High"
    assert [row["code"] for row in found["reasons"]] == [
        "behind_schedule",
        "overdue_deliverables",
        "critical_blocked",
        "budget_warning",
        "over_allocated",
    ]
    assert [row["severity"] for row in found["reasons"]] == ["High"] * 3 + [
        "Medium"
    ] * 2


@pytest.mark.parametrize("status", ["Completed", "Cancelled"])
def test_closed_projects_have_no_risk(get, world, status):
    project = world.project(-50, -10, status=status)
    world.spend(project, 5000)
    assert get(f"/projects/{project.id}")["risk"] is None
    board = get("/dashboard")
    assert board["projects"]["at_risk"] == board["projects"]["overdue"] == 0


def test_same_data_gives_the_same_answer(get, world):
    project = world.project(-50, 49)
    world.work(project, 10)
    answers = [get(f"/projects/{project.id}")["risk"] for _ in range(3)]
    assert answers[0] == answers[1] == answers[2]


# --- Expected progress and forecast ----------------------------------------


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-9, 0), (0, 0), (1, 10), (5, 50), (9, 90), (10, 100), (99, 100)],
)
def test_expected_progress(offset, expected):
    assert expected_progress(day(0), day(9), day(offset)) == expected


@pytest.mark.parametrize(
    ("elapsed", "progress", "last"),
    [
        (10, 50, 19),
        (10, 100, None),
        (10, 0, None),
        (0, 50, None),
        (10, 33, 30),
        (10, "0.1", None),  # Too far away to be useful
        (1, 99, 1),
    ],
)
def test_forecast(elapsed, progress, last):
    found = forecast_end(day(0), Decimal(progress), day(elapsed))
    assert found == (None if last is None else day(last))


def test_forecast_is_returned(get, world):
    project = world.project(-10, 89)
    world.work(project, 50)
    found = get(f"/projects/{project.id}")["risk"]
    assert found["forecast_end_date"] == str(day(9))
    assert found["expected_progress_percent"] == 10


# --- Filters and lists agree -----------------------------------------------


def test_risk_filter(get, world):
    low, medium, high = (world.project() for _ in range(3))
    world.work(low)
    world.work(medium, 50, -1)
    world.work(high, 50, -1, priority="Critical")
    world.project(status="Cancelled")
    for level, project in (("Low", low), ("Medium", medium), ("High", high)):
        page = get(f"/projects?risk={level}")
        assert [row["code"] for row in page["items"]] == [project.code]
        assert page["items"][0]["risk"]["level"] == level
    assert get("/projects?risk=High&risk=Medium")["total"] == 2
    get("/projects?risk=Huge", status=400)


def test_risk_is_hidden_from_viewers(get, world, people):
    project = world.project(-50, -1, manager_id=world.rival.id)
    for role in ("project_manager", "team_member"):
        person = world.person(user_id=people[role][0].id)
        world.assign(project, person, 10)
        assert get(f"/projects/{project.id}", role)["risk"] is None
        assert get("/projects", role)["items"][0]["risk"] is None
        assert get("/projects?risk=High", role)["total"] == 0
    assert get(f"/projects/{project.id}", "admin")["risk"]["level"] == "High"


def test_filter_choices_depend_on_role(get):
    assert get("/projects/options", "admin")["risk_levels"] == ["High", "Medium", "Low"]
    assert get("/projects/options", "team_member")["risk_levels"] == []


# --- Dashboard -------------------------------------------------------------


def test_team_members_have_no_dashboard(get):
    get("/dashboard", "team_member", 403)


def test_empty_dashboard(get):
    board = get("/dashboard")
    assert board["projects"]["total"] == board["deadline_count"] == 0
    assert board["deliverables"]["completion_percent"] is None
    assert board["resources"]["utilization_percent"] is None
    assert board["budget"]["consumed_percent"] is None
    assert board["risky_projects"] == board["deadlines"] == []


def test_manager_only_sees_own_projects(get, world):
    world.work(world.project())
    other = world.project(-50, -1, manager_id=world.rival.id, planned_budget=77)
    world.work(other, 50, 1, name="Secret")
    own, every = get("/dashboard"), get("/dashboard", "admin")
    assert (own["projects"]["total"], every["projects"]["total"]) == (1, 2)
    assert (own["deliverables"]["total"], every["deliverables"]["total"]) == (1, 2)
    assert (own["budget"]["planned"], every["budget"]["planned"]) == (
        "1000.00",
        "1077.00",
    )
    assert "Secret" not in str(own)
    assert other.code not in str(own)
    assert every["projects"]["at_risk"] == 1


@pytest.mark.parametrize(
    ("offset", "shown"), [(-1, False), (0, True), (14, True), (15, False)]
)
def test_upcoming_deadlines(get, world, offset, shown):
    project = world.project(-10, offset) if offset >= 0 else world.project()
    milestone = {"name": "M", "due_date": day(offset)}
    world.save(Milestone(project_id=project.id, **milestone))
    world.work(project, 50, offset)
    kinds = {row["kind"]: row["days_left"] for row in get("/dashboard")["deadlines"]}
    expected = {"Project", "Milestone", "Deliverable"} if shown else set()
    assert set(kinds) == expected
    assert set(kinds.values()) <= {offset}


def test_finished_work_has_no_deadline(get, world):
    project = world.project()
    world.work(project, 100, 3)
    world.save(
        Milestone(project_id=project.id, name="M", due_date=day(3), completed_date=NOW)
    )
    closed = world.project(-10, 3, status="Cancelled")
    world.work(closed, 50, 3)
    assert get("/dashboard")["deadline_count"] == 0


def test_upcoming_days_are_configurable(get, world):
    world.project(-10, 20)
    assert get("/dashboard")["deadline_count"] == 0
    world.set("upcoming_deadline_days", 20)
    board = get("/dashboard")
    assert (board["deadline_count"], board["upcoming_days"]) == (1, 20)


def test_long_lists_are_cut_but_counted(get, world):
    for offset in range(25):
        world.project(-400 - offset, -1)
    project = world.project()
    for _ in range(25):
        world.work(project, 50, 5)
    board = get("/dashboard")
    assert (board["projects"]["at_risk"], len(board["risky_projects"])) == (25, 10)
    assert (board["deadline_count"], len(board["deadlines"])) == (25, 20)


def test_risky_projects_are_ordered(get, world):
    later = world.project(-50, 60)
    world.work(later, 99, -1, priority="Critical")
    medium = world.project(-50, 10)
    world.work(medium, 99, -1)
    late = world.project(-50, -5)
    board = get("/dashboard")
    codes = [row["code"] for row in board["risky_projects"]]
    assert codes == [late.code, later.code, medium.code]
    assert board["projects"]["by_risk"] == {"High": 2, "Medium": 1, "Low": 0}


def test_every_figure_matches_the_records(get, world, session):
    """Recalculate every figure from the rows, without the application's code."""
    rng = random.Random(11)
    categories = session.scalars(select(ExpenseCategory)).all()
    people = [
        world.person(
            rng.choice([0, 50, 80, 100]),
            availability=rng.choice(["Available", "On Leave"]),
        )
        for _ in range(8)
    ]
    for _ in range(30):
        start = rng.randint(-120, 20)
        project = world.project(
            start,
            start + rng.randint(5, 200),
            status=rng.choice(STATUSES),
            planned_budget=rng.choice([0, 500, 1000, 5000]),
            manager_id=rng.choice([world.manager.id, world.rival.id]),
        )
        items = []
        for _ in range(rng.randint(0, 5)):
            items.append(
                world.work(
                    project,
                    rng.choice([0, 0, 40, 80, 100]),
                    rng.randint(-30, 40),
                    priority=rng.choice(["Low", "High", "Critical"]),
                    estimated_hours=rng.choice([0, 10, 25]),
                )
            )
        for before, after in zip(items, items[1:], strict=False):
            if rng.random() < 0.4 and after.status == "Not Started":
                world.link(before, after)
        for _ in range(rng.randint(0, 3)):
            session.add(
                Expense(
                    project_id=project.id,
                    category_id=rng.choice(categories).id,
                    amount=Decimal(rng.randint(1, 60000)) / 100,
                    expense_date=NOW,
                    description="X",
                )
            )
        for person in rng.sample(people, rng.randint(0, 3)):
            first = rng.randint(-20, 20)
            world.assign(
                project, person, rng.randint(5, 60), first, first + rng.randint(0, 40)
            )
        world.save(
            Milestone(
                project_id=project.id,
                name="M",
                due_date=day(rng.randint(-20, 30)),
                completed_date=rng.choice([None, NOW]),
            )
        )
    # Random data is mostly unhealthy, so add some healthy projects.
    for manager in (world.manager, world.rival) * 2:
        healthy = world.project(0, 60, manager_id=manager.id)
        world.work(healthy, 50, 30)
    session.flush()
    session.expire_all()

    projects = session.scalars(select(Project)).all()
    work = session.scalars(select(Deliverable)).all()
    links = session.scalars(select(DeliverableDependency)).all()
    expenses = session.scalars(select(Expense)).all()
    milestones = session.scalars(select(Milestone)).all()
    spans = session.scalars(select(ProjectAssignment)).all()
    by_id = {row.id: row for row in work}
    owner = {row.id: row for row in projects}

    def status(row):
        waits = any(
            by_id[link.predecessor_id].status != "Completed"
            for link in links
            if link.successor_id == row.id
        )
        return "Blocked" if waits and row.status != "Completed" else row.status

    def late(row):
        return (
            row.status != "Completed"
            and row.due_date < NOW
            and owner[row.project_id].status != "Cancelled"
        )

    def spent(row):
        return sum((e.amount for e in expenses if e.project_id == row.id), Decimal(0))

    def load(person_id, when):
        return sum(
            (
                span.allocation_percent
                for span in spans
                if span.resource_id == person_id
                and span.start_date <= when <= span.end_date
                and owner[span.project_id].status in OPEN
            ),
            Decimal(0),
        )

    def progress(row):
        own = [item for item in work if item.project_id == row.id]
        if not own:
            return Decimal(100 if row.status == "Completed" else 0)
        hours = [item.estimated_hours for item in own]
        weights = hours if min(hours) > 0 else [Decimal(1)] * len(own)
        pairs = zip(own, weights, strict=True)
        total = sum((i.progress_percent * w for i, w in pairs), Decimal(0))
        return total / sum(weights)

    def level(row):
        own = [item for item in work if item.project_id == row.id]
        late_work = [item for item in own if late(item)]
        high = medium = False
        if row.end_date < NOW:
            high = True
        else:
            length = (row.end_date - row.start_date).days + 1
            passed = max((NOW - row.start_date).days, 0)
            wanted = round(Decimal(passed * 100) / length, 1)
            gap = wanted - round(progress(row), 1)
            high |= gap >= 30
            medium |= gap >= 15
        high |= any(item.priority == "Critical" for item in late_work)
        medium |= bool(late_work)
        high |= any(i.priority == "Critical" and status(i) == "Blocked" for i in own)
        high |= spent(row) > row.planned_budget
        medium |= row.planned_budget > 0 and spent(row) * 100 >= row.planned_budget * 80
        for span in spans:
            if span.project_id == row.id and span.end_date >= NOW:
                capacity = next(
                    p.capacity_percent for p in people if p.id == span.resource_id
                )
                first = max(span.start_date, NOW)
                days = range((span.end_date - first).days + 1)
                medium |= any(
                    load(span.resource_id, first + timedelta(days=d)) > capacity
                    for d in days
                )
        return "High" if high else "Medium" if medium else "Low"

    for role in ("admin", "project_manager"):
        mine = [
            row
            for row in projects
            if role == "admin" or row.manager_id == world.manager.id
        ]
        ids = {row.id for row in mine}
        board = get("/dashboard", role)
        metrics = board["projects"]
        assert metrics["total"] == len(mine) > 10
        assert metrics["by_status"] == {
            name: sum(row.status == name for row in mine) for name in STATUSES
        }
        assert metrics["overdue"] == sum(
            row.status in OPEN and row.end_date < NOW for row in mine
        )
        levels = {row.id: level(row) for row in mine if row.status in OPEN}
        expected = {
            name: sum(value == name for value in levels.values())
            for name in ("High", "Medium", "Low")
        }
        assert metrics["by_risk"] == expected
        assert all(expected.values()), "The data must cover every level"
        assert metrics["at_risk"] == expected["High"] + expected["Medium"]
        for name, count in expected.items():
            page = get(f"/projects?risk={name}&limit=100", role)
            assert page["total"] == count
            assert {row["id"] for row in page["items"]} == {
                key for key, value in levels.items() if value == name
            }
        for key, value in levels.items():
            assert get(f"/projects/{key}", role)["risk"]["level"] == value

        counted = [
            row
            for row in work
            if row.project_id in ids and owner[row.project_id].status != "Cancelled"
        ]
        figures = board["deliverables"]
        done = sum(row.status == "Completed" for row in counted)
        assert (figures["total"], figures["completed"]) == (len(counted), done)
        assert figures["pending"] == len(counted) - done
        assert figures["overdue"] == sum(late(row) for row in counted)
        assert figures["completion_percent"] == pytest.approx(
            done * 100 / len(counted), abs=0.05
        )
        for name, count in figures["by_status"].items():
            assert count == sum(status(row) == name for row in counted)

        planned = sum((row.planned_budget for row in mine), Decimal(0))
        actual = sum((spent(row) for row in mine), Decimal(0))
        money = board["budget"]
        assert Decimal(money["planned"]) == planned
        assert Decimal(money["actual"]) == actual
        assert Decimal(money["remaining"]) == planned - actual
        assert money["consumed_percent"] == pytest.approx(
            float(actual * 100 / planned), abs=0.05
        )
        over = sum(spent(row) > row.planned_budget for row in mine)
        assert money["by_status"]["Over Budget"] == over

        horizon = range(0, 61)
        peaks = {p.id: max(load(p.id, day(d)) for d in horizon) for p in people}
        staff = board["resources"]
        assert staff["total"] == len(people)
        assert staff["over_allocated"] == sum(
            peaks[p.id] > p.capacity_percent for p in people
        )
        assert staff["needs_cover"] == sum(
            p.availability != "Available" and load(p.id, NOW) > 0 for p in people
        )
        capacity = sum(p.capacity_percent for p in people)
        assert staff["capacity_percent"] == float(capacity)
        assert staff["peak_percent"] == float(sum(peaks.values()))
        assert staff["utilization_percent"] == pytest.approx(
            float(sum(peaks.values()) * 100 / capacity), abs=0.05
        )

        soon = [
            date_
            for date_ in (
                [row.end_date for row in mine if row.status in OPEN]
                + [
                    row.due_date
                    for row in milestones
                    if row.project_id in ids
                    and owner[row.project_id].status in OPEN
                    and row.completed_date is None
                ]
                + [
                    row.due_date
                    for row in work
                    if row.project_id in ids
                    and owner[row.project_id].status in OPEN
                    and row.status != "Completed"
                ]
            )
            if NOW <= date_ <= day(14)
        ]
        assert board["deadline_count"] == len(soon)
        shown = [row["due_date"] for row in board["deadlines"]]
        assert shown == [str(value) for value in sorted(soon)[:20]]
