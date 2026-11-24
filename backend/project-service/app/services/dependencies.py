"""Dependencies between deliverables."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth.scopes import visible_deliverables, visible_projects
from app.errors import ApiError
from app.models import Deliverable, DeliverableDependency, Project, User
from app.schemas.deliverables import (
    ChainLink,
    ChainNode,
    DependencyChain,
    RelatedDeliverable,
)
from app.services.deliverables import (
    HIDDEN_NAME,
    effective_status,
    ensure_open,
    is_overdue,
    lock_work,
)


def add_dependency(
    session: Session, user: User, successor: Deliverable, predecessor_id: int
) -> None:
    """Make one deliverable wait for another.

    The database rejects circular chains. See migration 0001.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to see the predecessor.
        successor: The deliverable that waits, which the user may manage.
        predecessor_id: The deliverable that must be completed first.

    Raises:
        ApiError: The dependency is not allowed.
    """
    lock_work(session)
    session.refresh(successor)
    session.refresh(successor.project)
    ensure_open(successor.project)
    if predecessor_id == successor.id:
        raise ApiError(
            400, "A deliverable cannot depend on itself.", field="predecessor_id"
        )
    predecessor = session.scalar(
        select(Deliverable)
        .where(Deliverable.id == predecessor_id, visible_deliverables(user))
        .execution_options(populate_existing=True)
    )
    if predecessor is None:
        raise ApiError(400, "Deliverable not found.", field="predecessor_id")
    if successor.status == "Completed" and predecessor.status != "Completed":
        raise ApiError(
            409, "Completed work cannot wait for unfinished work. Reopen it first."
        )
    session.add(
        DeliverableDependency(predecessor_id=predecessor.id, successor_id=successor.id)
    )
    session.commit()


def remove_dependency(
    session: Session, successor: Deliverable, predecessor_id: int
) -> None:
    """Stop one deliverable from waiting for another.

    Args:
        session: Database session.
        successor: The deliverable that waits, which the user may manage.
        predecessor_id: The deliverable it waits for.

    Raises:
        ApiError: 404 when the dependency does not exist.
    """
    lock_work(session)
    session.refresh(successor.project)
    ensure_open(successor.project)
    link = session.get(DeliverableDependency, (predecessor_id, successor.id))
    if link is None:
        raise ApiError(404, "Dependency not found.")
    session.delete(link)
    session.commit()


def blocks_other_projects(session: Session, project_id: int) -> bool:
    """Check whether deliverables of other projects wait for a project.

    Args:
        session: Database session.
        project_id: The project.

    Returns:
        True when another project depends on it.
    """
    own = select(Deliverable.id).where(Deliverable.project_id == project_id)
    link = DeliverableDependency
    query = select(link).where(
        link.predecessor_id.in_(own), link.successor_id.not_in(own)
    )
    return session.scalar(query.limit(1)) is not None


def _steps(keys: set[int], links: list[tuple[int, int]]) -> dict[int, int]:
    """Number each deliverable by the longest chain that leads to it."""
    steps = dict.fromkeys(keys, 1)
    # Circular chains are impossible, so this settles within len(keys) rounds.
    for _ in keys:
        changed = False
        for before, after in links:
            if steps[after] <= steps[before]:
                steps[after] = steps[before] + 1
                changed = True
        if not changed:
            break
    return steps


def describe_chain(session: Session, user: User, project: Project) -> DependencyChain:
    """Return a project's dependency chain.

    Directly linked deliverables of other projects are included. Their details
    are hidden when the user cannot see those projects.

    Args:
        session: Database session.
        user: The signed-in user, who must be allowed to manage the project.
        project: The project.

    Returns:
        The deliverables in order, and the links between them.
    """
    own = select(Deliverable.id).where(Deliverable.project_id == project.id)
    link = DeliverableDependency
    links = [
        tuple(row)
        for row in session.execute(
            select(link.predecessor_id, link.successor_id)
            .where(or_(link.predecessor_id.in_(own), link.successor_id.in_(own)))
            .order_by(link.predecessor_id, link.successor_id)
        )
    ]
    linked = {key for pair in links for key in pair}
    rows = session.execute(
        select(
            Deliverable,
            Project.code,
            effective_status(),
            is_overdue(),
            visible_projects(user),
        )
        .join(Project, Project.id == Deliverable.project_id)
        .where(or_(Deliverable.project_id == project.id, Deliverable.id.in_(linked)))
        .order_by(Deliverable.start_date, Deliverable.due_date, Deliverable.id)
    ).all()
    steps = _steps({row.id for row, *_ in rows}, links)
    # Real ids of hidden deliverables are not revealed.
    keys = {row.id: f"n{number}" for number, (row, *_) in enumerate(rows)}
    nodes = [
        ChainNode(
            key=keys[row.id],
            deliverable=RelatedDeliverable(
                id=row.id if visible else None,
                name=row.name if visible else HIDDEN_NAME,
                project_code=code if visible else None,
                status=row.status,
            ),
            effective_status=current,
            is_external=row.project_id != project.id,
            is_overdue=late,
            due_date=row.due_date if visible else None,
            step=steps[row.id],
        )
        for row, code, current, late, visible in rows
    ]
    nodes.sort(key=lambda node: node.step)
    return DependencyChain(
        nodes=nodes,
        links=[
            ChainLink(predecessor=keys[before], successor=keys[after])
            for before, after in links
        ],
    )
