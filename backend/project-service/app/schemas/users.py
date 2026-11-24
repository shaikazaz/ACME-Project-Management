"""User and sign-in formats. Password hashes are never included."""

from datetime import datetime
from typing import Literal

from app.schemas.common import (
    Email,
    EnteredPassword,
    Name,
    NewPassword,
    RequestModel,
    ResponseModel,
)

RoleName = Literal["admin", "project_manager", "team_member"]


class LoginRequest(RequestModel):
    """Sign-in details."""

    email: Email
    password: EnteredPassword


class RefreshRequest(RequestModel):
    """Request for a new access token."""

    refresh_token: str


class ChangePasswordRequest(RequestModel):
    """A user changing their own password."""

    current_password: EnteredPassword
    new_password: NewPassword


class UserResponse(ResponseModel):
    """A user account."""

    id: int
    email: str
    full_name: str
    role: RoleName
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CurrentUserResponse(UserResponse):
    """The signed-in user, with the permissions of their role."""

    permissions: list[str]


class AccessTokenResponse(ResponseModel):
    """A new access token."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # nosec B105 - not a password
    expires_in: int


class LoginResponse(AccessTokenResponse):
    """The result of signing in."""

    refresh_token: str
    user: CurrentUserResponse


class UserUpdate(RequestModel):
    """Editable account fields."""

    email: Email
    full_name: Name
    role: RoleName
    is_active: bool = True


class UserCreate(UserUpdate):
    """A new account."""

    password: NewPassword


class ResetPasswordRequest(RequestModel):
    """An admin setting a user's password."""

    new_password: NewPassword
