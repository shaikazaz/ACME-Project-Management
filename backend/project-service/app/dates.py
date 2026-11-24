"""Date rules shared by every feature."""

from datetime import UTC, date, datetime, timedelta


def today() -> date:
    """Return the current UTC date, independent of server settings."""
    return datetime.now(UTC).date()


def check_not_in_future(value: date | None) -> date | None:
    """Reject future dates, allowing for time zones ahead of UTC.

    Args:
        value: The date to check.

    Returns:
        The same date.

    Raises:
        ValueError: The date is in the future.
    """
    if value is not None and value > today() + timedelta(days=1):
        raise ValueError("Completion date cannot be in the future")
    return value
