"""FastAPI dependencies that protect endpoints."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.permissions import Permission, has_permission
from app.auth.tokens import Purpose, TokenError, TokenExpiredError, read_token
from app.database import get_session
from app.errors import ApiError
from app.models import User

bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[Session, Depends(get_session)]


def unauthorized(code: str, message: str) -> ApiError:
    """Build a 401 error."""
    return ApiError(401, message, code, headers={"WWW-Authenticate": "Bearer"})


def user_from_token(session: Session, token: str, purpose: Purpose) -> User:
    """Find the active user a token belongs to.

    The account is read on every request, so logout, deactivation and role
    changes take effect immediately.

    Args:
        session: Database session.
        token: The encoded token.
        purpose: The purpose the token must have.

    Returns:
        The active user.

    Raises:
        ApiError: 401 when the token cannot be accepted.
    """
    try:
        claims = read_token(token, purpose)
    except TokenExpiredError as exc:
        raise unauthorized("token_expired", "Your session has expired.") from exc
    except TokenError as exc:
        raise unauthorized("invalid_token", "Please sign in again.") from exc
    user = session.get(User, claims.user_id)
    if user is None or not user.is_active or user.token_version != claims.version:
        raise unauthorized("invalid_token", "Please sign in again.")
    return user


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    """Return the signed-in user, or fail with 401."""
    if credentials is None:
        raise unauthorized("not_authenticated", "Please sign in.")
    return user_from_token(session, credentials.credentials, "access")


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(permission: Permission) -> Callable[[User], User]:
    """Create a dependency that requires a permission.

    Args:
        permission: The permission the user must have.

    Returns:
        A dependency that returns the user, or fails with 403.
    """

    def check(user: CurrentUser) -> User:
        """Check the signed-in user's role."""
        if not has_permission(user.role, permission):
            raise ApiError(403, "You do not have permission to do this.")
        return user

    return check
