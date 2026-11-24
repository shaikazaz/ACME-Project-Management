"""Project endpoints."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, SessionDep, require
from app.auth.permissions import Permission, has_permission
from app.auth.scopes import find_visible_project, managed_project
from app.models import Department, Project, User
from app.models.base import PRIORITIES
from app.models.projects import PROJECT_STATUSES
from app.schemas.common import Page
from app.schemas.projects import (
    BudgetStatus,
    NamedItem,
    Priority,
    ProjectDetails,
    ProjectOptions,
    ProjectRequest,
    ProjectStatus,
    ProjectSummary,
    RiskLevel,
)
from app.services import projects as service
from app.services.budgets import BUDGET_STATUSES
from app.services.risk import RISK_LEVELS

router = APIRouter(prefix="/projects", tags=["projects"])

Creator = Annotated[User, Depends(require(Permission.CREATE_PROJECTS))]
Deleter = Annotated[User, Depends(require(Permission.DELETE_PROJECTS))]
ManagedProject = Annotated[Project, Depends(managed_project(Permission.EDIT_PROJECTS))]


@router.get("")
def list_projects(
    session: SessionDep,
    user: CurrentUser,
    search: Annotated[str, Query(max_length=100)] = "",
    status: Annotated[list[ProjectStatus] | None, Query()] = None,
    priority: Annotated[list[Priority] | None, Query()] = None,
    department_id: int | None = None,
    manager_id: int | None = None,
    budget_status: Annotated[list[BudgetStatus] | None, Query()] = None,
    risk: Annotated[list[RiskLevel] | None, Query()] = None,
    start_from: date | None = None,
    start_to: date | None = None,
    end_from: date | None = None,
    end_to: date | None = None,
    sort: Literal[service.SORT_FIELDS] = "end_date",
    order: Literal["asc", "desc"] = "asc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Page[ProjectSummary]:
    """Search and filter the projects the user may view."""
    return service.search_projects(
        session,
        user,
        search=search.strip(),
        statuses=status or [],
        priorities=priority or [],
        department_id=department_id,
        manager_id=manager_id,
        budget_statuses=budget_status or [],
        risk_levels=risk or [],
        start_from=start_from,
        start_to=start_to,
        end_from=end_from,
        end_to=end_to,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get("/options")
def read_options(session: SessionDep, user: CurrentUser) -> ProjectOptions:
    """Return the choices for project forms and filters."""
    manages = has_permission(user.role, Permission.MANAGE_BUDGETS)
    departments = session.scalars(select(Department).order_by(Department.name))
    return ProjectOptions(
        statuses=list(PROJECT_STATUSES),
        priorities=list(PRIORITIES),
        budget_statuses=list(BUDGET_STATUSES) if manages else [],
        risk_levels=list(RISK_LEVELS) if manages else [],
        departments=[NamedItem.model_validate(row) for row in departments],
        managers=service.list_managers(session, user),
    )


@router.post("", status_code=201)
def create_project(
    body: ProjectRequest, session: SessionDep, user: Creator
) -> ProjectDetails:
    """Create a project."""
    project = Project()
    service.save_project(session, user, project, body)
    return service.describe_project(session, user, project.id)


@router.get("/{project_id}")
def read_project(
    project_id: int, session: SessionDep, user: CurrentUser
) -> ProjectDetails:
    """Return one project."""
    project = find_visible_project(session, user, project_id)
    return service.describe_project(session, user, project.id)


@router.put("/{project_id}")
def update_project(
    body: ProjectRequest,
    project: ManagedProject,
    session: SessionDep,
    user: CurrentUser,
) -> ProjectDetails:
    """Update a project the user manages."""
    service.save_project(session, user, project, body)
    return service.describe_project(session, user, project.id)


@router.delete("/{project_id}", status_code=204)
def delete_project(
    project_id: int,
    session: SessionDep,
    _: Deleter,
    confirm_code: Annotated[str, Query(max_length=30)] = "",
) -> None:
    """Delete a planned or cancelled project after confirming its code."""
    service.delete_project(session, project_id, confirm_code)
