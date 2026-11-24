"""Sign-in rules and account changes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.passwords import DUMMY_HASH, hash_password, verify_password
from app.auth.permissions import Role
from app.errors import ApiError
from app.models import User

MAX_FAILED_LOGINS = 5
LOCK_DURATION = timedelta(minutes=5)
ADMIN_CHANGE_LOCK_ID = 728403


def authenticate(session: Session, email: str, password: str) -> User | None:
    """Check an email and password, limiting repeated guesses.

    Unknown, inactive and locked accounts do the same work and give the same
    result, so a caller cannot discover which emails exist.

    Args:
        session: Database session. The outcome is committed.
        email: The email entered.
        password: The password entered.

    Returns:
        The user when sign-in succeeds, otherwise None.
    """
    # Locking the row makes simultaneous guesses wait for each other.
    user = session.scalar(
        select(User).where(func.lower(User.email) == email.lower()).with_for_update()
    )
    now = datetime.now(UTC)
    blocked = (
        user is None
        or not user.is_active
        or (user.locked_until is not None and user.locked_until > now)
    )
    if blocked:
        verify_password(password, DUMMY_HASH)
        session.rollback()
        return None
    if verify_password(password, user.password_hash):
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        session.commit()
        return user
    user.failed_login_count += 1
    if user.failed_login_count >= MAX_FAILED_LOGINS:
        user.failed_login_count = 0
        user.locked_until = now + LOCK_DURATION
    session.commit()
    return None


def revoke_tokens(user: User) -> None:
    """Make every token issued to a user invalid.

    Args:
        user: The account to sign out everywhere.
    """
    user.token_version = User.token_version + 1


def set_password(user: User, password: str) -> None:
    """Store a new password hash, unlock the account and sign it out everywhere.

    Args:
        user: The account to change.
        password: The new plain password.
    """
    user.password_hash = hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    revoke_tokens(user)


def ensure_another_admin(session: Session, user: User) -> None:
    """Fail when a user is the last active admin.

    Args:
        session: Database session.
        user: The account about to lose admin access.

    Raises:
        ApiError: 409 when no other active admin exists.
    """
    # Two admins removing each other at the same moment must not both succeed.
    session.execute(
        text("SELECT pg_advisory_xact_lock(:id)"), {"id": ADMIN_CHANGE_LOCK_ID}
    )
    others = session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.role == Role.ADMIN, User.is_active, User.id != user.id)
    )
    if not others:
        raise ApiError(409, "At least one active admin is required.")
