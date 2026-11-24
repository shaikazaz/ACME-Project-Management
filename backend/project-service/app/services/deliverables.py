"""Deliverable queries and business rules.

Blocking rule: a deliverable is blocked while any of its direct predecessors
is not completed. This is calculated from the dependencies each time, so
completing the predecessor unblocks its successors at once.
"""

from datetime import date

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select, text
from sqlalchemy.orm import Session, aliased, joinedload

from app.auth.scopes import can_manage_project, visible_deliverables, visible_projects
from app.dates import today
from app.errors import ApiError
from app.models import (
    Deliverable,
    DeliverableDependency,
    Milestone,
    Project,
    Resource,
    User,
)
from app.models.base import PRIORITIES
from app.models.deliverables import DELIVERABLE_STATUSES
from app.schemas.common import Page
from app.schemas.deliverables import (
    DeliverableDetails,
    DeliverableOptions,
    DeliverableRequest,
    DeliverableSummary,
    ProgressRequest,
    ProjectLabel,
    RelatedDeliverable,
)
from app.schemas.projects import NamedItem

CLOSED_STATUSES = ("Completed", "Cancelled")
HIDDEN_NAME = "A deliverable in another project"
# The circular dependency trigger uses the same lock.
WORK_LOCK_ID = 728402


def lock_work(session: Session) -> None:
    """Make changes to work wait for each other until the transaction ends.

    Rules such as "completed work has completed predecessors" involve several
    records, so two changes must not be checked at the same moment.

    Args:
        session: Database session.
    """
    session.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": WORK_LOCK_ID})


def has_unfinished_predecessor() -> ColumnElement[bool]:
    """Build the SQL condition for deliverables waiting for a predecessor."""
    predecessor = aliased(Deliverable)
    return (
        select(DeliverableDependency.successor_id)
        .join(predecessor, predecessor.id == DeliverableDependency.predecessor_id)
        .where(
            DeliverableDependency.successor_id == Deliverable.id,
            predecessor.status != "Completed",
        )
        .correlate(Deliverable)
        .exists()
    )


def effective_status() -> ColumnElement[str]:
    """Build the SQL for a deliverable's status after applying dependencies."""
    waiting = and_(Deliverable.status != "Completed", has_unfinished_predecessor())
    return case((waiting, "Blocked"), else_=Deliverable.status)


def is_overdue() -> ColumnElement[bool]:
    """Build the SQL condition for overdue deliverables.

    Unfinished work past its due date is overdue, unless its project was
    cancelled. The query must include Project.
    """
    return and_(
        Deliverable.due_date < today(),
        Deliverable.status != "Completed",
        Project.status != "Cancelled",
    )


def _sort_expressions() -> dict[str, ColumnElement]:
    """Map sort names to SQL."""
    rank = case(
        {name: i for i, name in enumerate(PRIORITIES)}, value=Deliverable.priority
    )
    return {
        "name": func.lower(Deliverable.name),
        "project": Project.code,
        "status": effective_status(),
        "priority": rank,
        "start_date": Deliverable.start_date,
        "due_date": Deliverable.due_date,
        "progress": Deliverable.progress_percent,
    }


SORT_FIELDS = tuple(_sort_expressions())


def with_details() -> Select:
    """Select deliverables with their effective status and overdue flag."""
    return (
        select(Deliverable, effective_status(), is_overdue())
        .join(Project, Project.id == Deliverable.project_id)
        .options(
            joinedload(Deliverable.project),
            joinedload(Deliverable.owner),
            joinedload(Deliverable.milestone),
        )
    )


def related_deliverables(
    session: Session, user: User, ids: list[int], *, upstream: bool
) -> dict[int, list[RelatedDeliverable]]:
    """Find the direct predecessors or successors of several deliverables.

    Args:
        session: Database session.
        user: The signed-in user. Names are hidden in projects they cannot see.
        ids: The deliverables.
        upstream: True for predecessors, False for successors.

    Returns:
        The related deliverables by deliverable id.
    """
    link = DeliverableDependency
    near, far = link.successor_id, link.predecessor_id
    if not upstream:
        near, far = far, near
    rows = session.execute(
        select(near, Deliverable, Project.code, visible_projects(user))
        .join(Deliverable, Deliverable.id == far)
        .join(Project, Project.id == Deliverable.project_id)
        .where(near.in_(ids))
        .order_by(Deliverable.due_date, Deliverable.id)
    )
    found: dict[int, list[RelatedDeliverable]] = {key: [] for key in ids}
    for key, row, code, visible in rows:
        found[key].append(
            RelatedDeliverable(
                id=row.id if visible else None,
                name=row.name if visible else HIDDEN_NAME,
                project_code=code if visible else None,
                status=row.status,
            )
        )
    return found


def summarize(
    user: User,
    row: Deliverable,
    current_status: str,
    overdue: bool,
    predecessors: list[RelatedDeliverable],
) -> dict:
    """Describe a deliverable as the user is allowed to see it.

    Args:
        user: The signed-in user, who must be allowed to view the deliverable.
        row: The deliverable.
        current_status: Its effective status.
        overdue: Whether it is overdue.
        predecessors: Its direct predecessors.

    Returns:
        Values for DeliverableSummary.
    """
    project = row.project
    is_open = project.status not in CLOSED_STATUSES
    done = row.status == "Completed"
    unfinished = [item for item in predecessors if item.status != "Completed"]
    return {
        "id": row.id,
        "name": row.name,
        "project": ProjectLabel.model_validate(project),
        "milestone": NamedItem.model_validate(row.milestone) if row.milestone else None,
        "owner": NamedItem(id=row.owner.id, name=row.owner.full_name)
        if row.owner
        else None,
        "start_date": row.start_date,
        "due_date": row.due_date,
        "completion_date": row.completion_date,
        "status": row.status,
        "effective_status": current_status,
        "blocked_by": [] if done else unfinished,
        "priority": row.priority,
        "progress_percent": row.progress_percent,
        "estimated_hours": row.estimated_hours,
        "actual_hours": row.actual_hours,
        "is_overdue": overdue,
        "days_overdue": (today() - row.due_date).days if overdue else 0,
        "completed_late": done and row.completion_date > row.due_date,
        "can_edit": is_open and can_manage_project(user, project),
        "can_update": is_open,
        "updated_at": row.updated_at,
    }


def search_deliverables(
    session: Session,
    user: User,
    *,
    search: str,
    statuses: list[str],
    priorities: list[str],
    project_id: int | None,
    owner_id: int | None,
    milestone_id: int | None,
    overdue: bool | None,
    due_from: date | None,
    due_to: date | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> Page[DeliverableSummary]:
    """Search the deliverables a user may view.

    Args:
        session: Database session.
        user: The signed-in user.
        search: Text to find in the name or description.
        statuses: Effective statuses to include; empty means all.
        priorities: Priorities to include; empty means all.
        project_id: Project to include.
        owner_id: Owner to include.
        milestone_id: Milestone to include.
        overdue: Whether to include only overdue or only other work.
        due_from: Earliest due date.
        due_to: Latest due date.
        sort: One of SORT_FIELDS.
        descending: Whether to reverse the order.
        limit: Page size.
        offset: Number of results to skip.

    Returns:
        One page of deliverables and the total number of matches.
    """
    conditions = [visible_deliverables(user)]
    if search:
        columns = (Deliverable.name, Deliverable.description)
        conditions.append(
            or_(*(column.icontains(search, autoescape=True) for column in columns))
        )
    if statuses:
        conditions.append(effective_status().in_(statuses))
    if priorities:
        conditions.append(Deliverable.priority.in_(priorities))
    for column, value in (
        (Deliverable.project_id, project_id),
        (Deliverable.owner_id, owner_id),
        (Deliverable.milestone_id, milestone_id),
    ):
        if value is not None:
            conditions.append(column == value)
    if overdue is not None:
        conditions.append(is_overdue() == overdue)
    if due_from is not None:
        conditions.append(Deliverable.due_date >= due_from)
    if due_to is not None:
        conditions.append(Deliverable.due_date <= due_to)

    total = session.scalar(
        select(func.count())
        .select_from(Deliverable)
        .join(Project, Project.id == Deliverable.project_id)
        .where(*conditions)
    )
    order = _sort_expressions()[sort]
    rows = session.execute(
        with_details()
        .where(*conditions)
        .order_by(order.desc() if descending else order.asc(), Deliverable.id)
        .limit(limit)
        .offset(offset)
    ).all()
    before = related_deliverables(
        session, user, [row.id for row, *_ in rows], upstream=True
    )
    items = [
        DeliverableSummary(**summarize(user, row, current, late, before[row.id]))
        for row, current, late in rows
    ]
    return Page(items=items, total=total)


def describe_deliverable(
    session: Session, user: User, deliverable_id: int
) -> DeliverableDetails:
    """Return one deliverable in full.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to view it.
        deliverable_id: The deliverable.

    Returns:
        The deliverable with its dependencies.
    """
    row, current, late = session.execute(
        with_details().where(Deliverable.id == deliverable_id)
    ).one()
    before = related_deliverables(session, user, [row.id], upstream=True)[row.id]
    after = related_deliverables(session, user, [row.id], upstream=False)[row.id]
    return DeliverableDetails(
        **summarize(user, row, current, late, before),
        description=row.description,
        predecessors=before,
        successors=after,
    )


def count_by_status(session: Session, project_id: int) -> dict[str, int]:
    """Count a project's deliverables by effective status, and the overdue ones.

    Args:
        session: Database session.
        project_id: The project.

    Returns:
        Counts by effective status, plus "Overdue".
    """
    rows = session.execute(
        select(effective_status(), is_overdue())
        .select_from(Deliverable)
        .join(Project, Project.id == Deliverable.project_id)
        .where(Deliverable.project_id == project_id)
    ).all()
    counts = dict.fromkeys((*DELIVERABLE_STATUSES, "Overdue"), 0)
    for current, late in rows:
        counts[current] += 1
        counts["Overdue"] += late
    return counts


def list_options(
    session: Session, user: User, project: Project | None
) -> DeliverableOptions:
    """List the choices for deliverable forms and filters.

    Args:
        session: Database session.
        user: The signed-in user.
        project: The project a form is for, which the user may view. Its
            managers may choose any resource as the owner.

    Returns:
        The choices.
    """
    projects = session.scalars(
        select(Project).where(visible_projects(user)).order_by(Project.code)
    )
    owners = select(Resource).order_by(Resource.full_name, Resource.id)
    if project is None or not can_manage_project(user, project):
        visible = select(Deliverable.owner_id).where(visible_deliverables(user))
        owners = owners.where(Resource.id.in_(visible))
    milestones = []
    if project is not None:
        milestones = session.scalars(
            select(Milestone)
            .where(Milestone.project_id == project.id)
            .order_by(Milestone.due_date, Milestone.id)
        )
    return DeliverableOptions(
        statuses=list(DELIVERABLE_STATUSES),
        priorities=list(PRIORITIES),
        projects=[
            NamedItem(id=row.id, name=f"{row.code} · {row.name}") for row in projects
        ],
        owners=[
            NamedItem(id=row.id, name=row.full_name) for row in session.scalars(owners)
        ],
        milestones=[NamedItem.model_validate(row) for row in milestones],
    )


def ensure_open(project: Project) -> None:
    """Fail when a project no longer accepts changes to its work.

    Args:
        project: The project.

    Raises:
        ApiError: 409 when the project is completed or cancelled.
    """
    if project.status in CLOSED_STATUSES:
        raise ApiError(
            409, f"This project is {project.status.lower()}. Reopen it first."
        )


def _names(rows: list[Deliverable]) -> str:
    """List deliverable names for a message."""
    shown = ", ".join(row.name for row in rows[:3])
    return f"{shown} and {len(rows) - 3} more" if len(rows) > 3 else shown


def _linked(deliverable_id: int, *, upstream: bool) -> Select:
    """Select the direct predecessors or successors of a deliverable."""
    link = DeliverableDependency
    near, far = link.successor_id, link.predecessor_id
    if not upstream:
        near, far = far, near
    return (
        select(Deliverable)
        .join(link, far == Deliverable.id)
        .where(near == deliverable_id)
    )


def _check_status_change(session: Session, row: Deliverable, status: str) -> None:
    """Apply the dependency rules to a status change.

    Messages name only deliverables of the same project, because the user may
    not be allowed to see others.
    """
    if row.id is None:
        return
    if status in ("In Progress", "Completed") and status != row.status:
        waiting = session.scalars(
            _linked(row.id, upstream=True).where(Deliverable.status != "Completed")
        ).all()
        if waiting:
            own = [item for item in waiting if item.project_id == row.project_id]
            names = _names(own) if len(own) == len(waiting) else "other work"
            raise ApiError(
                409, f"Blocked: complete {names} first.", "blocked", field="status"
            )
    if row.status == "Completed" and status != "Completed":
        finished = session.scalars(
            _linked(row.id, upstream=False).where(Deliverable.status == "Completed")
        ).all()
        if finished:
            own = [item for item in finished if item.project_id == row.project_id]
            names = _names(own) if len(own) == len(finished) else "dependent work"
            raise ApiError(
                409, f"Already completed: reopen {names} first.", field="status"
            )


def _apply_progress(session: Session, row: Deliverable, body: ProgressRequest) -> None:
    """Set the progress fields after checking the rules."""
    _check_status_change(session, row, body.status)
    completed = body.completion_date
    if body.status == "Completed":
        completed = completed or row.completion_date or today()
        if completed < row.start_date:
            raise ApiError(
                400,
                "Completion date must not be before the start date.",
                field="completion_date",
            )
    if row.milestone_id is not None and body.status != "Completed":
        milestone = session.get(Milestone, row.milestone_id, populate_existing=True)
        if milestone is not None and milestone.completed_date is not None:
            raise ApiError(
                409, "The milestone is already completed.", field="milestone_id"
            )
    row.status = body.status
    row.progress_percent = body.progress_percent
    row.actual_hours = body.actual_hours
    row.completion_date = completed


def save_deliverable(
    session: Session, project: Project, row: Deliverable, body: DeliverableRequest
) -> None:
    """Create or fully update a deliverable.

    Args:
        session: Database session.
        project: Its project, which the user must be allowed to manage.
        row: The deliverable to change.
        body: The requested values.

    Raises:
        ApiError: A value is not allowed.
    """
    lock_work(session)
    session.refresh(project)
    if row.id is not None:
        session.refresh(row)
    ensure_open(project)
    if body.owner_id is not None and not session.get(Resource, body.owner_id):
        raise ApiError(400, "Owner not found.", field="owner_id")
    if body.milestone_id is not None:
        milestone = session.get(Milestone, body.milestone_id)
        if milestone is None or milestone.project_id != project.id:
            raise ApiError(
                400, "Choose a milestone of this project.", field="milestone_id"
            )
    row.project_id = project.id
    for field in (
        "name",
        "description",
        "milestone_id",
        "owner_id",
        "start_date",
        "due_date",
        "priority",
        "estimated_hours",
    ):
        setattr(row, field, getattr(body, field))
    with session.no_autoflush:
        _apply_progress(session, row, body)
    session.add(row)
    session.commit()


def update_progress(session: Session, row: Deliverable, body: ProgressRequest) -> None:
    """Update only a deliverable's status, progress, effort and completion.

    Args:
        session: Database session.
        row: The deliverable, which the user must be allowed to update.
        body: The requested values.
    """
    lock_work(session)
    session.refresh(row)
    session.refresh(row.project)
    ensure_open(row.project)
    _apply_progress(session, row, body)
    session.commit()


def delete_deliverable(session: Session, row: Deliverable) -> None:
    """Delete a deliverable that nothing depends on.

    Args:
        session: Database session.
        row: The deliverable, which the user must be allowed to manage.

    Raises:
        ApiError: The deliverable may not be deleted.
    """
    lock_work(session)
    session.refresh(row.project)
    ensure_open(row.project)
    if session.scalar(_linked(row.id, upstream=False).limit(1)):
        raise ApiError(409, "Other deliverables depend on this one.")
    session.delete(row)
    session.commit()
