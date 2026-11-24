"""Deliverable, milestone and dependency formats."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from app.dates import check_not_in_future
from app.schemas.common import RequestModel, ResponseModel
from app.schemas.projects import BusinessDate, NamedItem, Priority

DeliverableStatus = Literal["Not Started", "In Progress", "Blocked", "Completed"]
PercentValue = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
HoursValue = Annotated[Decimal, Field(ge=0, max_digits=8, decimal_places=2)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=5000)]


class ProgressRequest(RequestModel):
    """The part of a deliverable its owner may update."""

    status: DeliverableStatus
    progress_percent: PercentValue = Decimal(0)
    actual_hours: HoursValue = Decimal(0)
    # Defaults to today when a deliverable is completed.
    completion_date: BusinessDate | None = None

    _check_completion_date = field_validator("completion_date")(check_not_in_future)

    @model_validator(mode="after")
    def check_progress(self) -> "ProgressRequest":
        """Keep the status, progress and completion date consistent."""
        if self.status == "Completed":
            self.progress_percent = Decimal(100)
            return self
        if self.completion_date is not None:
            raise ValueError("Only completed deliverables have a completion date")
        if self.status == "Not Started" and self.progress_percent > 0:
            raise ValueError("Work that has not started must have 0% progress")
        if self.progress_percent == 100:
            raise ValueError("Set the status to Completed instead of 100% progress")
        return self


class DeliverableRequest(ProgressRequest):
    """All deliverable fields that a project manager can set."""

    name: Title
    description: Description = ""
    milestone_id: int | None = None
    owner_id: int | None = None
    start_date: BusinessDate
    due_date: BusinessDate
    status: DeliverableStatus = "Not Started"
    priority: Priority = "Medium"
    estimated_hours: HoursValue = Decimal(0)

    @model_validator(mode="after")
    def check_dates(self) -> "DeliverableRequest":
        """Check the date order."""
        if self.due_date < self.start_date:
            raise ValueError("Due date must not be before the start date")
        return self


class ProjectLabel(ResponseModel):
    """The project a deliverable belongs to."""

    id: int
    code: str
    name: str


class RelatedDeliverable(ResponseModel):
    """A linked deliverable. Details are hidden in projects the user cannot see."""

    id: int | None
    name: str
    project_code: str | None
    status: DeliverableStatus


class DeliverableSummary(ResponseModel):
    """A deliverable as shown in lists."""

    id: int
    name: str
    project: ProjectLabel
    milestone: NamedItem | None
    owner: NamedItem | None
    start_date: date
    due_date: date
    completion_date: date | None
    # The status someone set, and the status after applying dependencies.
    status: DeliverableStatus
    effective_status: DeliverableStatus
    blocked_by: list[RelatedDeliverable]
    priority: Priority
    progress_percent: float
    estimated_hours: float
    actual_hours: float
    is_overdue: bool
    days_overdue: int
    completed_late: bool
    can_edit: bool
    can_update: bool
    updated_at: datetime


class DeliverableDetails(DeliverableSummary):
    """One deliverable in full."""

    description: str
    predecessors: list[RelatedDeliverable]
    successors: list[RelatedDeliverable]


class DeliverableOptions(ResponseModel):
    """Choices for deliverable forms and filters."""

    statuses: list[str]
    priorities: list[str]
    projects: list[NamedItem]
    owners: list[NamedItem]
    milestones: list[NamedItem]


class DependencyRequest(RequestModel):
    """The deliverable that must be completed first."""

    predecessor_id: int


class ChainNode(ResponseModel):
    """One deliverable in a dependency chain."""

    key: str
    deliverable: RelatedDeliverable
    effective_status: DeliverableStatus
    is_external: bool
    is_overdue: bool
    due_date: date | None
    # 1 for deliverables without predecessors, then one more per step.
    step: int


class ChainLink(ResponseModel):
    """An arrow from one deliverable to the next."""

    predecessor: str
    successor: str


class DependencyChain(ResponseModel):
    """The dependencies of a project."""

    nodes: list[ChainNode]
    links: list[ChainLink]


class MilestoneRequest(RequestModel):
    """Milestone fields."""

    name: Title
    description: Description = ""
    due_date: BusinessDate
    completed_date: BusinessDate | None = None

    _check_completed_date = field_validator("completed_date")(check_not_in_future)


class MilestoneResponse(ResponseModel):
    """A milestone and the state of its deliverables."""

    id: int
    name: str
    description: str
    due_date: date
    completed_date: date | None
    is_overdue: bool
    deliverable_count: int
    completed_count: int
