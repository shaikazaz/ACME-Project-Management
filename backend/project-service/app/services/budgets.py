"""Budget calculations and queries.

Only expenses are stored. Everything else is calculated from them with exact
decimals:

* Actual spending is the sum of the project's expenses.
* Remaining is the planned budget minus the actual spending.
* Consumed is the actual spending as a percentage of the planned budget.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, and_, case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.auth.scopes import managed_projects
from app.models import AppSetting, Expense, ExpenseCategory, Project, User
from app.schemas.budgets import (
    BudgetDetails,
    BudgetPage,
    BudgetRow,
    CategoryTotal,
    MonthTotal,
)
from app.schemas.projects import NamedItem, ProjectBudget

WARNING_SETTING = "budget_warning_percent"
OVER, WARNING, ON_TRACK, NO_BUDGET = (
    "Over Budget",
    "Warning",
    "On Track",
    "No Budget",
)
BUDGET_STATUSES = (ON_TRACK, WARNING, OVER, NO_BUDGET)
CENT, TENTH = Decimal("0.01"), Decimal("0.1")


def warning_percent(session: Session) -> Decimal:
    """Return the consumption at which a budget needs attention."""
    return session.get(AppSetting, WARNING_SETTING).value


def spent() -> ColumnElement[Decimal]:
    """Build the SQL for a project's actual spending."""
    total = (
        select(func.sum(Expense.amount))
        .where(Expense.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    return func.coalesce(total, 0)


def budget_status(
    planned: ColumnElement, actual: ColumnElement, warning: Decimal
) -> ColumnElement[str]:
    """Build the SQL for a budget status. It matches make_budget."""
    return case(
        (actual > planned, OVER),
        (planned == 0, NO_BUDGET),
        (actual * 100 >= planned * warning, WARNING),
        else_=ON_TRACK,
    )


def consumed(actual: Decimal, planned: Decimal) -> float | None:
    """Calculate the consumed percentage, or nothing without a budget."""
    if not planned:
        return None
    share = (actual * 100 / planned).quantize(TENTH, ROUND_HALF_UP)
    return float(share)


def make_budget(planned: Decimal, actual: Decimal, warning: Decimal) -> ProjectBudget:
    """Calculate a budget.

    Spending exactly the planned amount is not over budget.

    Args:
        planned: The planned budget.
        actual: The actual spending.
        warning: The consumption at which the budget needs attention.

    Returns:
        The budget.
    """
    planned, actual = (Decimal(value).quantize(CENT) for value in (planned, actual))
    if actual > planned:
        status = OVER
    elif not planned:
        status = NO_BUDGET
    elif actual * 100 >= planned * warning:
        status = WARNING
    else:
        status = ON_TRACK
    return ProjectBudget(
        planned=planned,
        actual=actual,
        remaining=planned - actual,
        consumed_percent=consumed(actual, planned),
        status=status,
    )


def project_budget(session: Session, project: Project) -> ProjectBudget:
    """Calculate one project's budget.

    Args:
        session: Database session.
        project: The project.

    Returns:
        The budget.
    """
    actual = session.scalar(select(spent()).where(Project.id == project.id))
    return make_budget(project.planned_budget, actual, warning_percent(session))


def describe_budget(session: Session, project: Project) -> BudgetDetails:
    """Return one project's budget with its spending by category and month.

    Args:
        session: Database session.
        project: The project, which the user must be allowed to manage.

    Returns:
        The budget.
    """
    budget = project_budget(session, project)
    total = func.sum(Expense.amount)
    by_category = session.execute(
        select(ExpenseCategory.id, ExpenseCategory.name, total)
        .join(Expense, Expense.category_id == ExpenseCategory.id)
        .where(Expense.project_id == project.id)
        .group_by(ExpenseCategory.id, ExpenseCategory.name)
        .order_by(total.desc(), ExpenseCategory.name)
    )
    month = func.to_char(Expense.expense_date, "YYYY-MM")
    by_month = session.execute(
        select(month, total)
        .where(Expense.project_id == project.id)
        .group_by(month)
        .order_by(month)
    )
    count = session.scalar(
        select(func.count())
        .select_from(Expense)
        .where(Expense.project_id == project.id)
    )
    return BudgetDetails(
        **budget.model_dump(),
        warning_percent=warning_percent(session),
        expense_count=count,
        categories=[
            CategoryTotal(
                category=NamedItem(id=key, name=name),
                amount=amount,
                share_percent=consumed(amount, budget.actual),
            )
            for key, name, amount in by_category
        ],
        months=[MonthTotal(month=key, amount=amount) for key, amount in by_month],
    )


def search_budgets(
    session: Session,
    user: User,
    *,
    search: str,
    budget_statuses: list[str],
    project_statuses: list[str],
    department_id: int | None,
    manager_id: int | None,
    sort: str,
    descending: bool,
    limit: int,
    offset: int,
) -> BudgetPage:
    """Search the budgets of the projects a user manages.

    Args:
        session: Database session.
        user: The signed-in user.
        search: Text to find in the project code or name.
        budget_statuses: Budget statuses to include; empty means all.
        project_statuses: Project statuses to include; empty means all.
        department_id: Department to include.
        manager_id: Project manager to include.
        sort: The sort field.
        descending: Whether to reverse the order.
        limit: Page size.
        offset: Number of results to skip.

    Returns:
        One page of budgets, and the totals of all matches.
    """
    warning = warning_percent(session)
    actual = spent()
    status = budget_status(Project.planned_budget, actual, warning)
    conditions = [managed_projects(user)]
    if search:
        columns = (Project.code, Project.name)
        conditions.append(
            or_(*(column.icontains(search, autoescape=True) for column in columns))
        )
    if budget_statuses:
        conditions.append(status.in_(budget_statuses))
    if project_statuses:
        conditions.append(Project.status.in_(project_statuses))
    if department_id is not None:
        conditions.append(Project.department_id == department_id)
    if manager_id is not None:
        conditions.append(Project.manager_id == manager_id)
    matches = and_(*conditions)

    rows = (
        select(Project.planned_budget, actual.label("actual"), status.label("status"))
        .where(matches)
        .subquery()
    )
    total, planned_sum, actual_sum = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(rows.c.planned_budget), 0),
            func.coalesce(func.sum(rows.c.actual), 0),
        ).select_from(rows)
    ).one()
    counts = dict.fromkeys(BUDGET_STATUSES, 0)
    counts.update(
        session.execute(
            select(rows.c.status, func.count()).group_by(rows.c.status)
        ).all()
    )

    order = {
        "name": func.lower(Project.name),
        "code": Project.code,
        "planned": Project.planned_budget,
        "actual": actual,
        "remaining": Project.planned_budget - actual,
        # Spending without any budget ranks above everything else.
        "consumed": func.coalesce(
            actual / func.nullif(Project.planned_budget, 0), actual * 1_000_000_000
        ),
    }[sort]
    page = session.execute(
        select(Project, actual)
        .where(matches)
        .options(joinedload(Project.department), joinedload(Project.manager))
        .order_by(order.desc() if descending else order.asc(), Project.id)
        .limit(limit)
        .offset(offset)
    )
    items = [
        BudgetRow(
            id=project.id,
            code=project.code,
            name=project.name,
            department=NamedItem.model_validate(project.department),
            manager=NamedItem(id=project.manager.id, name=project.manager.full_name)
            if project.manager
            else None,
            project_status=project.status,
            budget=make_budget(project.planned_budget, amount, warning),
        )
        for project, amount in page
    ]
    totals = make_budget(planned_sum, actual_sum, warning)
    return BudgetPage(
        items=items,
        total=total,
        planned=totals.planned,
        actual=totals.actual,
        remaining=totals.remaining,
        consumed_percent=totals.consumed_percent,
        by_status=counts,
    )
