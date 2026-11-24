"""Project expenses."""

from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Money, PrimaryKey, TimestampMixin, not_blank
from app.models.people import User
from app.models.projects import Project


class ExpenseCategory(TimestampMixin, Base):
    """A type of expense, such as software or travel."""

    __tablename__ = "expense_categories"

    id: Mapped[PrimaryKey]
    name: Mapped[str] = mapped_column(String(80), unique=True)

    __table_args__ = (
        CheckConstraint(not_blank("name"), name="name_not_blank"),
        Index("uq_expense_categories_name_lower", func.lower(name), unique=True),
    )


class Expense(TimestampMixin, Base):
    """Money spent on a project.

    Expenses block deletion of their project, so financial history cannot
    disappear by accident.
    """

    __tablename__ = "expenses"

    id: Mapped[PrimaryKey]
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    amount: Mapped[Money]
    expense_date: Mapped[date]
    description: Mapped[str] = mapped_column(Text, server_default="")

    project: Mapped[Project] = relationship()
    category: Mapped[ExpenseCategory] = relationship()
    created_by: Mapped[User | None] = relationship()

    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)
