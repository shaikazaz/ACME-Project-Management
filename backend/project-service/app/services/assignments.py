"""Project assignments."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.dates import today
from app.errors import ApiError
from app.models import Project, ProjectAssignment, Resource
from app.schemas.common import Page
from app.schemas.projects import NamedItem
from app.schemas.resources import AssignmentRequest, ProjectAssignmentResponse
from app.services.deliverables import ensure_open, lock_work
from app.services.resources import with_workload
from app.services.workload import Period, full_time_hours, make_workload


def list_assignments(
    session: Session, project: Project
) -> Page[ProjectAssignmentResponse]:
    """List a project's assignments with everyone's total workload.

    Args:
        session: Database session.
        project: The project, which the user must be allowed to view.

    Returns:
        The assignments, sorted by resource name.
    """
    rows = session.scalars(
        select(ProjectAssignment)
        .join(Resource, Resource.id == ProjectAssignment.resource_id)
        .where(ProjectAssignment.project_id == project.id)
        .options(joinedload(ProjectAssignment.resource))
        .order_by(Resource.full_name, ProjectAssignment.id)
    ).all()
    query, _ = with_workload(Period(today()))
    loads = {
        resource.id: (current, peak)
        for resource, current, peak in session.execute(
            query.where(Resource.id.in_([row.resource_id for row in rows]))
        )
    }
    week = full_time_hours(session)
    items = [
        ProjectAssignmentResponse(
            id=row.id,
            resource=NamedItem(id=row.resource_id, name=row.resource.full_name),
            job_title=row.resource.job_title,
            availability=row.resource.availability,
            project_role=row.project_role,
            allocation_percent=row.allocation_percent,
            allocation_hours=float(round(row.allocation_percent * week / 100, 2)),
            start_date=row.start_date,
            end_date=row.end_date,
            workload=make_workload(
                row.resource.capacity_percent, *loads[row.resource_id], week
            ),
        )
        for row in rows
    ]
    return Page(items=items, total=len(items))


def save_assignment(
    session: Session,
    project: Project,
    row: ProjectAssignment,
    body: AssignmentRequest,
) -> None:
    """Create or update an assignment.

    Over-allocation is reported but not refused: a manager may need it for a
    short time, and the report makes it visible.

    Args:
        session: Database session.
        project: Its project, which the user must be allowed to manage.
        row: The assignment to change.
        body: The requested values.

    Raises:
        ApiError: The assignment is not allowed.
    """
    lock_work(session)
    session.refresh(project)
    ensure_open(project)
    if row.id is not None and body.resource_id != row.resource_id:
        raise ApiError(
            400, "Create a new assignment for another person.", field="resource_id"
        )
    if row.id is None:
        resource = session.get(Resource, body.resource_id)
        if resource is None:
            raise ApiError(400, "Resource not found.", field="resource_id")
        if resource.availability == "Unavailable":
            raise ApiError(
                409, f"{resource.full_name} is unavailable.", field="resource_id"
            )
    row.project_id = project.id
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    session.add(row)
    session.commit()


def delete_assignment(
    session: Session, project: Project, row: ProjectAssignment
) -> None:
    """Remove a resource from a project.

    Args:
        session: Database session.
        project: Its project, which the user must be allowed to manage.
        row: The assignment.
    """
    lock_work(session)
    session.refresh(project)
    ensure_open(project)
    session.delete(row)
    session.commit()
