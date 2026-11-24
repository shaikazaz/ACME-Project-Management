"""Resource and workload endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.errors import ApiError
from app.models import Resource, User
from app.schemas.common import Page
from app.schemas.resources import (
    Availability,
    ResourceDetails,
    ResourceOptions,
    ResourceRequest,
    ResourceSummary,
    WorkloadReport,
)
from app.services import resources as service
from app.services.workload import Period

router = APIRouter(prefix="/resources", tags=["resources"])

Viewer = Annotated[User, Depends(require(Permission.VIEW_RESOURCES))]
Reporter = Annotated[User, Depends(require(Permission.VIEW_REPORTS))]
Admin = Annotated[User, Depends(require(Permission.MANAGE_RESOURCES))]


def find_period(
    period_from: date | None = None, period_to: date | None = None
) -> Period:
    """Read the reporting period. It starts today unless stated otherwise."""
    return service.make_period(period_from, period_to)


PeriodDep = Annotated[Period, Depends(find_period)]


def find_resource(resource_id: int, session: SessionDep, _: Admin) -> Resource:
    """Load the resource named in the path for an admin, or fail with 404."""
    row = session.get(Resource, resource_id)
    if row is None:
        raise ApiError(404, "Resource not found.")
    return row


TargetResource = Annotated[Resource, Depends(find_resource)]


@router.get("")
def list_resources(
    user: Viewer,
    session: SessionDep,
    period: PeriodDep,
    search: Annotated[str, Query(max_length=100)] = "",
    department_id: int | None = None,
    availability: Annotated[list[Availability] | None, Query()] = None,
    skill: Annotated[str, Query(max_length=50)] = "",
    over_allocated: bool | None = None,
    sort: Literal[service.SORT_FIELDS] = "name",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Page[ResourceSummary]:
    """Search and filter resources with their workload."""
    return service.search_resources(
        session,
        user,
        search=search.strip(),
        department_id=department_id,
        availability=availability or [],
        skill=skill.strip(),
        over_allocated=over_allocated,
        period=period,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get("/options")
def read_options(user: Viewer, session: SessionDep) -> ResourceOptions:
    """Return the choices for resource forms and filters."""
    return service.list_options(session, user)


@router.get("/workload")
def read_workload(
    user: Reporter, session: SessionDep, period: PeriodDep
) -> WorkloadReport:
    """Summarize the workload of all resources."""
    return service.report_workload(session, user, period)


@router.post("", status_code=201)
def create_resource(
    body: ResourceRequest, user: Admin, session: SessionDep, period: PeriodDep
) -> ResourceDetails:
    """Create a resource."""
    row = Resource()
    service.save_resource(session, row, body)
    return service.describe_resource(session, user, row.id, period)


@router.get("/{resource_id}")
def read_resource(
    resource_id: int, user: Viewer, session: SessionDep, period: PeriodDep
) -> ResourceDetails:
    """Return one resource with its assignments."""
    return service.describe_resource(session, user, resource_id, period)


@router.put("/{resource_id}")
def update_resource(
    body: ResourceRequest,
    row: TargetResource,
    user: Admin,
    session: SessionDep,
    period: PeriodDep,
) -> ResourceDetails:
    """Update a resource."""
    service.save_resource(session, row, body)
    return service.describe_resource(session, user, row.id, period)


@router.delete("/{resource_id}", status_code=204)
def delete_resource(row: TargetResource, session: SessionDep) -> None:
    """Delete a resource without assignments or deliverables."""
    session.delete(row)
    session.commit()
