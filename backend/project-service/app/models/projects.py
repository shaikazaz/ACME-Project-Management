"""Projects and the resources assigned to them."""

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    PRIORITIES,
    Base,
    Money,
    Percent,
    PrimaryKey,
    TimestampMixin,
    not_blank,
    one_of,
)
from app.models.people import Department, Resource, User

PROJECT_STATUSES = ("Planned", "Active", "On Hold", "Completed", "Cancelled")


class Project(TimestampMixin, Base):
    """A project.

    Actual spending and progress are not columns. They are calculated from
    expenses and deliverables, so they can never disagree with the records.
    """

    __tablename__ = "projects"

    id: Mapped[PrimaryKey]
    code: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, server_default="")
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    start_date: Mapped[date]
    end_date: Mapped[date] = mapped_column(index=True)
    actual_completion_date: Mapped[date | None]
    status: Mapped[str] = mapped_column(
        String(20), server_default="Planned", index=True
    )
    priority: Mapped[str] = mapped_column(String(10), server_default="Medium")
    planned_budget: Mapped[Money] = mapped_column(server_default="0")

    department: Mapped[Department] = relationship()
    manager: Mapped[User | None] = relationship()
    assignments: Mapped[list["ProjectAssignment"]] = relationship(
        back_populates="project", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint(not_blank("code"), name="code_not_blank"),
        CheckConstraint(not_blank("name"), name="name_not_blank"),
        CheckConstraint(one_of("status", PROJECT_STATUSES), name="status_valid"),
        CheckConstraint(one_of("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint("end_date >= start_date", name="dates_in_order"),
        CheckConstraint(
            "(status = 'Completed') = (actual_completion_date IS NOT NULL)",
            name="completion_date_matches_status",
        ),
        CheckConstraint(
            "actual_completion_date >= start_date", name="completed_after_start"
        ),
        CheckConstraint("planned_budget >= 0", name="planned_budget_not_negative"),
        Index("uq_projects_code_lower", func.lower(code), unique=True),
    )


class ProjectAssignment(TimestampMixin, Base):
    """How much of a resource's time is allocated to a project."""

    __tablename__ = "project_resource_assignments"

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="RESTRICT"), index=True
    )
    project_role: Mapped[str] = mapped_column(String(120), server_default="")
    allocation_percent: Mapped[Percent]
    start_date: Mapped[date]
    end_date: Mapped[date]

    project: Mapped[Project] = relationship(back_populates="assignments")
    resource: Mapped[Resource] = relationship()

    __table_args__ = (
        UniqueConstraint("project_id", "resource_id"),
        CheckConstraint(
            "allocation_percent > 0 AND allocation_percent <= 100",
            name="allocation_percent_range",
        ),
        CheckConstraint("end_date >= start_date", name="dates_in_order"),
    )
