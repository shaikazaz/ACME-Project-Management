"""Departments, login accounts and resources (the people doing the work)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    Percent,
    PrimaryKey,
    TimestampMixin,
    not_blank,
    one_of,
)

USER_ROLES = ("admin", "project_manager", "team_member")
AVAILABILITY = ("Available", "On Leave", "Unavailable")


class Department(TimestampMixin, Base):
    """A business department."""

    __tablename__ = "departments"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, server_default="")

    __table_args__ = (
        CheckConstraint(not_blank("name"), name="name_not_blank"),
        Index("uq_departments_name_lower", func.lower(name), unique=True),
    )


class User(TimestampMixin, Base):
    """A login account. Only a password hash is ever stored."""

    __tablename__ = "users"

    id: Mapped[PrimaryKey]
    email: Mapped[str] = mapped_column(String(254))
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(server_default="true")
    # Raising this number invalidates every token already issued to the user.
    token_version: Mapped[int] = mapped_column(server_default="0")
    failed_login_count: Mapped[int] = mapped_column(server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    resource: Mapped["Resource | None"] = relationship(back_populates="user")

    __table_args__ = (
        CheckConstraint(one_of("role", USER_ROLES), name="role_valid"),
        CheckConstraint(not_blank("email"), name="email_not_blank"),
        CheckConstraint(not_blank("full_name"), name="full_name_not_blank"),
        CheckConstraint(not_blank("password_hash"), name="password_hash_not_blank"),
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )


class Resource(TimestampMixin, Base):
    """An employee who can be assigned to projects.

    A resource does not need a login, and a login does not need a resource.
    """

    __tablename__ = "resources"

    id: Mapped[PrimaryKey]
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    employee_code: Mapped[str] = mapped_column(String(30), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254))
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    job_title: Mapped[str] = mapped_column(String(120))
    skills: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    capacity_percent: Mapped[Percent] = mapped_column(server_default="100")
    availability: Mapped[str] = mapped_column(String(20), server_default="Available")

    user: Mapped[User | None] = relationship(back_populates="resource")
    department: Mapped[Department] = relationship()

    __table_args__ = (
        CheckConstraint(not_blank("employee_code"), name="employee_code_not_blank"),
        CheckConstraint(not_blank("full_name"), name="full_name_not_blank"),
        CheckConstraint(
            "capacity_percent BETWEEN 0 AND 100", name="capacity_percent_range"
        ),
        CheckConstraint(
            one_of("availability", AVAILABILITY), name="availability_valid"
        ),
        Index("uq_resources_email_lower", func.lower(email), unique=True),
    )
