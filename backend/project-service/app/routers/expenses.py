"""Expense and category endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.auth.scopes import managed_project, managed_projects
from app.errors import ApiError
from app.models import Expense, ExpenseCategory, Project, User
from app.schemas.budgets import (
    CategoryRequest,
    CategoryResponse,
    ExpenseOptions,
    ExpensePage,
    ExpenseRequest,
    ExpenseResponse,
    ExpenseSort,
    SavedExpense,
)
from app.schemas.common import Page
from app.services import expenses as service
from app.services.budgets import project_budget

router = APIRouter(tags=["expenses"])

Manager = Annotated[User, Depends(require(Permission.MANAGE_BUDGETS))]
Admin = Annotated[User, Depends(require(Permission.MANAGE_SETTINGS))]
ManagedProject = Annotated[Project, Depends(managed_project(Permission.MANAGE_BUDGETS))]
AmountFilter = Annotated[Decimal | None, Query(ge=0, max_digits=14, decimal_places=2)]


def find_expense(expense_id: int, user: Manager, session: SessionDep) -> Expense:
    """Load an expense of a project the user manages, or fail with 404."""
    row = session.scalar(
        select(Expense)
        .join(Project, Project.id == Expense.project_id)
        .where(Expense.id == expense_id, managed_projects(user))
    )
    if row is None:
        raise ApiError(404, "Expense not found.")
    return row


def find_category(category_id: int, _: Admin, session: SessionDep) -> ExpenseCategory:
    """Load a category for an admin, or fail with 404."""
    row = session.get(ExpenseCategory, category_id)
    if row is None:
        raise ApiError(404, "Category not found.")
    return row


TargetExpense = Annotated[Expense, Depends(find_expense)]
TargetCategory = Annotated[ExpenseCategory, Depends(find_category)]


def _saved(session: SessionDep, row: Expense) -> SavedExpense:
    """Return a saved expense with the project's new budget."""
    budget = project_budget(session, row.project)
    return SavedExpense(expense=service.describe(row), budget=budget)


@router.get("/expenses")
def list_expenses(
    user: Manager,
    session: SessionDep,
    search: Annotated[str, Query(max_length=100)] = "",
    project_id: int | None = None,
    category_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    amount_min: AmountFilter = None,
    amount_max: AmountFilter = None,
    sort: ExpenseSort = "expense_date",
    order: Literal["asc", "desc"] = "desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> ExpensePage:
    """Search and filter the expenses of the projects the user manages."""
    return service.search_expenses(
        session,
        user,
        search=search.strip(),
        project_id=project_id,
        category_id=category_id,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )


@router.get("/expenses/options")
def read_options(user: Manager, session: SessionDep) -> ExpenseOptions:
    """Return the choices for expense forms and filters."""
    return service.list_options(session, user)


@router.post("/projects/{project_id}/expenses", status_code=201)
def create_expense(
    body: ExpenseRequest, project: ManagedProject, user: Manager, session: SessionDep
) -> SavedExpense:
    """Add an expense to a project the user manages."""
    row = Expense(project_id=project.id, created_by_id=user.id)
    service.save_expense(session, row, body)
    return _saved(session, row)


@router.get("/expenses/{expense_id}")
def read_expense(row: TargetExpense) -> ExpenseResponse:
    """Return one expense."""
    return service.describe(row)


@router.put("/expenses/{expense_id}")
def update_expense(
    body: ExpenseRequest, row: TargetExpense, session: SessionDep
) -> SavedExpense:
    """Update an expense."""
    service.save_expense(session, row, body)
    return _saved(session, row)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(row: TargetExpense, session: SessionDep) -> None:
    """Delete an expense."""
    session.delete(row)
    session.commit()


@router.get("/expense-categories")
def list_categories(_: Manager, session: SessionDep) -> Page[CategoryResponse]:
    """List expense categories."""
    return service.list_categories(session)


@router.post("/expense-categories", status_code=201)
def create_category(
    body: CategoryRequest, _: Admin, session: SessionDep
) -> CategoryResponse:
    """Create an expense category."""
    row = ExpenseCategory(name=body.name)
    session.add(row)
    session.commit()
    return CategoryResponse(id=row.id, name=row.name, expense_count=0)


@router.put("/expense-categories/{category_id}")
def update_category(
    body: CategoryRequest, row: TargetCategory, session: SessionDep
) -> CategoryResponse:
    """Rename an expense category."""
    row.name = body.name
    session.commit()
    page = service.list_categories(session)
    return next(item for item in page.items if item.id == row.id)


@router.delete("/expense-categories/{category_id}", status_code=204)
def delete_category(row: TargetCategory, session: SessionDep) -> None:
    """Delete an expense category that is not used."""
    session.delete(row)
    session.commit()
