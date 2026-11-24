"""Project formats."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.dates import check_not_in_future
from app.schemas.common import RequestModel, ResponseModel

ProjectStatus = Literal["Planned", "Active", "On Hold", "Completed", "Cancelled"]
BudgetStatus = Literal["On Track", "Warning", "Over Budget", "No Budget"]
RiskLevel = Literal["High", "Medium", "Low"]
Priority = Literal["Low", "Medium", "High", "Critical"]

# Letters, digits and hyphens keep codes easy to type and read aloud.
Code = Annotated[
    str,
    StringConstraints(
        to_upper=True, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$"
    ),
]
BusinessDate = Annotated[date, Field(ge=date(2000, 1, 1), le=date(2100, 12, 31))]


class ProjectRequest(RequestModel):
    """Project fields that users can set."""

    code: Code
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=5000)] = ""
    department_id: int
    manager_id: int | None = None
    start_date: BusinessDate
    end_date: BusinessDate
    actual_completion_date: BusinessDate | None = None
    status: ProjectStatus = "Planned"
    priority: Priority = "Medium"
    planned_budget: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] = (
        Decimal(0)
    )

    _check_completion_date = field_validator("actual_completion_date")(
        check_not_in_future
    )

    @model_validator(mode="after")
    def check_dates(self) -> "ProjectRequest":
        """Check the rules that involve more than one field."""
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before the start date")
        completed = self.actual_completion_date
        if (self.status == "Completed") != (completed is not None):
            raise ValueError(
                "A completion date is required for completed projects only"
            )
        if completed is not None and completed < self.start_date:
            raise ValueError("Completion date must not be before the start date")
        return self


class NamedItem(ResponseModel):
    """An id and a name, for links and choices."""

    id: int
    name: str


class ProjectBudget(ResponseModel):
    """A project's budget. Amounts are text, so every digit stays exact."""

    planned: Decimal
    actual: Decimal
    # Negative when over budget.
    remaining: Decimal
    # Empty when nothing is planned.
    consumed_percent: float | None
    status: BudgetStatus


class RiskReason(ResponseModel):
    """Why a project is at risk."""

    code: str
    severity: RiskLevel
    message: str


class Risk(ResponseModel):
    """The risk of an open project."""

    level: RiskLevel
    reasons: list[RiskReason]
    expected_progress_percent: float
    # When the project ends if it continues at its current pace.
    forecast_end_date: date | None


class ProjectSummary(ResponseModel):
    """A project as shown in lists."""

    id: int
    code: str
    name: str
    department: NamedItem
    manager: NamedItem | None
    start_date: date
    end_date: date
    actual_completion_date: date | None
    status: ProjectStatus
    priority: Priority
    progress_percent: float
    # Empty for users who may not see budgets. Text keeps every digit exact.
    planned_budget: Decimal | None
    budget: ProjectBudget | None
    # Empty for closed projects and users who do not manage the project.
    risk: Risk | None
    can_edit: bool
    can_delete: bool
    created_at: datetime
    updated_at: datetime


class ProjectDetails(ProjectSummary):
    """One project in full."""

    description: str
    deliverable_count: int
    # Counts by effective status, plus "Overdue".
    deliverables_by_status: dict[str, int]
    milestone_count: int
    assignment_count: int
    expense_count: int


class ProjectOptions(ResponseModel):
    """Choices for project forms and filters."""

    statuses: list[str]
    priorities: list[str]
    budget_statuses: list[str]
    risk_levels: list[str]
    departments: list[NamedItem]
    managers: list[NamedItem]
