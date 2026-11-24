"""Milestones, deliverables and the dependencies between deliverables."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    PRIORITIES,
    Base,
    Hours,
    Percent,
    PrimaryKey,
    TimestampMixin,
    not_blank,
    one_of,
)
from app.models.people import Resource
from app.models.projects import Project

DELIVERABLE_STATUSES = ("Not Started", "In Progress", "Blocked", "Completed")


class Milestone(TimestampMixin, Base):
    """A key date in a project."""

    __tablename__ = "milestones"

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    due_date: Mapped[date]
    completed_date: Mapped[date | None]

    project: Mapped[Project] = relationship()

    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        # Target of the deliverables foreign key below.
        UniqueConstraint("id", "project_id"),
        CheckConstraint(not_blank("name"), name="name_not_blank"),
    )


class Deliverable(TimestampMixin, Base):
    """A piece of work that a project must deliver."""

    __tablename__ = "deliverables"

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    milestone_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("resources.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    start_date: Mapped[date]
    due_date: Mapped[date] = mapped_column(index=True)
    completion_date: Mapped[date | None]
    status: Mapped[str] = mapped_column(
        String(20), server_default="Not Started", index=True
    )
    priority: Mapped[str] = mapped_column(String(10), server_default="Medium")
    progress_percent: Mapped[Percent] = mapped_column(server_default="0")
    estimated_hours: Mapped[Hours] = mapped_column(server_default="0")
    actual_hours: Mapped[Hours] = mapped_column(server_default="0")

    project: Mapped[Project] = relationship()
    owner: Mapped[Resource | None] = relationship()
    milestone: Mapped[Milestone | None] = relationship(
        foreign_keys=[milestone_id], viewonly=True
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        # A deliverable may only use a milestone from its own project.
        ForeignKeyConstraint(
            ["milestone_id", "project_id"],
            ["milestones.id", "milestones.project_id"],
            ondelete="SET NULL (milestone_id)",
        ),
        CheckConstraint(not_blank("name"), name="name_not_blank"),
        CheckConstraint(one_of("status", DELIVERABLE_STATUSES), name="status_valid"),
        CheckConstraint(one_of("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint("due_date >= start_date", name="dates_in_order"),
        CheckConstraint(
            "(status = 'Completed') = (completion_date IS NOT NULL)",
            name="completion_date_matches_status",
        ),
        CheckConstraint("completion_date >= start_date", name="completed_after_start"),
        CheckConstraint(
            "progress_percent BETWEEN 0 AND 100", name="progress_percent_range"
        ),
        CheckConstraint(
            "status <> 'Completed' OR progress_percent = 100",
            name="completed_means_full_progress",
        ),
        CheckConstraint("estimated_hours >= 0", name="estimated_hours_not_negative"),
        CheckConstraint("actual_hours >= 0", name="actual_hours_not_negative"),
    )


class DeliverableDependency(Base):
    """The successor cannot proceed until the predecessor is completed.

    A database trigger rejects circular chains. Dependencies may cross
    projects, so project-to-project dependencies are visible too.
    """

    __tablename__ = "deliverable_dependencies"

    predecessor_id: Mapped[int] = mapped_column(
        ForeignKey("deliverables.id", ondelete="CASCADE"), primary_key=True
    )
    successor_id: Mapped[int] = mapped_column(
        ForeignKey("deliverables.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    predecessor: Mapped[Deliverable] = relationship(foreign_keys=[predecessor_id])
    successor: Mapped[Deliverable] = relationship(foreign_keys=[successor_id])

    __table_args__ = (
        CheckConstraint("predecessor_id <> successor_id", name="not_self"),
    )
