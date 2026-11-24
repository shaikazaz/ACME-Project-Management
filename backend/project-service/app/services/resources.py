"""Resource queries and business rules."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Row, Select, and_, func, or_, select, true
from sqlalchemy.orm import Session, joinedload

from app.auth.permissions import Permission, has_permission
from app.auth.scopes import visible_projects
from app.auth.shared import is_shared, visible_email
from app.dates import today
from app.errors import ApiError
from app.models import Department, Project, ProjectAssignment, Resource, User
from app.models.people import AVAILABILITY
from app.schemas.common import Page
from app.schemas.projects import NamedItem
from app.schemas.resources import (
    DepartmentWorkload,
    ResourceAssignment,
    ResourceDetails,
    ResourceOptions,
    ResourceRequest,
    ResourceSummary,
    WorkloadReport,
)
from app.services.deliverables import CLOSED_STATUSES
from app.services.workload import (
    Period,
    current_load,
    full_time_hours,
    make_workload,
    peak_loads,
    percent_of,
    workload_periods,
)

HIDDEN_PROJECT = "Another project"
SORT_FIELDS = (
    "name",
    "code",
    "department",
    "capacity",
    "current",
    "peak",
    "utilization",
)


def with_workload(period: Period) -> tuple[Select, dict]:
    """Select resources with their current and peak load.

    Args:
        period: The period to find the peak in.

    Returns:
        The query, and the SQL expression for every sort field plus
        "over_allocated".
    """
    peaks = peak_loads(period)
    peak = func.coalesce(peaks.c.peak, 0)
    current = current_load()
    query = (
        select(Resource, current, peak)
        .join(Department, Department.id == Resource.department_id)
        .outerjoin(peaks, peaks.c.resource_id == Resource.id)
        .options(joinedload(Resource.department), joinedload(Resource.user))
    )
    expressions = {
        "name": func.lower(Resource.full_name),
        "code": Resource.employee_code,
        "department": func.lower(Department.name),
        "capacity": Resource.capacity_percent,
        "current": current,
        "peak": peak,
        # Allocation without any capacity ranks above everything else.
        "utilization": func.coalesce(
            peak / func.nullif(Resource.capacity_percent, 0), peak * 1_000_000
        ),
        "over_allocated": peak > Resource.capacity_percent,
    }
    return query, expressions


def summarize(user: User, row: Row, week: Decimal) -> dict:
    """Describe a resource.

    Args:
        user: The signed-in user, who must be allowed to view resources.
        row: The resource with its current and peak load.
        week: Weekly hours of a 100% allocation.

    Returns:
        Values for ResourceSummary.
    """
    resource, current, peak = row
    account = resource.user
    return {
        "id": resource.id,
        "employee_code": resource.employee_code,
        "full_name": resource.full_name,
        "email": visible_email(user, resource.email),
        "department": NamedItem.model_validate(resource.department),
        "job_title": resource.job_title,
        "skills": resource.skills,
        "availability": resource.availability,
        "user": NamedItem(id=account.id, name=account.full_name) if account else None,
        "workload": make_workload(resource.capacity_percent, current, peak, week),
        "needs_cover": resource.availability != "Available" and current > 0,
        "can_edit": has_permission(user.role, Permission.MANAGE_RESOURCES),
        "updated_at": resource.updated_at,
    }


def search_resources(
    session: Session,
    user: User,
    *,
    search: str,
    department_id: int | None,
    availability: list[str],
    skill: str,
    over_allocated: bool | None,
    period: Period,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> Page[ResourceSummary]:
    """Search resources.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to view resources.
        search: Text to find in the name, code, email, job title or skills.
        department_id: Department to include.
        availability: Availability values to include; empty means all.
        skill: A skill the resource must have.
        over_allocated: Whether to include only over-allocated or only others.
        period: The period to find the peak load in.
        sort: One of SORT_FIELDS.
        descending: Whether to reverse the order.
        limit: Page size.
        offset: Number of results to skip.

    Returns:
        One page of resources and the total number of matches.
    """
    query, expressions = with_workload(period)
    skills = func.array_to_string(Resource.skills, "\n")
    conditions = [true()]
    if search:
        columns = (
            Resource.full_name,
            Resource.employee_code,
            Resource.job_title,
            skills,
            # A search must not guess a hidden email.
            *(() if is_shared(user) else (Resource.email,)),
        )
        conditions.append(
            or_(*(column.icontains(search, autoescape=True) for column in columns))
        )
    if department_id is not None:
        conditions.append(Resource.department_id == department_id)
    if availability:
        conditions.append(Resource.availability.in_(availability))
    if skill:
        one = func.unnest(Resource.skills).table_valued("value").render_derived()
        matches = select(one.c.value).where(func.lower(one.c.value) == skill.lower())
        conditions.append(matches.correlate(Resource).exists())
    if over_allocated is not None:
        conditions.append(expressions["over_allocated"] == over_allocated)

    query = query.where(and_(*conditions))
    total = session.scalar(
        select(func.count()).select_from(
            query.with_only_columns(Resource.id).order_by(None).subquery()
        )
    )
    order = expressions[sort]
    rows = session.execute(
        query.order_by(order.desc() if descending else order.asc(), Resource.id)
        .limit(limit)
        .offset(offset)
    )
    week = full_time_hours(session)
    items = [ResourceSummary(**summarize(user, row, week)) for row in rows]
    return Page(items=items, total=total)


def describe_resource(
    session: Session, user: User, resource_id: int, period: Period
) -> ResourceDetails:
    """Return one resource in full.

    Every assignment is included, because the totals need them all. Project
    details are hidden when the user cannot see the project.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to view resources.
        resource_id: The resource.
        period: The period to find the peak load in.

    Returns:
        The resource with its assignments and workload over time.

    Raises:
        ApiError: 404 when the resource does not exist.
    """
    query, _ = with_workload(period)
    row = session.execute(query.where(Resource.id == resource_id)).one_or_none()
    if row is None:
        raise ApiError(404, "Resource not found.")
    rows = session.execute(
        select(ProjectAssignment, Project, visible_projects(user))
        .join(Project, Project.id == ProjectAssignment.project_id)
        .where(ProjectAssignment.resource_id == resource_id)
        .order_by(ProjectAssignment.start_date, ProjectAssignment.id)
    ).all()
    assignments = [
        ResourceAssignment(
            project_id=project.id if visible else None,
            project_name=project.name if visible else HIDDEN_PROJECT,
            project_code=project.code if visible else None,
            project_status=project.status,
            project_role=item.project_role if visible else "",
            allocation_percent=item.allocation_percent,
            start_date=item.start_date,
            end_date=item.end_date,
            counts=project.status not in CLOSED_STATUSES,
        )
        for item, project, visible in rows
    ]
    spans = [
        (item.start_date, item.end_date, item.allocation_percent)
        for item, project, _ in rows
        if project.status not in CLOSED_STATUSES
    ]
    return ResourceDetails(
        **summarize(user, row, full_time_hours(session)),
        assignments=assignments,
        periods=workload_periods(spans, row[0].capacity_percent, period.start),
    )


def list_options(session: Session, user: User) -> ResourceOptions:
    """List the choices for resource forms and filters."""
    departments = session.scalars(select(Department).order_by(Department.name))
    skills = session.scalars(select(func.unnest(Resource.skills)).distinct())
    users = []
    if has_permission(user.role, Permission.MANAGE_RESOURCES) and not is_shared(user):
        linked = select(Resource.user_id).where(Resource.user_id.is_not(None))
        users = session.scalars(
            select(User).where(User.id.not_in(linked)).order_by(User.full_name, User.id)
        )
    return ResourceOptions(
        availability=list(AVAILABILITY),
        departments=[NamedItem.model_validate(row) for row in departments],
        skills=sorted(skills, key=str.lower),
        users=[
            NamedItem(id=row.id, name=f"{row.full_name} ({row.email})") for row in users
        ],
    )


def save_resource(session: Session, row: Resource, body: ResourceRequest) -> None:
    """Create or update a resource.

    Args:
        session: Database session.
        row: The resource to change.
        body: The requested values.

    Raises:
        ApiError: A value is not allowed.
    """
    if not session.get(Department, body.department_id):
        raise ApiError(400, "Department not found.", field="department_id")
    if body.user_id is not None and not session.get(User, body.user_id):
        raise ApiError(400, "Account not found.", field="user_id")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    session.add(row)
    session.commit()


def report_workload(session: Session, user: User, period: Period) -> WorkloadReport:
    """Summarize the workload of all resources.

    Department and overall utilization compare the sum of everyone's peak with
    the sum of everyone's capacity.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to view resources.
        period: The period to find the peak loads in.

    Returns:
        The report.
    """
    query, _ = with_workload(period)
    week = full_time_hours(session)
    items = [
        ResourceSummary(**summarize(user, row, week)) for row in session.execute(query)
    ]

    def total(rows: list[ResourceSummary], field: str) -> Decimal:
        """Add up one workload value."""
        values = (Decimal(str(getattr(row.workload, field))) for row in rows)
        return sum(values, Decimal(0))

    def over(rows: list[ResourceSummary]) -> int:
        """Count over-allocated resources."""
        return sum(row.workload.is_over_allocated for row in rows)

    groups: dict[int, list[ResourceSummary]] = {}
    for item in items:
        groups.setdefault(item.department.id, []).append(item)
    departments = []
    for rows in groups.values():
        capacity, peak = total(rows, "capacity_percent"), total(rows, "peak_percent")
        departments.append(
            DepartmentWorkload(
                department=rows[0].department,
                resource_count=len(rows),
                over_allocated_count=over(rows),
                capacity_percent=capacity,
                peak_percent=peak,
                utilization_percent=percent_of(peak, capacity),
            )
        )
    departments.sort(key=lambda row: row.department.name.lower())

    loads = [item.workload for item in items]
    capacity, peak = total(items, "capacity_percent"), total(items, "peak_percent")
    unallocated = sum(load.peak_percent == 0 for load in loads)
    full = sum(load.peak_percent == load.capacity_percent > 0 for load in loads)
    return WorkloadReport(
        period_from=period.start,
        period_to=period.end,
        resource_count=len(items),
        over_allocated_count=over(items),
        fully_allocated_count=full,
        partly_allocated_count=len(items) - over(items) - full - unallocated,
        unallocated_count=unallocated,
        needs_cover_count=sum(item.needs_cover for item in items),
        capacity_percent=capacity,
        peak_percent=peak,
        utilization_percent=percent_of(peak, capacity),
        departments=departments,
    )


def make_period(start: date | None, end: date | None) -> Period:
    """Build a period that starts today unless stated otherwise.

    Raises:
        ApiError: 400 when the period ends before it starts.
    """
    period = Period(start or today(), end)
    if period.end is not None and period.end < period.start:
        raise ApiError(400, "The period ends before it starts.", field="period_to")
    return period
