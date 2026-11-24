"""Project risk rules.

Every rule is a fixed comparison of stored data with a threshold, so the same
data always gives the same result. Only open projects are assessed. A project
is at risk when its level is high or medium:

* High: at least one high reason.
* Medium: at least one medium reason.
* Low: no reason.
"""

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dates import today
from app.models import AppSetting, Deliverable, Project, ProjectAssignment, Resource
from app.schemas.projects import Risk, RiskReason
from app.services.budgets import OVER, WARNING, make_budget, warning_percent
from app.services.deliverables import CLOSED_STATUSES, effective_status, is_overdue
from app.services.workload import counts

LAG_SETTING = "schedule_lag_percent"
HIGH, MEDIUM, LOW = "High", "Medium", "Low"
RISK_LEVELS = (HIGH, MEDIUM, LOW)
MAX_FORECAST_DAYS = 3650
MAX_NAMES = 3


@dataclass
class Facts:
    """What the rules need to know about one project."""

    overdue: int = 0
    critical_overdue: int = 0
    critical_blocked: list[str] = field(default_factory=list)
    over_allocated: list[str] = field(default_factory=list)


def is_open(project: Project) -> bool:
    """Check whether a project is assessed."""
    return project.status not in CLOSED_STATUSES


def expected_progress(start: date, end: date, day: date) -> Decimal:
    """Calculate the progress a steady project has at the start of a day.

    Args:
        start: The project's first day.
        end: The project's last day.
        day: The day.

    Returns:
        A percentage: 0 on the first day, 100 on the day after the last.
    """
    total = (end - start).days + 1
    elapsed = min(max((day - start).days, 0), total)
    share = Decimal(elapsed * 100) / total
    return share.quantize(Decimal("0.1"), ROUND_HALF_UP)


def forecast_end(start: date, progress: Decimal, day: date) -> date | None:
    """Forecast the last day of a project that continues at its current pace.

    Args:
        start: The project's first day.
        progress: The progress so far.
        day: The day of the forecast.

    Returns:
        The date, or nothing when there is no pace to continue, or the result
        is more than ten years away.
    """
    elapsed = (day - start).days
    if elapsed <= 0 or progress <= 0 or progress >= 100:
        return None
    # A started day counts as a whole one.
    needed = math.ceil(Decimal(elapsed) * 100 / progress)
    if needed > MAX_FORECAST_DAYS:
        return None
    return start + timedelta(days=needed - 1)


def _names(items: list[str]) -> str:
    """List names for a message."""
    shown = ", ".join(items[:MAX_NAMES])
    rest = len(items) - MAX_NAMES
    return f"{shown} and {rest} more" if rest > 0 else shown


def _collect_facts(session: Session, ids: list[int]) -> dict[int, Facts]:
    """Load the facts of several projects."""
    facts: dict[int, Facts] = defaultdict(Facts)
    rows = session.execute(
        select(
            Deliverable.project_id,
            Deliverable.name,
            Deliverable.priority,
            effective_status(),
            is_overdue(),
        )
        .join(Project, Project.id == Deliverable.project_id)
        .where(Deliverable.project_id.in_(ids), Deliverable.status != "Completed")
        .order_by(Deliverable.name)
    )
    for project_id, name, priority, status, late in rows:
        found = facts[project_id]
        critical = priority == "Critical"
        found.overdue += late
        found.critical_overdue += late and critical
        if critical and status == "Blocked":
            found.critical_blocked.append(name)
    for project_id, names in _over_allocated(session, ids).items():
        facts[project_id].over_allocated = names
    return facts


def _over_allocated(session: Session, ids: list[int]) -> dict[int, list[str]]:
    """Find people who are over-allocated while they work on each project."""
    now = today()
    members = select(ProjectAssignment.resource_id).where(
        ProjectAssignment.project_id.in_(ids), ProjectAssignment.end_date >= now
    )
    rows = session.execute(
        select(ProjectAssignment, Resource.full_name, Resource.capacity_percent)
        .join(Project, Project.id == ProjectAssignment.project_id)
        .join(Resource, Resource.id == ProjectAssignment.resource_id)
        .where(
            counts(),
            ProjectAssignment.end_date >= now,
            ProjectAssignment.resource_id.in_(members),
        )
        .order_by(Resource.full_name, Resource.id)
    ).all()
    spans = defaultdict(list)
    for item, *_ in rows:
        spans[item.resource_id].append(
            (max(item.start_date, now), item.end_date, item.allocation_percent)
        )
    wanted = set(ids)
    found: dict[int, list[str]] = defaultdict(list)
    for item, name, capacity in rows:
        if item.project_id not in wanted:
            continue
        first = max(item.start_date, now)
        own = spans[item.resource_id]
        # A total only rises when an assignment starts.
        days = {first} | {day for day, *_ in own if first <= day <= item.end_date}
        peak = max(
            sum(
                (percent for begin, end, percent in own if begin <= day <= end),
                Decimal(0),
            )
            for day in days
        )
        if peak > capacity:
            found[item.project_id].append(name)
    return found


def _reasons(
    project: Project,
    progress: Decimal,
    budget_status: str,
    consumed: float | None,
    facts: Facts,
    lag: Decimal,
) -> list[RiskReason]:
    """Apply every rule to one project."""
    now = today()
    reasons = []

    def add(code: str, severity: str, message: str) -> None:
        """Record a reason."""
        reasons.append(RiskReason(code=code, severity=severity, message=message))

    late = (now - project.end_date).days
    if late > 0:
        days = "day" if late == 1 else "days"
        add("deadline_passed", HIGH, f"The deadline passed {late} {days} ago.")
    else:
        # After the deadline the rule above says it all.
        expected = expected_progress(project.start_date, project.end_date, now)
        gap = expected - progress
        if gap > 0 and gap >= lag:
            severity = HIGH if gap >= 2 * lag else MEDIUM
            add(
                "behind_schedule",
                severity,
                f"Progress is {progress}%, but {expected}% was expected by now.",
            )
    if facts.overdue:
        noun = "deliverable is" if facts.overdue == 1 else "deliverables are"
        critical = facts.critical_overdue
        extra = f", {critical} of them critical" if critical else ""
        severity = HIGH if critical else MEDIUM
        add("overdue_deliverables", severity, f"{facts.overdue} {noun} overdue{extra}.")
    if facts.critical_blocked:
        names = _names(facts.critical_blocked)
        add("critical_blocked", HIGH, f"Critical work is blocked: {names}.")
    if budget_status == OVER:
        share = "" if consumed is None else f" ({consumed}% consumed)"
        add("over_budget", HIGH, f"Spending is over budget{share}.")
    elif budget_status == WARNING:
        add("budget_warning", MEDIUM, f"{consumed}% of the budget is consumed.")
    if facts.over_allocated:
        names = _names(facts.over_allocated)
        add("over_allocated", MEDIUM, f"Over-allocated people: {names}.")
    return reasons


def assess_projects(
    session: Session, rows: Iterable[tuple[Project, Decimal, Decimal]]
) -> dict[int, Risk]:
    """Assess the risk of several projects.

    Args:
        session: Database session.
        rows: Each project with its calculated progress and actual spending.

    Returns:
        The risk of every open project, by project id.
    """
    rows = [row for row in rows if is_open(row[0])]
    if not rows:
        return {}
    now = today()
    warning = warning_percent(session)
    lag = session.get(AppSetting, LAG_SETTING).value
    facts = _collect_facts(session, [project.id for project, *_ in rows])
    risks = {}
    for project, progress, actual in rows:
        budget = make_budget(project.planned_budget, actual, warning)
        progress = Decimal(progress).quantize(Decimal("0.1"))
        reasons = _reasons(
            project,
            progress,
            budget.status,
            budget.consumed_percent,
            facts[project.id],
            lag,
        )
        severities = {reason.severity for reason in reasons}
        level = next((name for name in (HIGH, MEDIUM) if name in severities), LOW)
        # The most severe reasons come first.
        reasons.sort(key=lambda reason: RISK_LEVELS.index(reason.severity))
        risks[project.id] = Risk(
            level=level,
            reasons=reasons,
            expected_progress_percent=expected_progress(
                project.start_date, project.end_date, now
            ),
            forecast_end_date=forecast_end(project.start_date, progress, now),
        )
    return risks
