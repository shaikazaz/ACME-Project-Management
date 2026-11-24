"""Assignment endpoints, all below their project."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.auth.scopes import find_visible_project, managed_project
from app.errors import ApiError
from app.models import Project, ProjectAssignment, User
from app.schemas.common import Page
from app.schemas.resources import AssignmentRequest, ProjectAssignmentResponse
from app.services import assignments as service

router = APIRouter(prefix="/projects/{project_id}/assignments", tags=["assignments"])

Viewer = Annotated[User, Depends(require(Permission.VIEW_RESOURCES))]
ManagedProject = Annotated[
    Project, Depends(managed_project(Permission.ASSIGN_RESOURCES))
]


def find_assignment(
    assignment_id: int, project: ManagedProject, session: SessionDep
) -> ProjectAssignment:
    """Load an assignment of a project the user manages, or fail with 404."""
    row = session.get(ProjectAssignment, assignment_id)
    if row is None or row.project_id != project.id:
        raise ApiError(404, "Assignment not found.")
    return row


TargetAssignment = Annotated[ProjectAssignment, Depends(find_assignment)]


def _describe(
    session: SessionDep, project: Project, row_id: int
) -> ProjectAssignmentResponse:
    """Return one assignment with the resource's workload."""
    page = service.list_assignments(session, project)
    return next(item for item in page.items if item.id == row_id)


@router.get("")
def list_assignments(
    project_id: int, user: Viewer, session: SessionDep
) -> Page[ProjectAssignmentResponse]:
    """List the assignments of a project the user may view."""
    project = find_visible_project(session, user, project_id)
    return service.list_assignments(session, project)


@router.post("", status_code=201)
def create_assignment(
    body: AssignmentRequest, project: ManagedProject, session: SessionDep
) -> ProjectAssignmentResponse:
    """Assign a resource to a project the user manages."""
    row = ProjectAssignment()
    service.save_assignment(session, project, row, body)
    return _describe(session, project, row.id)


@router.put("/{assignment_id}")
def update_assignment(
    body: AssignmentRequest,
    row: TargetAssignment,
    project: ManagedProject,
    session: SessionDep,
) -> ProjectAssignmentResponse:
    """Change an assignment's role, percentage or dates."""
    service.save_assignment(session, project, row, body)
    return _describe(session, project, row.id)


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(
    row: TargetAssignment, project: ManagedProject, session: SessionDep
) -> None:
    """Remove a resource from a project."""
    service.delete_assignment(session, project, row)
