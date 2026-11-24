"""Expense and category queries and rules."""

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth.scopes import managed_projects
from app.errors import ApiError
from app.models import Expense, ExpenseCategory, Project, User
from app.schemas.budgets import (
    CategoryResponse,
    ExpenseOptions,
    ExpensePage,
    ExpenseRequest,
    ExpenseResponse,
    ProjectLabel,
)
from app.schemas.common import Page
from app.schemas.projects import NamedItem


def describe(row: Expense) -> ExpenseResponse:
    """Describe an expense."""
    author = row.created_by
    return ExpenseResponse(
        id=row.id,
        project=ProjectLabel.model_validate(row.project),
        category=NamedItem.model_validate(row.category),
        amount=row.amount,
        expense_date=row.expense_date,
        description=row.description,
        created_by=NamedItem(id=author.id, name=author.full_name) if author else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def search_expenses(
    session: Session,
    user: User,
    *,
    search: str,
    project_id: int | None,
    category_id: int | None,
    date_from: date | None,
    date_to: date | None,
    amount_min: Decimal | None,
    amount_max: Decimal | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> ExpensePage:
    """Search the expenses of the projects a user manages.

    Args:
        session: Database session.
        user: The signed-in user.
        search: Text to find in the description.
        project_id: Project to include.
        category_id: Category to include.
        date_from: Earliest date.
        date_to: Latest date.
        amount_min: Smallest amount.
        amount_max: Largest amount.
        sort: The sort field.
        descending: Whether to reverse the order.
        limit: Page size.
        offset: Number of results to skip.

    Returns:
        One page of expenses, and the sum of all matches.
    """
    conditions = [managed_projects(user)]
    if search:
        conditions.append(Expense.description.icontains(search, autoescape=True))
    if project_id is not None:
        conditions.append(Expense.project_id == project_id)
    if category_id is not None:
        conditions.append(Expense.category_id == category_id)
    if date_from is not None:
        conditions.append(Expense.expense_date >= date_from)
    if date_to is not None:
        conditions.append(Expense.expense_date <= date_to)
    if amount_min is not None:
        conditions.append(Expense.amount >= amount_min)
    if amount_max is not None:
        conditions.append(Expense.amount <= amount_max)

    total, amount = session.execute(
        select(func.count(), func.coalesce(func.sum(Expense.amount), Decimal("0.00")))
        .join(Project, Project.id == Expense.project_id)
        .where(*conditions)
    ).one()
    order = {
        "expense_date": Expense.expense_date,
        "amount": Expense.amount,
        "category": ExpenseCategory.name,
        "project": Project.code,
    }[sort]
    rows = session.scalars(
        select(Expense)
        .join(Project, Project.id == Expense.project_id)
        .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
        .where(*conditions)
        .options(
            joinedload(Expense.project),
            joinedload(Expense.category),
            joinedload(Expense.created_by),
        )
        .order_by(order.desc() if descending else order.asc(), Expense.id)
        .limit(limit)
        .offset(offset)
    )
    return ExpensePage(
        items=[describe(row) for row in rows], total=total, total_amount=amount
    )


def save_expense(session: Session, row: Expense, body: ExpenseRequest) -> None:
    """Create or update an expense.

    Expenses are accepted whatever the project's status, because invoices
    often arrive after a project has ended.

    Args:
        session: Database session.
        row: The expense, in a project the user must be allowed to manage.
        body: The requested values.

    Raises:
        ApiError: 400 when the category does not exist.
    """
    if not session.get(ExpenseCategory, body.category_id):
        raise ApiError(400, "Category not found.", field="category_id")
    for field, value in body.model_dump().items():
        setattr(row, field, value)
    session.add(row)
    session.commit()


def list_options(session: Session, user: User) -> ExpenseOptions:
    """List the choices for expense forms and filters."""
    categories = session.scalars(select(ExpenseCategory).order_by(ExpenseCategory.name))
    projects = session.scalars(
        select(Project).where(managed_projects(user)).order_by(Project.code)
    )
    return ExpenseOptions(
        categories=[NamedItem.model_validate(row) for row in categories],
        projects=[
            NamedItem(id=row.id, name=f"{row.code} · {row.name}") for row in projects
        ],
    )


def list_categories(session: Session) -> Page[CategoryResponse]:
    """List expense categories with how often they are used."""
    rows = session.execute(
        select(ExpenseCategory, func.count(Expense.id))
        .outerjoin(Expense, Expense.category_id == ExpenseCategory.id)
        .group_by(ExpenseCategory.id)
        .order_by(func.lower(ExpenseCategory.name))
    )
    items = [
        CategoryResponse(id=row.id, name=row.name, expense_count=count)
        for row, count in rows
    ]
    return Page(items=items, total=len(items))
