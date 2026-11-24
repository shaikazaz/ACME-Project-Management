"""Project queries and business rules."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, Row, Select, case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import Permission, Role, has_permission
from app.auth.scopes import can_manage_project, managed_projects, visible_projects
from app.errors import ApiError
from app.models import (
    Deliverable,
    Department,
    Expense,
    Milestone,
    Project,
    ProjectAssignment,
    User,
)
from app.models.base import PRIORITIES
from app.schemas.common import Page
from app.schemas.projects import (
    NamedItem,
    ProjectDetails,
    ProjectRequest,
    ProjectSummary,
    Risk,
)
from app.services.budgets import (
    budget_status,
    make_budget,
    spent,
    warning_percent,
)
from app.services.deliverables import CLOSED_STATUSES, count_by_status, lock_work
from app.services.dependencies import blocks_other_projects
from app.services.risk import assess_projects

# Projects that are running, paused or finished must be cancelled first.
DELETABLE_STATUSES = ("Planned", "Cancelled")
MANAGER_ROLES = (Role.ADMIN, Role.PROJECT_MANAGER)
ADMIN_ONLY_FIELDS = ("code", "department_id", "manager_id")


def progress_expression() -> ColumnElement:
    """Build the SQL that calculates a project's progress.

    Progress is the average of its deliverables, weighted by estimated hours
    when every deliverable has an estimate. Without deliverables it is 100 for
    completed projects and 0 otherwise.

    Returns:
        A percentage from 0 to 100.
    """
    weighted = func.sum(
        Deliverable.progress_percent * Deliverable.estimated_hours
    ) / func.nullif(func.sum(Deliverable.estimated_hours), 0)
    average = case(
        (func.min(Deliverable.estimated_hours) > 0, weighted),
        else_=func.avg(Deliverable.progress_percent),
    )
    from_deliverables = (
        select(average)
        .where(Deliverable.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    fallback = case((Project.status == "Completed", 100), else_=0)
    return func.round(func.coalesce(from_deliverables, fallback), 1)


def _sort_expressions() -> dict[str, ColumnElement]:
    """Map sort names to SQL. Budget is excluded: not everyone may see it."""
    rank = case({name: i for i, name in enumerate(PRIORITIES)}, value=Project.priority)
    return {
        "name": func.lower(Project.name),
        "code": Project.code,
        "status": Project.status,
        "priority": rank,
        "start_date": Project.start_date,
        "end_date": Project.end_date,
        "progress": progress_expression(),
        "updated_at": Project.updated_at,
    }


SORT_FIELDS = tuple(_sort_expressions())


def with_details() -> Select:
    """Select projects with their progress, spending, department and manager."""
    return select(Project, progress_expression(), spent()).options(
        joinedload(Project.department), joinedload(Project.manager)
    )


def summarize(
    user: User,
    project: Project,
    progress: Decimal,
    actual: Decimal,
    warning: Decimal,
    risks: dict[int, Risk],
) -> dict:
    """Describe a project as the user is allowed to see it.

    Args:
        user: The signed-in user.
        project: The project.
        progress: The calculated progress.
        actual: The actual spending.
        warning: The consumption at which a budget needs attention.
        risks: The risks of the projects the user manages.

    Returns:
        Values for ProjectSummary.
    """
    manager = project.manager
    can_manage = can_manage_project(user, project)
    may_delete = has_permission(user.role, Permission.DELETE_PROJECTS)
    return {
        "id": project.id,
        "code": project.code,
        "name": project.name,
        "department": NamedItem.model_validate(project.department),
        "manager": NamedItem(id=manager.id, name=manager.full_name)
        if manager
        else None,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "actual_completion_date": project.actual_completion_date,
        "status": project.status,
        "priority": project.priority,
        "progress_percent": progress,
        "planned_budget": project.planned_budget if can_manage else None,
        "budget": make_budget(project.planned_budget, actual, warning)
        if can_manage
        else None,
        "risk": risks.get(project.id),
        "can_edit": can_manage,
        "can_delete": may_delete and project.status in DELETABLE_STATUSES,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _managed_risks(
    session: Session, user: User, rows: Sequence[Row]
) -> dict[int, Risk]:
    """Assess the projects a user manages."""
    managed = [row for row in rows if can_manage_project(user, row[0])]
    return assess_projects(session, managed)


def search_projects(
    session: Session,
    user: User,
    *,
    search: str,
    statuses: list[str],
    priorities: list[str],
    department_id: int | None,
    manager_id: int | None,
    budget_statuses: list[str],
    risk_levels: list[str],
    start_from: date | None,
    start_to: date | None,
    end_from: date | None,
    end_to: date | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> Page[ProjectSummary]:
    """Search the projects a user may view.

    Args:
        session: Database session.
        user: The signed-in user.
        search: Text to find in the code, name or description.
        statuses: Statuses to include; empty means all.
        priorities: Priorities to include; empty means all.
        department_id: Department to include.
        manager_id: Project manager to include.
        budget_statuses: Budget statuses to include; empty means all.
        risk_levels: Risk levels to include; empty means all.
        start_from: Earliest start date.
        start_to: Latest start date.
        end_from: Earliest end date.
        end_to: Latest end date.
        sort: One of SORT_FIELDS.
        descending: Whether to reverse the order.
        limit: Page size.
        offset: Number of results to skip.

    Returns:
        One page of projects and the total number of matches.
    """
    conditions = [visible_projects(user)]
    if search:
        columns = (Project.code, Project.name, Project.description)
        conditions.append(
            or_(*(column.icontains(search, autoescape=True) for column in columns))
        )
    if statuses:
        conditions.append(Project.status.in_(statuses))
    if priorities:
        conditions.append(Project.priority.in_(priorities))
    if department_id is not None:
        conditions.append(Project.department_id == department_id)
    if manager_id is not None:
        conditions.append(Project.manager_id == manager_id)
    warning = warning_percent(session)
    if budget_statuses:
        # Only for managed projects: others may not learn about the budget.
        status = budget_status(Project.planned_budget, spent(), warning)
        conditions += [managed_projects(user), status.in_(budget_statuses)]
    if risk_levels:
        # Risk reveals budgets too, so this is also only for managed projects.
        managed = session.execute(
            with_details().where(
                managed_projects(user), Project.status.not_in(CLOSED_STATUSES)
            )
        ).all()
        risks = assess_projects(session, managed)
        matching = [key for key, risk in risks.items() if risk.level in risk_levels]
        conditions.append(Project.id.in_(matching))
    if start_from is not None:
        conditions.append(Project.start_date >= start_from)
    if start_to is not None:
        conditions.append(Project.start_date <= start_to)
    if end_from is not None:
        conditions.append(Project.end_date >= end_from)
    if end_to is not None:
        conditions.append(Project.end_date <= end_to)

    order = _sort_expressions()[sort]
    total = session.scalar(select(func.count()).select_from(Project).where(*conditions))
    rows = session.execute(
        with_details()
        .where(*conditions)
        .order_by(order.desc() if descending else order.asc(), Project.id)
        .limit(limit)
        .offset(offset)
    ).all()
    risks = _managed_risks(session, user, rows)
    items = [ProjectSummary(**summarize(user, *row, warning, risks)) for row in rows]
    return Page(items=items, total=total)


def describe_project(session: Session, user: User, project_id: int) -> ProjectDetails:
    """Return one project in full.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to view the project.
        project_id: The project.

    Returns:
        The project with its related record counts.
    """
    row = session.execute(with_details().where(Project.id == project_id)).one()
    project = row[0]
    warning = warning_percent(session)
    risks = _managed_risks(session, user, [row])

    def count(model: type) -> int:
        """Count the project's records in one table."""
        query = (
            select(func.count())
            .select_from(model)
            .where(model.project_id == project_id)
        )
        return session.scalar(query)

    return ProjectDetails(
        **summarize(user, *row, warning, risks),
        description=project.description,
        deliverable_count=count(Deliverable),
        deliverables_by_status=count_by_status(session, project_id),
        milestone_count=count(Milestone),
        assignment_count=count(ProjectAssignment),
        expense_count=count(Expense),
    )


def save_project(
    session: Session, user: User, project: Project, body: ProjectRequest
) -> None:
    """Apply changes to a new or existing project.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to manage the project.
        project: The project to change.
        body: The requested values.

    Raises:
        ApiError: A value is not allowed.
    """
    lock_work(session)
    if project.id is not None:
        session.refresh(project)
    changed = {
        field
        for field, value in body.model_dump().items()
        if getattr(project, field) != value
    }
    if user.role != Role.ADMIN and changed & set(ADMIN_ONLY_FIELDS):
        raise ApiError(
            403, "Only an admin can change the code, department or project manager."
        )
    if "department_id" in changed and not session.get(Department, body.department_id):
        raise ApiError(400, "Department not found.", field="department_id")
    if "manager_id" in changed and body.manager_id is not None:
        manager = session.get(User, body.manager_id)
        if (
            manager is None
            or not manager.is_active
            or manager.role not in MANAGER_ROLES
        ):
            raise ApiError(
                400, "Choose an active project manager or admin.", field="manager_id"
            )
    if "status" in changed and body.status == "Completed" and project.id is not None:
        unfinished = session.scalar(
            select(func.count())
            .select_from(Deliverable)
            .where(
                Deliverable.project_id == project.id, Deliverable.status != "Completed"
            )
        )
        if unfinished:
            raise ApiError(
                409,
                f"{unfinished} deliverables are not completed yet.",
                field="status",
            )
    for field in changed:
        setattr(project, field, getattr(body, field))
    session.add(project)
    session.commit()


def delete_project(session: Session, project_id: int, confirm_code: str) -> None:
    """Delete a project that is safe to delete.

    Args:
        session: Database session.
        project_id: The project.
        confirm_code: The project's code, typed by the user as confirmation.

    Raises:
        ApiError: The project may not be deleted.
    """
    lock_work(session)
    # Lock the row, so its status cannot change between the check and delete.
    project = session.get(Project, project_id, with_for_update=True)
    if project is None:
        raise ApiError(404, "Project not found.")
    if confirm_code.strip().upper() != project.code.upper():
        raise ApiError(400, "Type the project code to confirm.", field="confirm_code")
    if project.status not in DELETABLE_STATUSES:
        raise ApiError(
            409, "Only planned or cancelled projects can be deleted. Cancel it first."
        )
    if blocks_other_projects(session, project_id):
        raise ApiError(409, "Deliverables in other projects depend on this project.")
    session.delete(project)
    session.commit()


def list_managers(session: Session, user: User) -> list[NamedItem]:
    """List project managers for forms and filters.

    Admins see everyone who may manage a project. Others see only the managers
    of projects they may view.

    Args:
        session: Database session.
        user: The signed-in user.

    Returns:
        The managers, sorted by name.
    """
    current = select(Project.manager_id).where(visible_projects(user))
    condition = User.id.in_(current)
    if user.role == Role.ADMIN:
        assignable = User.is_active & User.role.in_(MANAGER_ROLES)
        condition = or_(condition, assignable)
    rows = session.scalars(
        select(User).where(condition).order_by(User.full_name, User.id)
    )
    return [NamedItem(id=row.id, name=row.full_name) for row in rows]
