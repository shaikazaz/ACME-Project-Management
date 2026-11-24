"""Shared building blocks for all database models."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names keep migrations and error handling reliable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}

PRIORITIES = ("Low", "Medium", "High", "Critical")

PrimaryKey = Annotated[
    int, mapped_column(BigInteger, Identity(always=True), primary_key=True)
]
# Exact decimals: floating point would introduce rounding errors.
Money = Annotated[Decimal, mapped_column(Numeric(14, 2))]
Percent = Annotated[Decimal, mapped_column(Numeric(5, 2))]
Hours = Annotated[Decimal, mapped_column(Numeric(8, 2))]


class Base(DeclarativeBase):
    """Base class for all models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds created and updated timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def one_of(column: str, values: tuple[str, ...]) -> str:
    """Build the SQL condition that restricts a column to fixed values.

    Args:
        column: Column name.
        values: Allowed values; must be constants defined in this package.

    Returns:
        The SQL condition for a check constraint.
    """
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


def not_blank(column: str) -> str:
    """Build the SQL condition that rejects empty text.

    Args:
        column: Column name.

    Returns:
        The SQL condition for a check constraint.
    """
    return f"btrim({column}) <> ''"
