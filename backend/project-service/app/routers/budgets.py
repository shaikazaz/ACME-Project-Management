"""Budget endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.auth.scopes import managed_project
from app.models import Project, User
from app.schemas.budgets import BudgetDetails, BudgetPage, BudgetSort
from app.schemas.projects import BudgetStatus, ProjectStatus
from app.services import budgets as service

router = APIRouter(tags=["budgets"])

Manager = Annotated[User, Depends(require(Permission.MANAGE_BUDGETS))]
ManagedProject = Annotated[Project, Depends(managed_project(Permission.MANAGE_BUDGETS))]


@router.get("/budgets")
def list_budgets(
    user: Manager,
    session: SessionDep,
    search: Annotated[str, Query(max_length=100)] = "",
    budget_status: Annotated[list[BudgetStatus] | None, Query()] = None,
    project_status: Annotated[list[ProjectStatus] | None, Query()] = None,
    department_id: int | None = None,
    manager_id: int | None = None,
    sort: BudgetSort = "consumed",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> BudgetPage:
    """Search and filter the budgets of the projects the user manages."""
    return service.search_budgets(
        session,
        user,
        search=search.strip(),
        budget_statuses=budget_status or [],
        project_statuses=project_status or [],
        department_id=department_id,
        manager_id=manager_id,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get("/projects/{project_id}/budget")
def read_budget(project: ManagedProject, session: SessionDep) -> BudgetDetails:
    """Return the budget of a project the user manages."""
    return service.describe_budget(session, project)
