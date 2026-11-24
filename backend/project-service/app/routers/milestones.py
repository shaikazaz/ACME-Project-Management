"""Milestone endpoints, all below their project."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.permissions import Permission
from app.auth.scopes import find_visible_project, managed_project
from app.errors import ApiError
from app.models import Milestone, Project
from app.schemas.common import Page
from app.schemas.deliverables import MilestoneRequest, MilestoneResponse
from app.services import milestones as service

router = APIRouter(prefix="/projects/{project_id}/milestones", tags=["milestones"])

ManagedProject = Annotated[
    Project, Depends(managed_project(Permission.MANAGE_DELIVERABLES))
]


def find_milestone(
    milestone_id: int, project: ManagedProject, session: SessionDep
) -> Milestone:
    """Load a milestone of a project the user manages, or fail with 404."""
    row = session.get(Milestone, milestone_id)
    if row is None or row.project_id != project.id:
        raise ApiError(404, "Milestone not found.")
    return row


TargetMilestone = Annotated[Milestone, Depends(find_milestone)]


def _describe(session: SessionDep, project: Project, row_id: int) -> MilestoneResponse:
    """Return one milestone with its counts."""
    page = service.list_milestones(session, project)
    return next(item for item in page.items if item.id == row_id)


@router.get("")
def list_milestones(
    project_id: int, session: SessionDep, user: CurrentUser
) -> Page[MilestoneResponse]:
    """List the milestones of a project the user may view."""
    project = find_visible_project(session, user, project_id)
    return service.list_milestones(session, project)


@router.post("", status_code=201)
def create_milestone(
    body: MilestoneRequest, project: ManagedProject, session: SessionDep
) -> MilestoneResponse:
    """Create a milestone."""
    row = Milestone()
    service.save_milestone(session, project, row, body)
    return _describe(session, project, row.id)


@router.put("/{milestone_id}")
def update_milestone(
    body: MilestoneRequest,
    row: TargetMilestone,
    project: ManagedProject,
    session: SessionDep,
) -> MilestoneResponse:
    """Update a milestone."""
    service.save_milestone(session, project, row, body)
    return _describe(session, project, row.id)


@router.delete("/{milestone_id}", status_code=204)
def delete_milestone(
    row: TargetMilestone, project: ManagedProject, session: SessionDep
) -> None:
    """Delete a milestone and keep its deliverables."""
    service.delete_milestone(session, project, row)
