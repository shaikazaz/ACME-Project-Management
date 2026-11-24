"""Workload calculations.

An assignment allocates a percentage of a full-time week to a project between
two dates. Assignments only add up while they overlap:

* The current load is the total of the assignments that include today.
* The peak load is the highest total on any day of the period.

A resource is over-allocated when the peak is higher than their own capacity.
Assignments of completed and cancelled projects do not count.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, Subquery, func, literal, select
from sqlalchemy.orm import Session, aliased

from app.dates import today
from app.models import AppSetting, Project, ProjectAssignment, Resource
from app.schemas.resources import Workload, WorkloadPeriod
from app.services.deliverables import CLOSED_STATUSES

HOURS_SETTING = "full_time_hours_per_week"


@dataclass(frozen=True)
class Period:
    """The period to report on. Without an end it is open."""

    start: date
    end: date | None = None


def full_time_hours(session: Session) -> Decimal:
    """Return the weekly hours of a 100% allocation."""
    return session.get(AppSetting, HOURS_SETTING).value


def counts() -> ColumnElement[bool]:
    """Build the SQL condition for projects whose assignments count."""
    return Project.status.not_in(CLOSED_STATUSES)


def peak_loads(period: Period) -> Subquery:
    """Build the SQL that finds each resource's peak load in a period.

    A total can only rise on a day when an assignment starts, so it is enough
    to check the first day of every assignment, cut to the period.

    Args:
        period: The period.

    Returns:
        A subquery with resource_id and peak.
    """
    start = literal(period.start)
    loads = (
        select(
            ProjectAssignment.id,
            ProjectAssignment.resource_id,
            ProjectAssignment.allocation_percent.label("percent"),
            func.greatest(ProjectAssignment.start_date, start).label("first_day"),
            ProjectAssignment.end_date.label("last_day"),
        )
        .join(Project, Project.id == ProjectAssignment.project_id)
        .where(counts(), ProjectAssignment.end_date >= period.start)
    )
    if period.end is not None:
        loads = loads.where(ProjectAssignment.start_date <= period.end)
    loads = loads.cte("loads")
    other = aliased(loads)
    totals = (
        select(loads.c.resource_id, func.sum(other.c.percent).label("total"))
        .join(
            other,
            (other.c.resource_id == loads.c.resource_id)
            & (other.c.first_day <= loads.c.first_day)
            & (other.c.last_day >= loads.c.first_day),
        )
        .group_by(loads.c.resource_id, loads.c.id)
        .subquery("totals")
    )
    return (
        select(totals.c.resource_id, func.max(totals.c.total).label("peak"))
        .group_by(totals.c.resource_id)
        .subquery("peaks")
    )


def current_load() -> ColumnElement[Decimal]:
    """Build the SQL for a resource's total allocation today."""
    total = (
        select(func.sum(ProjectAssignment.allocation_percent))
        .join(Project, Project.id == ProjectAssignment.project_id)
        .where(
            ProjectAssignment.resource_id == Resource.id,
            ProjectAssignment.start_date <= today(),
            ProjectAssignment.end_date >= today(),
            counts(),
        )
        .correlate(Resource)
        .scalar_subquery()
    )
    return func.coalesce(total, 0)


def percent_of(part: Decimal, whole: Decimal) -> float | None:
    """Calculate a percentage, or nothing when the whole is zero."""
    return float(round(part / whole * 100, 1)) if whole else None


def make_workload(
    capacity: Decimal, current: Decimal, peak: Decimal, week: Decimal
) -> Workload:
    """Build a workload from its totals.

    Args:
        capacity: The resource's capacity as a percentage of full time.
        current: The total today.
        peak: The highest total in the period.
        week: Weekly hours of a 100% allocation.

    Returns:
        The workload.
    """

    def hours(percent: Decimal) -> float:
        """Convert a percentage to weekly hours."""
        return float(round(percent * week / 100, 2))

    # Without capacity, no allocation is 0% utilization and any other has none.
    utilization = percent_of(peak, capacity)
    if utilization is None and not peak:
        utilization = 0.0
    return Workload(
        capacity_percent=capacity,
        current_percent=current,
        peak_percent=peak,
        current_hours=hours(current),
        peak_hours=hours(peak),
        capacity_hours=hours(capacity),
        utilization_percent=utilization,
        remaining_percent=capacity - peak,
        is_over_allocated=peak > capacity,
        is_over_allocated_now=current > capacity,
    )


def workload_periods(
    spans: list[tuple[date, date, Decimal]], capacity: Decimal, start: date
) -> list[WorkloadPeriod]:
    """Split a resource's assignments into periods with a constant total.

    Args:
        spans: First day, last day and percentage of each counting assignment.
        capacity: The resource's capacity.
        start: The first day to include.

    Returns:
        The periods with an allocation, in order.
    """
    spans = [
        (max(first, start), last, percent)
        for first, last, percent in spans
        if last >= start
    ]
    edges = sorted(
        {first for first, _, _ in spans}
        | {last + timedelta(days=1) for _, last, _ in spans}
    )
    periods: list[WorkloadPeriod] = []
    for first, following in zip(edges, edges[1:], strict=False):
        total = sum(
            (percent for begin, end, percent in spans if begin <= first <= end),
            Decimal(0),
        )
        if total:
            periods.append(
                WorkloadPeriod(
                    start_date=first,
                    end_date=following - timedelta(days=1),
                    total_percent=total,
                    is_over_allocated=total > capacity,
                )
            )
    return periods
