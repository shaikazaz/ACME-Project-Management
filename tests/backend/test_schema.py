"""Schema tests: CRUD, constraints, relationships and migrations."""

import threading
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from conftest import SERVICE_DIR
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    User,
)

START, END = date(2026, 1, 1), date(2026, 6, 30)


def save(session, record):
    """Insert one record and return it."""
    session.add(record)
    session.flush()
    return record


def rejects(session, *records):
    """Return the name of the constraint that rejects the records."""
    with pytest.raises(IntegrityError) as caught, session.begin_nested():
        session.add_all(records)
        session.flush()
    return caught.value.orig.diag.constraint_name


def make_department(session, name="IT"):
    return save(session, Department(name=name))


def make_project(session, code="P1", department=None, **extra):
    department = department or make_department(session, f"Dept {code}")
    values = {"name": code, "start_date": START, "end_date": END, **extra}
    return save(session, Project(code=code, department_id=department.id, **values))


def make_resource(session, code="E1", department=None, **extra):
    department = department or make_department(session, f"Dept {code}")
    values = {
        "employee_code": code,
        "full_name": code,
        "email": f"{code}@example.com",
        "job_title": "Engineer",
        **extra,
    }
    return save(session, Resource(department_id=department.id, **values))


def make_deliverable(session, project, name, **extra):
    values = {"start_date": START, "due_date": END, **extra}
    return save(session, Deliverable(project_id=project.id, name=name, **values))


def link(session, before, after):
    return save(
        session,
        DeliverableDependency(predecessor_id=before.id, successor_id=after.id),
    )


# --- Create, read, update and delete ---------------------------------------


def test_project_crud_and_defaults(session):
    project = make_project(session, planned_budget=Decimal("1234.56"))
    session.refresh(project)
    assert (project.status, project.priority) == ("Planned", "Medium")
    assert project.planned_budget == Decimal("1234.56")
    assert project.created_at.tzinfo is not None
    assert project.department.name == "Dept P1"

    project.name = "Renamed"
    session.flush()
    session.expire_all()
    assert session.get(Project, project.id).name == "Renamed"

    session.delete(project)
    session.flush()
    assert session.scalar(select(func.count()).select_from(Project)) == 0


def test_reference_data_exists(session):
    assert session.scalar(select(func.count()).select_from(ExpenseCategory)) == 7
    assert session.get(AppSetting, "budget_warning_percent").value == 80


def test_money_is_exact(session):
    project = make_project(session)
    category = session.scalars(select(ExpenseCategory)).first()
    for amount in ("0.10", "0.20"):
        save(
            session,
            Expense(
                project_id=project.id,
                category_id=category.id,
                amount=Decimal(amount),
                expense_date=START,
            ),
        )
    assert session.scalar(select(func.sum(Expense.amount))) == Decimal("0.30")


def test_allocation_can_be_summed_across_projects(session):
    resource = make_resource(session)
    for code, percent in (("A", 60), ("B", 50)):
        save(
            session,
            ProjectAssignment(
                project_id=make_project(session, code).id,
                resource_id=resource.id,
                allocation_percent=percent,
                start_date=START,
                end_date=END,
            ),
        )
    total = session.scalar(select(func.sum(ProjectAssignment.allocation_percent)))
    assert total == 110 > resource.capacity_percent


# --- Constraints -----------------------------------------------------------


@pytest.mark.parametrize(
    ("extra", "constraint"),
    [
        ({"status": "Unknown"}, "status_valid"),
        ({"priority": "Urgent"}, "priority_valid"),
        ({"end_date": date(2025, 1, 1)}, "dates_in_order"),
        ({"planned_budget": -1}, "planned_budget_not_negative"),
        ({"name": "  "}, "name_not_blank"),
        ({"status": "Completed"}, "completion_date_matches_status"),
        ({"actual_completion_date": END}, "completion_date_matches_status"),
        (
            {"status": "Completed", "actual_completion_date": date(2025, 1, 1)},
            "completed_after_start",
        ),
    ],
)
def test_project_rules(session, extra, constraint):
    department = make_department(session)
    values = {"name": "X", "start_date": START, "end_date": END, **extra}
    project = Project(code="X", department_id=department.id, **values)
    assert rejects(session, project) == f"ck_projects_{constraint}"


@pytest.mark.parametrize(
    ("extra", "constraint"),
    [
        ({"status": "Late"}, "status_valid"),
        ({"due_date": date(2025, 1, 1)}, "dates_in_order"),
        ({"progress_percent": 101}, "progress_percent_range"),
        ({"estimated_hours": -1}, "estimated_hours_not_negative"),
        ({"actual_hours": -1}, "actual_hours_not_negative"),
        (
            {"status": "Completed", "completion_date": END, "progress_percent": 50},
            "completed_means_full_progress",
        ),
    ],
)
def test_deliverable_rules(session, extra, constraint):
    project = make_project(session)
    values = {"start_date": START, "due_date": END, **extra}
    record = Deliverable(project_id=project.id, name="D", **values)
    assert rejects(session, record) == f"ck_deliverables_{constraint}"


@pytest.mark.parametrize("percent", [0, -5, 100.01])
def test_allocation_range(session, percent):
    record = ProjectAssignment(
        project_id=make_project(session).id,
        resource_id=make_resource(session).id,
        allocation_percent=percent,
        start_date=START,
        end_date=END,
    )
    assert rejects(session, record).endswith("allocation_percent_range")


def test_expense_must_be_positive(session):
    record = Expense(
        project_id=make_project(session).id,
        category_id=session.scalars(select(ExpenseCategory.id)).first(),
        amount=0,
        expense_date=START,
    )
    assert rejects(session, record) == "ck_expenses_amount_positive"


def test_user_role_is_restricted(session):
    user = User(email="a@b.c", full_name="A", password_hash="x", role="superuser")
    assert rejects(session, user) == "ck_users_role_valid"


def test_duplicates_are_rejected_ignoring_case(session):
    department = make_department(session, "Finance")
    assert rejects(session, Department(name="FINANCE")) == "uq_departments_name_lower"
    make_project(session, "abc", department)
    values = {"name": "n", "start_date": START, "end_date": END}
    duplicate = Project(code="ABC", department_id=department.id, **values)
    assert rejects(session, duplicate) == "uq_projects_code_lower"


def test_unknown_department_is_rejected(session):
    project = Project(
        code="X", name="X", department_id=999, start_date=START, end_date=END
    )
    assert rejects(session, project) == "fk_projects_department_id"


# --- Relationships and deletion --------------------------------------------


def test_milestone_must_belong_to_same_project(session):
    first, second = make_project(session, "A"), make_project(session, "B")
    milestone = save(session, Milestone(project_id=first.id, name="M", due_date=END))
    record = Deliverable(
        project_id=second.id,
        milestone_id=milestone.id,
        name="D",
        start_date=START,
        due_date=END,
    )
    assert rejects(session, record) == "fk_deliverables_milestone_id_project_id"


def test_deleting_milestone_keeps_its_deliverables(session):
    project = make_project(session)
    milestone = save(session, Milestone(project_id=project.id, name="M", due_date=END))
    record = make_deliverable(session, project, "D", milestone_id=milestone.id)
    session.execute(delete(Milestone).where(Milestone.id == milestone.id))
    session.expire_all()
    assert record.milestone_id is None
    assert record.project_id == project.id


def test_deleting_project_removes_its_work_but_not_people(session):
    project, resource = make_project(session), make_resource(session)
    milestone = save(session, Milestone(project_id=project.id, name="M", due_date=END))
    first = make_deliverable(session, project, "D1", milestone_id=milestone.id)
    link(session, first, make_deliverable(session, project, "D2"))
    save(
        session,
        ProjectAssignment(
            project_id=project.id,
            resource_id=resource.id,
            allocation_percent=50,
            start_date=START,
            end_date=END,
        ),
    )
    session.execute(delete(Project).where(Project.id == project.id))
    for model in (Milestone, Deliverable, DeliverableDependency, ProjectAssignment):
        assert session.scalar(select(func.count()).select_from(model)) == 0
    assert session.scalar(select(func.count()).select_from(Resource)) == 1


def test_project_with_expenses_cannot_be_deleted(session):
    project = make_project(session)
    save(
        session,
        Expense(
            project_id=project.id,
            category_id=session.scalars(select(ExpenseCategory.id)).first(),
            amount=10,
            expense_date=START,
        ),
    )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(delete(Project).where(Project.id == project.id))


def test_department_in_use_cannot_be_deleted(session):
    department = make_department(session)
    make_project(session, "P", department)
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(delete(Department).where(Department.id == department.id))


def test_deleting_user_keeps_resource(session):
    user = save(
        session,
        User(email="a@b.c", full_name="A", password_hash="x", role="team_member"),
    )
    resource = make_resource(session, user_id=user.id)
    session.execute(delete(User).where(User.id == user.id))
    session.expire_all()
    assert resource.user_id is None


# --- Dependencies ----------------------------------------------------------


def test_dependency_chain_allows_valid_and_rejects_circular(session):
    project = make_project(session)
    names = ("Requirements", "Design", "Development", "Testing", "Deployment")
    steps = [make_deliverable(session, project, name) for name in names]
    for before, after in zip(steps, steps[1:], strict=False):
        link(session, before, after)
    link(session, steps[0], steps[4])  # A shortcut is not a circle

    for before, after in ((4, 0), (1, 0), (3, 1)):
        circular = DeliverableDependency(
            predecessor_id=steps[before].id, successor_id=steps[after].id
        )
        assert rejects(session, circular) == "deliverable_dependencies_no_cycle"


def test_dependency_on_itself_is_rejected(session):
    record = make_deliverable(session, make_project(session), "D")
    loop = DeliverableDependency(predecessor_id=record.id, successor_id=record.id)
    assert rejects(session, loop) == "ck_deliverable_dependencies_not_self"


def test_dependency_may_cross_projects(session):
    first = make_deliverable(session, make_project(session, "A"), "D")
    second = make_deliverable(session, make_project(session, "B"), "D")
    link(session, first, second)
    circular = DeliverableDependency(predecessor_id=second.id, successor_id=first.id)
    assert rejects(session, circular) == "deliverable_dependencies_no_cycle"


def test_dependency_cannot_be_edited(session):
    project = make_project(session)
    link(
        session,
        make_deliverable(session, project, "A"),
        make_deliverable(session, project, "B"),
    )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text("UPDATE deliverable_dependencies SET created_at = now()"))


def test_simultaneous_inserts_cannot_form_a_circle(migrated_engine):
    with Session(migrated_engine) as setup:
        project = make_project(setup, "RACE")
        ids = [make_deliverable(setup, project, name).id for name in ("A", "B")]
        project_id, department_id = project.id, project.department_id
        setup.commit()

    outcomes = []

    def insert(before, after):
        try:
            with Session(migrated_engine) as own:
                barrier.wait(5)
                own.add(
                    DeliverableDependency(predecessor_id=before, successor_id=after)
                )
                own.commit()
            outcomes.append("saved")
        except IntegrityError:
            outcomes.append("rejected")

    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(target=insert, args=pair)
        for pair in ((ids[0], ids[1]), (ids[1], ids[0]))
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with Session(migrated_engine) as cleanup:
        cleanup.execute(delete(Project).where(Project.id == project_id))
        cleanup.execute(delete(Department).where(Department.id == department_id))
        cleanup.commit()
    assert sorted(outcomes) == ["rejected", "saved"]


# --- Migrations ------------------------------------------------------------


def test_models_match_migrations(migrated_engine):
    command.check(Config(str(SERVICE_DIR / "alembic.ini")))


def test_rerunning_migrations_keeps_data(migrated_engine):
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    with Session(migrated_engine) as own:
        own.add(Department(name="Keep me"))
        own.commit()
    command.upgrade(config, "head")
    with Session(migrated_engine) as own:
        found = own.scalar(select(Department).where(Department.name == "Keep me"))
        assert found is not None
        own.delete(found)
        own.commit()


def test_downgrade_refuses_to_delete_data(migrated_engine):
    with pytest.raises(RuntimeError, match="would delete all data"):
        command.downgrade(Config(str(SERVICE_DIR / "alembic.ini")), "base")
    with Session(migrated_engine) as own:
        assert own.scalar(select(func.count()).select_from(ExpenseCategory)) == 7
