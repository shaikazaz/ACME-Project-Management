"""Milestone queries and business rules."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dates import today
from app.errors import ApiError
from app.models import Deliverable, Milestone, Project
from app.schemas.common import Page
from app.schemas.deliverables import MilestoneRequest, MilestoneResponse
from app.services.deliverables import ensure_open, lock_work


def list_milestones(session: Session, project: Project) -> Page[MilestoneResponse]:
    """List a project's milestones.

    Args:
        session: Database session.
        project: The project, which the user must be allowed to view.

    Returns:
        The milestones with their deliverable counts.
    """
    finished = func.count().filter(Deliverable.status == "Completed")
    counts = {
        key: (total, done)
        for key, total, done in session.execute(
            select(Deliverable.milestone_id, func.count(), finished)
            .where(Deliverable.project_id == project.id)
            .group_by(Deliverable.milestone_id)
        )
    }
    rows = session.scalars(
        select(Milestone)
        .where(Milestone.project_id == project.id)
        .order_by(Milestone.due_date, Milestone.id)
    )
    items = []
    for row in rows:
        total, done = counts.get(row.id, (0, 0))
        items.append(
            MilestoneResponse(
                id=row.id,
                name=row.name,
                description=row.description,
                due_date=row.due_date,
                completed_date=row.completed_date,
                is_overdue=row.completed_date is None
                and row.due_date < today()
                and project.status != "Cancelled",
                deliverable_count=total,
                completed_count=done,
            )
        )
    return Page(items=items, total=len(items))


def save_milestone(
    session: Session, project: Project, row: Milestone, body: MilestoneRequest
) -> None:
    """Create or update a milestone.

    Args:
        session: Database session.
        project: Its project, which the user must be allowed to manage.
        row: The milestone to change.
        body: The requested values.

    Raises:
        ApiError: The change is not allowed.
    """
    lock_work(session)
    session.refresh(project)
    ensure_open(project)
    if body.completed_date is not None and row.id is not None:
        unfinished = session.scalar(
            select(func.count())
            .select_from(Deliverable)
            .where(
                Deliverable.milestone_id == row.id, Deliverable.status != "Completed"
            )
        )
        if unfinished:
            raise ApiError(
                409,
                f"{unfinished} of its deliverables are not completed.",
                field="completed_date",
            )
    row.project_id = project.id
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    session.add(row)
    session.commit()


def delete_milestone(session: Session, project: Project, row: Milestone) -> None:
    """Delete a milestone. Its deliverables are kept.

    Args:
        session: Database session.
        project: Its project, which the user must be allowed to manage.
        row: The milestone.
    """
    lock_work(session)
    session.refresh(project)
    ensure_open(project)
    session.delete(row)
    session.commit()
