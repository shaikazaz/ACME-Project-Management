"""Record-level rules: which projects and deliverables a user may use.

Admins may use everything. Project managers may use projects they manage.
Team members may view projects they are assigned to, and update their own
deliverables. Records a user may not see return 404, so their existence is
not revealed.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from sqlalchemy import ColumnElement, false, or_, select, true

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission, Role
from app.errors import ApiError
from app.models import Deliverable, Project, ProjectAssignment, Resource, User


def visible_projects(user: User) -> ColumnElement[bool]:
    """Build the filter for the projects a user may view.

    Args:
        user: The signed-in user.

    Returns:
        A condition for a Project query.
    """
    if user.role == Role.ADMIN:
        return true()
    own_resource = (
        select(Resource.id).where(Resource.user_id == user.id).scalar_subquery()
    )
    assigned = or_(
        Project.id.in_(
            select(ProjectAssignment.project_id).where(
                ProjectAssignment.resource_id == own_resource
            )
        ),
        Project.id.in_(
            select(Deliverable.project_id).where(Deliverable.owner_id == own_resource)
        ),
    )
    if user.role == Role.PROJECT_MANAGER:
        return or_(Project.manager_id == user.id, assigned)
    return assigned


def managed_projects(user: User) -> ColumnElement[bool]:
    """Build the filter for the projects a user may manage.

    Args:
        user: The signed-in user.

    Returns:
        A condition for a query that includes Project.
    """
    if user.role == Role.ADMIN:
        return true()
    if user.role == Role.PROJECT_MANAGER:
        return Project.manager_id == user.id
    return false()


def visible_deliverables(user: User) -> ColumnElement[bool]:
    """Build the filter for the deliverables a user may view.

    Args:
        user: The signed-in user.

    Returns:
        A condition for a Deliverable query.
    """
    if user.role == Role.ADMIN:
        return true()
    owned = Deliverable.owner_id.in_(
        select(Resource.id).where(Resource.user_id == user.id)
    )
    if user.role == Role.PROJECT_MANAGER:
        managed = select(Project.id).where(Project.manager_id == user.id)
        return or_(Deliverable.project_id.in_(managed), owned)
    return owned


def can_manage_project(user: User, project: Project) -> bool:
    """Check whether a user manages a project.

    Args:
        user: The signed-in user.
        project: The project.

    Returns:
        True for admins and for the project's own manager.
    """
    return user.role == Role.ADMIN or (
        user.role == Role.PROJECT_MANAGER and project.manager_id == user.id
    )


def find_visible_project(session: SessionDep, user: User, project_id: int) -> Project:
    """Load a project the user may view, or fail with 404."""
    project = session.scalar(
        select(Project).where(Project.id == project_id, visible_projects(user))
    )
    if project is None:
        raise ApiError(404, "Project not found.")
    return project


def managed_project(permission: Permission) -> Callable[..., Project]:
    """Create a dependency that loads a project the user may manage.

    Args:
        permission: The permission also required.

    Returns:
        A dependency that returns the project, or fails with 403 or 404.
    """

    def load(
        project_id: int,
        session: SessionDep,
        user: Annotated[User, Depends(require(permission))],
    ) -> Project:
        """Load the project named in the path."""
        project = find_visible_project(session, user, project_id)
        if not can_manage_project(user, project):
            raise ApiError(403, "You do not manage this project.")
        return project

    return load


def find_visible_deliverable(
    session: SessionDep, user: User, deliverable_id: int
) -> Deliverable:
    """Load a deliverable the user may view, or fail with 404."""
    deliverable = session.scalar(
        select(Deliverable).where(
            Deliverable.id == deliverable_id, visible_deliverables(user)
        )
    )
    if deliverable is None:
        raise ApiError(404, "Deliverable not found.")
    return deliverable


def managed_deliverable(permission: Permission) -> Callable[..., Deliverable]:
    """Create a dependency that loads a deliverable the user may manage.

    Args:
        permission: The permission also required.

    Returns:
        A dependency that returns the deliverable, or fails with 403 or 404.
    """

    def load(
        deliverable_id: int,
        session: SessionDep,
        user: Annotated[User, Depends(require(permission))],
    ) -> Deliverable:
        """Load the deliverable named in the path."""
        deliverable = find_visible_deliverable(session, user, deliverable_id)
        if not can_manage_project(user, deliverable.project):
            raise ApiError(403, "You do not manage this project.")
        return deliverable

    return load


def find_updatable_deliverable(
    deliverable_id: int,
    session: SessionDep,
    user: Annotated[User, Depends(require(Permission.UPDATE_DELIVERABLE_STATUS))],
) -> Deliverable:
    """Load a deliverable whose status the user may update, or fail with 404.

    Everyone who can see a deliverable may update its status: its owner, the
    project's manager and admins.
    """
    return find_visible_deliverable(session, user, deliverable_id)
