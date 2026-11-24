"""Budget and expense tests through the real HTTP routes."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from helpers import add_user
from sqlalchemy import func, select

from app.dates import today
from app.models import Department, Expense, ExpenseCategory, Project

SPENT_ON = "2026-03-10"


@pytest.fixture()
def world(session, people):
    """Create two managed projects and one of another manager."""
    department = Department(name="IT")
    session.add(department)
    session.flush()
    rival = add_user(session, "project_manager", "rival")
    manager = people["project_manager"][0]
    ids = {"department": department.id, "manager": manager.id, "rival": rival.id}
    for code, owner in (("A", manager), ("B", manager), ("OTHER", rival)):
        row = Project(
            code=code,
            name=f"Project {code}",
            department_id=department.id,
            manager_id=owner.id,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="Active",
            planned_budget=Decimal(100000),
        )
        session.add(row)
        session.flush()
        ids[code] = row.id
    for row in session.scalars(select(ExpenseCategory)):
        ids[row.name] = row.id
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

    def body(self, amount, **changes):
        return {
            "category_id": self.world["Software"],
            "amount": str(amount),
            "expense_date": SPENT_ON,
            "description": "Licences",
            **changes,
        }

    def spend(self, amount, project="A", **changes):
        url = f"/projects/{self.world[project]}/expenses"
        return self.ok("post", url, self.body(amount, **changes), 201)

    def budget(self, project="A"):
        return self.ok("get", f"/projects/{self.world[project]}/budget")


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


def plan(session, world, amount, project="A"):
    """Set a project's planned budget."""
    session.get(Project, world[project]).planned_budget = Decimal(amount)
    session.flush()


# --- Calculations ----------------------------------------------------------


@pytest.mark.parametrize(
    ("planned", "expenses", "actual", "remaining", "percent", "status"),
    [
        # The workshop example
        ("100000", [25000, 30000, 20000], "75000.00", "25000.00", 75, "On Track"),
        ("100000", [], "0.00", "100000.00", 0, "On Track"),
        # The warning starts at 80%
        ("100000", ["79999.99"], "79999.99", "20000.01", 80, "On Track"),
        ("100000", [80000], "80000.00", "20000.00", 80, "Warning"),
        # Exactly the plan is not over budget, one cent more is
        ("100000", [60000, 40000], "100000.00", "0.00", 100, "Warning"),
        ("100000", [100000, "0.01"], "100000.01", "-0.01", 100, "Over Budget"),
        ("100000", [75000, 50000], "125000.00", "-25000.00", 125, "Over Budget"),
        # Nothing planned
        ("0", [], "0.00", "0.00", None, "No Budget"),
        ("0", ["0.01"], "0.01", "-0.01", None, "Over Budget"),
        # Exact decimals: floating point would give 0.30000000000000004
        ("0.30", ["0.10", "0.20"], "0.30", "0.00", 100, "Warning"),
        ("1", ["0.10"] * 3, "0.30", "0.70", 30, "On Track"),
        ("3", [1], "1.00", "2.00", 33.3, "On Track"),
        ("800", ["1"], "1.00", "799.00", 0.1, "On Track"),
        # The largest amounts
        (
            "999999999999.99",
            ["999999999999.99", "0.01"],
            "1000000000000.00",
            "-0.01",
            100,
            "Over Budget",
        ),
    ],
)
def test_calculations(
    pm, session, world, planned, expenses, actual, remaining, percent, status
):
    plan(session, world, planned)
    for amount in expenses:
        pm.spend(amount)
    expected = {
        "planned": str(Decimal(planned).quantize(Decimal("0.01"))),
        "actual": actual,
        "remaining": remaining,
        "consumed_percent": percent,
        "status": status,
    }

    def check(budget):
        assert {key: budget[key] for key in expected} == expected

    check(pm.budget())
    check(pm.ok("get", f"/projects/{world['A']}")["budget"])
    check(pm.ok("get", "/projects?search=Project A")["items"][0]["budget"])
    row = pm.ok("get", "/budgets?search=Project A")
    check(row["items"][0]["budget"])
    # The SQL status used by the filters must agree.
    assert row["by_status"][status] == 1
    for name in ("On Track", "Warning", "Over Budget", "No Budget"):
        for url in ("/budgets", "/projects"):
            page = pm.ok("get", f"{url}?search=Project A&budget_status={name}")
            assert page["total"] == int(name == status)


def test_every_change_updates_the_budget(pm):
    first = pm.spend(25000)
    assert first["budget"]["actual"] == "25000.00"
    second = pm.spend(90000)
    assert second["budget"]["status"] == "Over Budget"
    assert second["budget"]["remaining"] == "-15000.00"
    url = f"/expenses/{second['expense']['id']}"
    edited = pm.ok("put", url, pm.body(30000))
    assert edited["budget"]["actual"] == "55000.00"
    assert edited["budget"]["status"] == "On Track"
    pm.ok("delete", url, status=204)
    assert pm.budget()["actual"] == "25000.00"
    assert pm.budget("B")["actual"] == "0.00"


def test_changing_the_plan_changes_the_status(pm, session, world):
    pm.spend(75000)
    plan(session, world, 50000)
    budget = pm.budget()
    assert (budget["status"], budget["consumed_percent"]) == ("Over Budget", 150)


def test_warning_threshold_is_configurable(pm, admin):
    pm.spend(75000)
    assert pm.budget()["status"] == "On Track"
    admin.ok("put", "/settings/budget_warning_percent", {"value": 75})
    budget = pm.budget()
    assert (budget["status"], budget["warning_percent"]) == ("Warning", 75)


def test_spending_by_category_and_month(pm, world):
    pm.spend(50000, expense_date="2026-01-31")
    pm.spend(25000, category_id=world["Travel"], expense_date="2026-02-01")
    pm.spend(5000, category_id=world["Travel"], expense_date="2026-01-01")
    budget = pm.budget()
    assert budget["expense_count"] == 3
    rows = [
        (row["category"]["name"], row["amount"], row["share_percent"])
        for row in budget["categories"]
    ]
    assert rows == [("Software", "50000.00", 62.5), ("Travel", "30000.00", 37.5)]
    months = [(row["month"], row["amount"]) for row in budget["months"]]
    assert months == [("2026-01", "55000.00"), ("2026-02", "25000.00")]


# --- Expense CRUD ----------------------------------------------------------


def test_crud(pm, session, world):
    saved = pm.spend("1234.56", category_id=world["Travel"])["expense"]
    assert saved["amount"] == "1234.56"
    assert saved["category"]["name"] == "Travel"
    assert saved["project"]["code"] == "A"
    assert saved["created_by"]["name"] == "project_manager"
    url = f"/expenses/{saved['id']}"
    assert pm.ok("get", url) == saved

    changes = pm.body(
        "99.90",
        category_id=world["Training"],
        expense_date="2026-04-01",
        description="Course",
    )
    pm.ok("put", url, changes)
    session.expire_all()
    row = session.get(Expense, saved["id"])
    assert (row.amount, row.category_id) == (Decimal("99.90"), world["Training"])
    assert (row.expense_date, row.description) == (date(2026, 4, 1), "Course")
    assert row.project_id == world["A"]

    pm.ok("delete", url, status=204)
    assert pm.call("get", url).status_code == 404
    assert session.scalar(select(func.count()).select_from(Expense)) == 0


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"amount": 0}, "body.amount"),
        ({"amount": -1}, "body.amount"),
        ({"amount": "0.001"}, "body.amount"),
        ({"amount": "1000000000000"}, "body.amount"),
        ({"amount": "NaN"}, "body.amount"),
        ({"amount": "Infinity"}, "body.amount"),
        ({"amount": "abc"}, "body.amount"),
        ({"amount": None}, "body.amount"),
        ({"expense_date": "nope"}, "body.expense_date"),
        ({"expense_date": "1999-12-31"}, "body.expense_date"),
        (
            {"expense_date": str(today() + timedelta(days=2))},
            "body.expense_date",
        ),
        ({"description": "  "}, "body.description"),
        ({"description": "X" * 2001}, "body.description"),
        ({"category_id": 999999}, "category_id"),
        ({"project_id": 1}, "body.project_id"),
        ({"created_by_id": 1}, "body.created_by_id"),
    ],
)
def test_invalid_expenses(pm, session, world, changes, field):
    url = f"/projects/{world['A']}/expenses"
    response = pm.call("post", url, pm.body(10) | changes)
    assert response.status_code == 400, response.text
    assert field in fields(response)
    assert session.scalar(select(func.count()).select_from(Expense)) == 0


@pytest.mark.parametrize("status", ["Planned", "On Hold", "Completed", "Cancelled"])
def test_late_invoices_are_accepted(pm, session, world, status):
    row = session.get(Project, world["A"])
    row.status = status
    if status == "Completed":
        row.actual_completion_date = date(2026, 6, 1)
    session.flush()
    assert pm.spend(10)["budget"]["actual"] == "10.00"


def test_project_with_expenses_is_kept(pm, admin, session, world):
    saved = pm.spend(10)["expense"]
    session.get(Project, world["A"]).status = "Cancelled"
    session.flush()
    url = f"/projects/{world['A']}?confirm_code=A"
    assert admin.call("delete", url).status_code == 409
    pm.ok("delete", f"/expenses/{saved['id']}", status=204)
    assert admin.call("delete", url).status_code == 204


# --- Expense search --------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected", "total"),
    [
        ("", "321", "60.60"),
        ("search=HOTEL", "2", "20.20"),
        ("search=%25", "", "0.00"),
        ("project_id={B}", "3", "30.30"),
        ("category_id={Travel}", "32", "50.50"),
        ("date_from=2026-02-01", "32", "50.50"),
        ("date_to=2026-02-01", "21", "30.30"),
        ("date_from=2026-02-01&date_to=2026-02-28", "2", "20.20"),
        ("amount_min=20.20", "32", "50.50"),
        ("amount_max=20.20", "21", "30.30"),
        ("sort=amount&order=asc", "123", "60.60"),
        ("sort=category&order=asc", "123", "60.60"),
        ("sort=project&order=desc", "312", "60.60"),
        ("sort=amount&limit=1", "3", "60.60"),
        ("sort=amount&limit=1&offset=1", "2", "60.60"),
    ],
)
def test_expense_search(pm, world, query, expected, total):
    pm.spend("10.10", description="1 server", expense_date="2026-01-15")
    travel = world["Travel"]
    pm.spend(
        "20.20", description="2 Hotel", expense_date="2026-02-01", category_id=travel
    )
    pm.spend(
        "30.30",
        "B",
        description="3 train",
        expense_date="2026-03-01",
        category_id=travel,
    )
    page = pm.ok("get", f"/expenses?{query.format(**world)}")
    assert "".join(item["description"][0] for item in page["items"]) == expected
    assert page["total_amount"] == total


@pytest.mark.parametrize(
    "query",
    ["sort=id", "limit=0", "amount_min=-1", "amount_min=x", "date_from=x"],
)
def test_invalid_expense_filters(pm, query):
    assert pm.call("get", f"/expenses?{query}").status_code == 400


# --- Budget list -----------------------------------------------------------


@pytest.fixture()
def spread(admin, pm, session, world):
    """Spend different shares of three budgets."""
    plan(session, world, "0", "OTHER")
    pm.spend(120000, "A")
    pm.spend(50000, "B")
    session.get(Project, world["B"]).status = "On Hold"
    session.flush()
    return world


@pytest.mark.parametrize(
    ("query", "codes"),
    [
        ("", ["A", "B", "OTHER"]),
        ("budget_status=Over Budget", ["A"]),
        ("budget_status=On Track&budget_status=No Budget", ["B", "OTHER"]),
        ("budget_status=Warning", []),
        ("project_status=On Hold", ["B"]),
        ("manager_id={rival}", ["OTHER"]),
        ("department_id={department}&search=project b", ["B"]),
        ("sort=code&order=desc", ["OTHER", "B", "A"]),
        ("sort=planned&order=asc", ["OTHER", "A", "B"]),
        ("sort=actual", ["A", "B", "OTHER"]),
        ("sort=remaining&order=asc", ["A", "OTHER", "B"]),
        ("sort=name&order=asc&limit=1&offset=1", ["B"]),
    ],
)
def test_budget_list(admin, spread, query, codes):
    page = admin.ok("get", f"/budgets?{query.format(**spread)}")
    found = [item["code"] for item in page["items"]]
    if "sort" in query or not found:
        assert found == codes
    assert sorted(found) == sorted(codes)


def test_budget_totals(admin, pm, spread):
    page = admin.ok("get", "/budgets?limit=1")
    assert (page["total"], len(page["items"])) == (3, 1)
    assert page["items"][0]["code"] == "A"  # Highest consumption first
    assert (page["planned"], page["actual"]) == ("200000.00", "170000.00")
    assert (page["remaining"], page["consumed_percent"]) == ("30000.00", 85)
    assert page["by_status"] == {
        "On Track": 1,
        "Warning": 0,
        "Over Budget": 1,
        "No Budget": 1,
    }
    own = pm.ok("get", "/budgets")
    assert (own["total"], own["by_status"]["No Budget"]) == (2, 0)
    empty = admin.ok("get", "/budgets?search=nothing")
    assert (empty["planned"], empty["consumed_percent"]) == ("0.00", None)


def test_spending_without_a_plan_ranks_first(admin, spread):
    admin.spend(1, "OTHER")
    page = admin.ok("get", "/budgets?sort=consumed&order=desc")
    assert [item["code"] for item in page["items"]] == ["OTHER", "A", "B"]


@pytest.mark.parametrize("query", ["budget_status=Bad", "sort=x", "limit=101"])
def test_invalid_budget_filters(pm, query):
    assert pm.call("get", f"/budgets?{query}").status_code == 400


# --- Categories ------------------------------------------------------------


def test_category_crud(admin, pm, session):
    created = admin.ok("post", "/expense-categories", {"name": "Legal"}, 201)
    url = f"/expense-categories/{created['id']}"
    admin.ok("put", url, {"name": "Legal fees"})
    expense = pm.spend(5, category_id=created["id"])["expense"]
    page = pm.ok("get", "/expense-categories")
    counts = {item["name"]: item["expense_count"] for item in page["items"]}
    assert (counts["Legal fees"], counts["Travel"], len(counts)) == (1, 0, 8)
    response = admin.call("delete", url)
    assert response.status_code == 409
    assert "used by expenses" in response.json()["error"]["message"]
    pm.ok("delete", f"/expenses/{expense['id']}", status=204)
    admin.ok("delete", url, status=204)
    assert session.get(ExpenseCategory, created["id"]) is None
    assert admin.call("delete", url).status_code == 404


@pytest.mark.parametrize("name", ["", "  ", "X" * 81])
def test_invalid_categories(admin, name):
    body = {"name": name}
    assert admin.call("post", "/expense-categories", body).status_code == 400


@pytest.mark.parametrize("name", ["Travel", "TRAVEL", " travel "])
def test_duplicate_categories(admin, name):
    response = admin.call("post", "/expense-categories", {"name": name})
    assert (response.status_code, fields(response)) == (409, ["name"])


# --- Roles -----------------------------------------------------------------


def test_team_member_is_refused_everywhere(clients, pm, world):
    expense = pm.spend(10)["expense"]
    member = clients["team_member"]
    calls = [
        ("get", "/budgets"),
        ("get", f"/projects/{world['A']}/budget"),
        ("get", "/expenses"),
        ("get", "/expenses/options"),
        ("get", "/expense-categories"),
        ("post", "/expense-categories"),
        ("put", f"/expense-categories/{world['Travel']}"),
        ("delete", f"/expense-categories/{world['Travel']}"),
        ("post", f"/projects/{world['A']}/expenses"),
        ("get", f"/expenses/{expense['id']}"),
        ("put", f"/expenses/{expense['id']}"),
        ("delete", f"/expenses/{expense['id']}"),
    ]
    answers = {member.call(method, url, {}).status_code for method, url in calls}
    assert answers == {403}
    assert pm.budget()["actual"] == "10.00"


def test_manager_cannot_reach_other_projects(admin, pm, world):
    expense = admin.spend(10, "OTHER")["expense"]
    url = f"/expenses/{expense['id']}"
    project = f"/projects/{world['OTHER']}"
    answers = [
        pm.call("get", url),
        pm.call("put", url, pm.body(1)),
        pm.call("delete", url),
        pm.call("get", f"{project}/budget"),
        pm.call("post", f"{project}/expenses", pm.body(1)),
    ]
    assert {answer.status_code for answer in answers} == {404}
    assert pm.ok("get", "/expenses")["total_amount"] == "0.00"
    assert pm.ok("get", f"/expenses?project_id={world['OTHER']}")["total"] == 0
    codes = {item["code"] for item in pm.ok("get", "/budgets")["items"]}
    assert codes == {"A", "B"}
    options = pm.ok("get", "/expenses/options")["projects"]
    assert [item["name"] for item in options] == ["A · Project A", "B · Project B"]


def test_manager_cannot_change_categories(pm, world):
    url = f"/expense-categories/{world['Travel']}"
    answers = [
        pm.call("post", "/expense-categories", {"name": "X"}),
        pm.call("put", url, {"name": "X"}),
        pm.call("delete", url),
    ]
    assert {answer.status_code for answer in answers} == {403}


@pytest.fixture()
def viewer(clients, people, session, world):
    """Let the manager and the member see a project neither of them manages."""
    from app.models import ProjectAssignment, Resource

    for role in ("project_manager", "team_member"):
        row = Resource(
            employee_code=role[:5],
            full_name=role,
            email=f"r-{role}@example.com",
            department_id=world["department"],
            job_title="X",
            user_id=people[role][0].id,
        )
        session.add(row)
        session.flush()
        session.add(
            ProjectAssignment(
                project_id=world["OTHER"],
                resource_id=row.id,
                allocation_percent=10,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 2, 1),
            )
        )
    session.flush()


def test_seeing_a_project_does_not_reveal_its_budget(admin, clients, pm, world, viewer):
    admin.spend(150000, "OTHER")
    project = f"/projects/{world['OTHER']}"
    for role in ("project_manager", "team_member"):
        found = clients[role].ok("get", project)
        assert (found["budget"], found["planned_budget"]) == (None, None)
        page = clients[role].ok("get", "/projects?budget_status=Over Budget")
        assert page["total"] == 0  # The filter must not reveal it either
    assert pm.call("get", f"{project}/budget").status_code == 403
    body = pm.body(1)
    assert pm.call("post", f"{project}/expenses", body).status_code == 403


def test_budget_filter_choices_depend_on_role(clients):
    for role, count in (("admin", 4), ("project_manager", 4), ("team_member", 0)):
        options = clients[role].ok("get", "/projects/options")
        assert len(options["budget_statuses"]) == count
