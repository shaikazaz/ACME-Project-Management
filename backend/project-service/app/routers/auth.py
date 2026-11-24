"""Sign-in, sign-out and current-user endpoints."""

from fastapi import APIRouter

from app.auth.dependencies import (
    CurrentUser,
    SessionDep,
    unauthorized,
    user_from_token,
)
from app.auth.passwords import verify_password
from app.auth.permissions import ROLE_PERMISSIONS, Role
from app.auth.service import authenticate, revoke_tokens, set_password
from app.auth.shared import is_shared
from app.auth.tokens import LIFETIMES, create_token
from app.errors import ApiError
from app.models import User
from app.schemas.users import (
    AccessTokenResponse,
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    UserResponse,
)

public_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_SECONDS = int(LIFETIMES["access"].total_seconds())


def describe(user: User) -> CurrentUserResponse:
    """Describe a user together with the permissions of their role."""
    account = UserResponse.model_validate(user).model_dump()
    permissions = sorted(ROLE_PERMISSIONS[Role(user.role)])
    return CurrentUserResponse(**account, permissions=permissions)


def start_session(user: User) -> LoginResponse:
    """Issue new tokens for a user."""
    return LoginResponse(
        access_token=create_token(user.id, user.token_version, "access"),
        refresh_token=create_token(user.id, user.token_version, "refresh"),
        expires_in=ACCESS_SECONDS,
        user=describe(user),
    )


@public_router.post("/login")
def login(body: LoginRequest, session: SessionDep) -> LoginResponse:
    """Sign in with an email and password."""
    user = authenticate(session, body.email, body.password)
    if user is None:
        raise unauthorized(
            "invalid_credentials",
            "Email or password is incorrect, or the account is temporarily locked.",
        )
    return start_session(user)


@public_router.post("/refresh")
def refresh(body: RefreshRequest, session: SessionDep) -> AccessTokenResponse:
    """Exchange a refresh token for a new access token."""
    user = user_from_token(session, body.refresh_token, "refresh")
    return AccessTokenResponse(
        access_token=create_token(user.id, user.token_version, "access"),
        expires_in=ACCESS_SECONDS,
    )


@router.post("/logout", status_code=204)
def logout(user: CurrentUser, session: SessionDep) -> None:
    """Sign out on every device by making all of the user's tokens invalid.

    A shared demo account signs out only here, so other visitors stay signed in.
    """
    if is_shared(user):
        return
    revoke_tokens(user)
    session.commit()


@router.get("/me")
def read_current_user(user: CurrentUser) -> CurrentUserResponse:
    """Return the signed-in user."""
    return describe(user)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest, user: CurrentUser, session: SessionDep
) -> LoginResponse:
    """Change the signed-in user's password and sign out other devices."""
    if not verify_password(body.current_password, user.password_hash):
        raise ApiError(400, "Your current password is incorrect.")
    set_password(user, body.new_password)
    session.commit()
    return start_session(user)
