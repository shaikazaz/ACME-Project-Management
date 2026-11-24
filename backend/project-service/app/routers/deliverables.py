"""Deliverable and dependency endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.permissions import Permission
from app.auth.scopes import (
    find_updatable_deliverable,
    find_visible_deliverable,
    find_visible_project,
    managed_deliverable,
    managed_project,
)
from app.models import Deliverable, Project
from app.schemas.common import Page
from app.schemas.deliverables import (
    DeliverableDetails,
    DeliverableOptions,
    DeliverableRequest,
    DeliverableStatus,
    DeliverableSummary,
    DependencyChain,
    DependencyRequest,
    ProgressRequest,
)
from app.schemas.projects import Priority
from app.services import deliverables as service
from app.services import dependencies

router = APIRouter(tags=["deliverables"])

ManagedProject = Annotated[
    Project, Depends(managed_project(Permission.MANAGE_DELIVERABLES))
]
ChainProject = Annotated[
    Project, Depends(managed_project(Permission.MANAGE_DEPENDENCIES))
]
Managed = Annotated[
    Deliverable, Depends(managed_deliverable(Permission.MANAGE_DELIVERABLES))
]
Successor = Annotated[
    Deliverable, Depends(managed_deliverable(Permission.MANAGE_DEPENDENCIES))
]
Updatable = Annotated[Deliverable, Depends(find_updatable_deliverable)]


@router.get("/deliverables")
def list_deliverables(
    session: SessionDep,
    user: CurrentUser,
    search: Annotated[str, Query(max_length=100)] = "",
    status: Annotated[list[DeliverableStatus] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    project_id: int | None = None,
    owner_id: int | None = None,
    milestone_id: int | None = None,
    overdue: bool | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    sort: Literal[service.SORT_FIELDS] = "due_date",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Page[DeliverableSummary]:
    """Search and filter the deliverables the user may view."""
    return service.search_deliverables(
        session,
        user,
        search=search.strip(),
        statuses=status or [],
        priorities=priority or [],
        project_id=project_id,
        owner_id=owner_id,
        milestone_id=milestone_id,
        overdue=overdue,
        due_from=due_from,
        due_to=due_to,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get("/deliverables/options")
def read_options(
    session: SessionDep, user: CurrentUser, project_id: int | None = None
) -> DeliverableOptions:
    """Return the choices for deliverable forms and filters."""
    project = None
    if project_id is not None:
        project = find_visible_project(session, user, project_id)
    return service.list_options(session, user, project)


@router.post("/projects/{project_id}/deliverables", status_code=201)
def create_deliverable(
    body: DeliverableRequest,
    project: ManagedProject,
    session: SessionDep,
    user: CurrentUser,
) -> DeliverableDetails:
    """Create a deliverable in a project the user manages."""
    row = Deliverable()
    service.save_deliverable(session, project, row, body)
    return service.describe_deliverable(session, user, row.id)


@router.get("/projects/{project_id}/dependencies")
def read_chain(
    project: ChainProject, session: SessionDep, user: CurrentUser
) -> DependencyChain:
    """Return the dependency chain of a project the user manages."""
    return dependencies.describe_chain(session, user, project)


@router.get("/deliverables/{deliverable_id}")
def read_deliverable(
    deliverable_id: int, session: SessionDep, user: CurrentUser
) -> DeliverableDetails:
    """Return one deliverable."""
    row = find_visible_deliverable(session, user, deliverable_id)
    return service.describe_deliverable(session, user, row.id)


@router.put("/deliverables/{deliverable_id}")
def update_deliverable(
    body: DeliverableRequest, row: Managed, session: SessionDep, user: CurrentUser
) -> DeliverableDetails:
    """Update every field of a deliverable."""
    service.save_deliverable(session, row.project, row, body)
    return service.describe_deliverable(session, user, row.id)


@router.patch("/deliverables/{deliverable_id}/progress")
def update_progress(
    body: ProgressRequest, row: Updatable, session: SessionDep, user: CurrentUser
) -> DeliverableDetails:
    """Update a deliverable's status, progress and actual effort."""
    service.update_progress(session, row, body)
    return service.describe_deliverable(session, user, row.id)


@router.delete("/deliverables/{deliverable_id}", status_code=204)
def delete_deliverable(row: Managed, session: SessionDep) -> None:
    """Delete a deliverable that nothing depends on."""
    service.delete_deliverable(session, row)


@router.post("/deliverables/{deliverable_id}/predecessors", status_code=201)
def add_predecessor(
    body: DependencyRequest, row: Successor, session: SessionDep, user: CurrentUser
) -> DeliverableDetails:
    """Make a deliverable wait for another one."""
    dependencies.add_dependency(session, user, row, body.predecessor_id)
    return service.describe_deliverable(session, user, row.id)


@router.delete(
    "/deliverables/{deliverable_id}/predecessors/{predecessor_id}", status_code=204
)
def remove_predecessor(
    predecessor_id: int, row: Successor, session: SessionDep
) -> None:
    """Stop a deliverable from waiting for another one."""
    dependencies.remove_dependency(session, row, predecessor_id)
