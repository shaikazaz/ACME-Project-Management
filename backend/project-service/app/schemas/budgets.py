"""Budget and expense formats.

Amounts are sent as text, such as "75000.00", so no digit is lost on the way.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.dates import check_not_in_future
from app.schemas.common import Page, RequestModel, ResponseModel
from app.schemas.projects import (
    BudgetStatus,
    BusinessDate,
    NamedItem,
    ProjectBudget,
    ProjectStatus,
)

CategoryName = Annotated[str, Field(min_length=1, max_length=80)]


class ExpenseRequest(RequestModel):
    """Expense fields that a project manager can set."""

    category_id: int
    amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
    expense_date: BusinessDate
    description: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("expense_date")
    @classmethod
    def check_date(cls, value: date) -> date:
        """Reject expenses that have not happened yet."""
        try:
            return check_not_in_future(value)
        except ValueError as exc:
            raise ValueError("Expense date cannot be in the future") from exc


class ProjectLabel(ResponseModel):
    """The project an expense belongs to."""

    id: int
    code: str
    name: str


class ExpenseResponse(ResponseModel):
    """An expense."""

    id: int
    project: ProjectLabel
    category: NamedItem
    amount: Decimal
    expense_date: date
    description: str
    created_by: NamedItem | None
    created_at: datetime
    updated_at: datetime


class ExpensePage(Page[ExpenseResponse]):
    """One page of expenses, and the sum of all matches."""

    total_amount: Decimal


class SavedExpense(ResponseModel):
    """A saved expense, and what it does to the budget."""

    expense: ExpenseResponse
    budget: ProjectBudget


class ExpenseOptions(ResponseModel):
    """Choices for expense forms and filters."""

    categories: list[NamedItem]
    projects: list[NamedItem]


class CategoryTotal(ResponseModel):
    """The spending in one category."""

    category: NamedItem
    amount: Decimal
    # Share of the project's actual spending.
    share_percent: float


class MonthTotal(ResponseModel):
    """The spending in one month, such as "2026-03"."""

    month: str
    amount: Decimal


class BudgetDetails(ProjectBudget):
    """A project's budget in full."""

    warning_percent: float
    expense_count: int
    categories: list[CategoryTotal]
    months: list[MonthTotal]


class BudgetRow(ResponseModel):
    """A project's budget as shown in the budget list."""

    id: int
    code: str
    name: str
    department: NamedItem
    manager: NamedItem | None
    project_status: ProjectStatus
    budget: ProjectBudget


class BudgetPage(Page[BudgetRow]):
    """One page of budgets, and the totals of all matches."""

    planned: Decimal
    actual: Decimal
    remaining: Decimal
    consumed_percent: float | None
    by_status: dict[BudgetStatus, int]


class CategoryRequest(RequestModel):
    """Category fields."""

    name: CategoryName


class CategoryResponse(ResponseModel):
    """An expense category."""

    id: int
    name: str
    expense_count: int


BudgetSort = Literal["name", "code", "planned", "actual", "remaining", "consumed"]
ExpenseSort = Literal["expense_date", "amount", "category", "project"]
