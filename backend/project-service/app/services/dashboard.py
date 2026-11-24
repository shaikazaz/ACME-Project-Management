"""Dashboard figures, all calculated from the stored records."""

from datetime import timedelta

from sqlalchemy import Select, func, literal, select
from sqlalchemy.orm import Session

from app.auth.scopes import managed_projects
from app.dates import today
from app.models import AppSetting, Deliverable, Milestone, Project, User
from app.models.deliverables import DELIVERABLE_STATUSES
from app.models.projects import PROJECT_STATUSES
from app.schemas.dashboard import (
    BudgetMetrics,
    Dashboard,
    Deadline,
    DeliverableMetrics,
    ProjectMetrics,
    ResourceMetrics,
    RiskyProject,
)
from app.schemas.projects import NamedItem
from app.services.budgets import search_budgets
from app.services.deliverables import CLOSED_STATUSES, effective_status, is_overdue
from app.services.projects import with_details
from app.services.resources import report_workload
from app.services.risk import HIGH, LOW, MEDIUM, RISK_LEVELS, assess_projects, is_open
from app.services.workload import Period

UPCOMING_SETTING = "upcoming_deadline_days"
MAX_DEADLINES = 20
MAX_RISKY_PROJECTS = 10


def _deliverables(session: Session, user: User) -> DeliverableMetrics:
    """Count deliverables."""
    rows = session.execute(
        select(effective_status(), is_overdue())
        .select_from(Deliverable)
        .join(Project, Project.id == Deliverable.project_id)
        .where(managed_projects(user), Project.status != "Cancelled")
    ).all()
    by_status = dict.fromkeys(DELIVERABLE_STATUSES, 0)
    for status, _ in rows:
        by_status[status] += 1
    completed = by_status["Completed"]
    return DeliverableMetrics(
        total=len(rows),
        completed=completed,
        pending=len(rows) - completed,
        overdue=sum(late for _, late in rows),
        by_status=by_status,
        completion_percent=round(completed * 100 / len(rows), 1) if rows else None,
    )


def _deadlines(session: Session, user: User, days: int) -> tuple[int, list[Deadline]]:
    """List the deadlines of open work, from today until a number of days later."""
    now = today()
    until = now + timedelta(days=days)

    def query(kind: str, model: type, due: object, *conditions: object) -> Select:
        """Select one kind of deadline."""
        rows = select(
            literal(kind).label("kind"),
            model.id.label("id"),
            model.name.label("name"),
            Project.id.label("project_id"),
            Project.code.label("project_code"),
            due.label("due_date"),
        )
        if model is not Project:
            rows = rows.join(Project, Project.id == model.project_id)
        return rows.where(
            managed_projects(user),
            Project.status.not_in(CLOSED_STATUSES),
            due >= now,
            due <= until,
            *conditions,
        )

    rows = (
        query("Project", Project, Project.end_date)
        .union_all(
            query(
                "Milestone",
                Milestone,
                Milestone.due_date,
                Milestone.completed_date.is_(None),
            ),
            query(
                "Deliverable",
                Deliverable,
                Deliverable.due_date,
                Deliverable.status != "Completed",
            ),
        )
        .subquery()
    )
    total = session.scalar(select(func.count()).select_from(rows))
    items = session.execute(
        select(rows)
        .order_by(rows.c.due_date, rows.c.kind.desc(), rows.c.id)
        .limit(MAX_DEADLINES)
    ).mappings()
    return total, [
        Deadline(**item, days_left=(item["due_date"] - now).days) for item in items
    ]


def build_dashboard(session: Session, user: User) -> Dashboard:
    """Calculate the dashboard of the projects a user manages.

    Resource figures cover everyone, because people work across projects.

    Args:
        session: Database session.
        user: The signed-in user.

    Returns:
        The dashboard.
    """
    now = today()
    rows = [
        tuple(row)
        for row in session.execute(with_details().where(managed_projects(user)))
    ]
    by_status = dict.fromkeys(PROJECT_STATUSES, 0)
    for project, *_ in rows:
        by_status[project.status] += 1
    risks = assess_projects(session, rows)
    by_risk = dict.fromkeys(RISK_LEVELS, 0)
    for risk in risks.values():
        by_risk[risk.level] += 1

    risky = [
        row for row in rows if row[0].id in risks and risks[row[0].id].level != LOW
    ]
    risky.sort(
        key=lambda row: (
            RISK_LEVELS.index(risks[row[0].id].level),
            row[0].end_date,
            row[0].id,
        )
    )
    days = int(session.get(AppSetting, UPCOMING_SETTING).value)
    deadline_count, deadlines = _deadlines(session, user, days)
    workload = report_workload(session, user, Period(now))
    budget = search_budgets(
        session,
        user,
        search="",
        budget_statuses=[],
        project_statuses=[],
        department_id=None,
        manager_id=None,
        sort="code",
        descending=False,
        limit=1,
        offset=0,
    )
    return Dashboard(
        as_of=now,
        upcoming_days=days,
        projects=ProjectMetrics(
            total=len(rows),
            by_status=by_status,
            overdue=sum(is_open(row[0]) and row[0].end_date < now for row in rows),
            by_risk=by_risk,
            at_risk=by_risk[HIGH] + by_risk[MEDIUM],
        ),
        deliverables=_deliverables(session, user),
        resources=ResourceMetrics(
            total=workload.resource_count,
            over_allocated=workload.over_allocated_count,
            needs_cover=workload.needs_cover_count,
            capacity_percent=workload.capacity_percent,
            peak_percent=workload.peak_percent,
            utilization_percent=workload.utilization_percent,
        ),
        budget=BudgetMetrics(
            planned=budget.planned,
            actual=budget.actual,
            remaining=budget.remaining,
            consumed_percent=budget.consumed_percent,
            by_status=budget.by_status,
        ),
        deadline_count=deadline_count,
        deadlines=deadlines,
        risky_projects=[
            RiskyProject(
                id=project.id,
                code=project.code,
                name=project.name,
                status=project.status,
                manager=NamedItem(id=project.manager.id, name=project.manager.full_name)
                if project.manager
                else None,
                end_date=project.end_date,
                progress_percent=progress,
                risk=risks[project.id],
            )
            for project, progress, _ in risky[:MAX_RISKY_PROJECTS]
        ],
    )
