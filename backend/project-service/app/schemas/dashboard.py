"""Risk and dashboard formats."""

from datetime import date
from decimal import Decimal
from typing import Literal

from app.schemas.common import ResponseModel
from app.schemas.projects import (
    BudgetStatus,
    NamedItem,
    ProjectStatus,
    Risk,
    RiskLevel,
)


class ProjectMetrics(ResponseModel):
    """Project counts."""

    total: int
    by_status: dict[ProjectStatus, int]
    overdue: int
    # Open projects by risk level. At risk means high or medium.
    by_risk: dict[RiskLevel, int]
    at_risk: int


class DeliverableMetrics(ResponseModel):
    """Deliverable counts, without those of cancelled projects."""

    total: int
    completed: int
    pending: int
    overdue: int
    by_status: dict[str, int]
    completion_percent: float | None


class ResourceMetrics(ResponseModel):
    """Resource figures, the same as in the workload report."""

    total: int
    over_allocated: int
    needs_cover: int
    capacity_percent: float
    peak_percent: float
    utilization_percent: float | None


class BudgetMetrics(ResponseModel):
    """Budget figures, the same as in the budget list."""

    planned: Decimal
    actual: Decimal
    remaining: Decimal
    consumed_percent: float | None
    by_status: dict[BudgetStatus, int]


class RiskyProject(ResponseModel):
    """A project at risk."""

    id: int
    code: str
    name: str
    status: ProjectStatus
    manager: NamedItem | None
    end_date: date
    progress_percent: float
    risk: Risk


class Deadline(ResponseModel):
    """An upcoming deadline."""

    kind: Literal["Project", "Milestone", "Deliverable"]
    id: int
    name: str
    project_id: int
    project_code: str
    due_date: date
    days_left: int


class Dashboard(ResponseModel):
    """All dashboard figures of the projects a user manages."""

    as_of: date
    upcoming_days: int
    projects: ProjectMetrics
    deliverables: DeliverableMetrics
    resources: ResourceMetrics
    budget: BudgetMetrics
    deadline_count: int
    deadlines: list[Deadline]
    risky_projects: list[RiskyProject]
