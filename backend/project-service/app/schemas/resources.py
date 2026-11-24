"""Resource, assignment and workload formats."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.schemas.common import Email, Name, RequestModel, ResponseModel
from app.schemas.projects import BusinessDate, NamedItem

Availability = Literal["Available", "On Leave", "Unavailable"]
EmployeeCode = Annotated[
    str,
    StringConstraints(
        to_upper=True, max_length=30, pattern=r"^[A-Za-z0-9][A-Za-z0-9-]*$"
    ),
]
Skill = Annotated[str, Field(min_length=1, max_length=50)]


class ResourceRequest(RequestModel):
    """Resource fields that an admin can set."""

    employee_code: EmployeeCode
    full_name: Name
    email: Email
    department_id: int
    job_title: Name
    skills: Annotated[list[Skill], Field(max_length=20)] = []
    capacity_percent: Annotated[
        Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)
    ] = Decimal(100)
    availability: Availability = "Available"
    user_id: int | None = None

    @field_validator("skills")
    @classmethod
    def remove_duplicates(cls, value: list[str]) -> list[str]:
        """Keep the first spelling of each skill."""
        unique: dict[str, str] = {}
        for skill in value:
            unique.setdefault(skill.lower(), skill)
        return list(unique.values())


class Workload(ResponseModel):
    """How much of a resource's capacity is allocated.

    Percentages are of a full-time week, like the capacity itself.
    """

    capacity_percent: float
    # The total today, and the highest overlapping total in the period.
    current_percent: float
    peak_percent: float
    current_hours: float
    peak_hours: float
    capacity_hours: float
    # The peak as a share of the capacity; empty when the capacity is zero.
    utilization_percent: float | None
    # Capacity left at the peak; negative when over-allocated.
    remaining_percent: float
    is_over_allocated: bool
    is_over_allocated_now: bool


class ResourceSummary(ResponseModel):
    """A resource as shown in lists."""

    id: int
    employee_code: str
    full_name: str
    email: str
    department: NamedItem
    job_title: str
    skills: list[str]
    availability: Availability
    user: NamedItem | None
    workload: Workload
    # Assigned today although not available.
    needs_cover: bool
    can_edit: bool
    updated_at: datetime


class ResourceAssignment(ResponseModel):
    """An assignment as seen from its resource."""

    project_id: int | None
    project_name: str
    project_code: str | None
    project_status: str
    project_role: str
    allocation_percent: float
    start_date: date
    end_date: date
    # Assignments of completed and cancelled projects do not count.
    counts: bool


class WorkloadPeriod(ResponseModel):
    """A period in which the total allocation does not change."""

    start_date: date
    end_date: date
    total_percent: float
    is_over_allocated: bool


class ResourceDetails(ResourceSummary):
    """One resource in full."""

    assignments: list[ResourceAssignment]
    periods: list[WorkloadPeriod]


class ResourceOptions(ResponseModel):
    """Choices for resource forms and filters."""

    availability: list[str]
    departments: list[NamedItem]
    skills: list[str]
    # Accounts that are not linked to a resource; admins only.
    users: list[NamedItem]


class AssignmentRequest(RequestModel):
    """Assignment fields that a project manager can set."""

    resource_id: int
    project_role: Annotated[str, Field(max_length=120)] = ""
    allocation_percent: Annotated[
        Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)
    ]
    start_date: BusinessDate
    end_date: BusinessDate

    @model_validator(mode="after")
    def check_dates(self) -> "AssignmentRequest":
        """Check the date order."""
        if self.end_date < self.start_date:
            raise ValueError("End date must not be before the start date")
        return self


class ProjectAssignmentResponse(ResponseModel):
    """An assignment as seen from its project."""

    id: int
    resource: NamedItem
    job_title: str
    availability: Availability
    project_role: str
    allocation_percent: float
    allocation_hours: float
    start_date: date
    end_date: date
    workload: Workload


class DepartmentWorkload(ResponseModel):
    """The workload of one department at each person's peak."""

    department: NamedItem
    resource_count: int
    over_allocated_count: int
    capacity_percent: float
    peak_percent: float
    utilization_percent: float | None


class WorkloadReport(ResponseModel):
    """The workload of all resources in a period."""

    period_from: date
    period_to: date | None
    resource_count: int
    over_allocated_count: int
    fully_allocated_count: int
    partly_allocated_count: int
    unallocated_count: int
    needs_cover_count: int
    capacity_percent: float
    peak_percent: float
    utilization_percent: float | None
    departments: list[DepartmentWorkload]
