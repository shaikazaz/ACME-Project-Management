"""User administration. Admins only."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.auth.dependencies import SessionDep, require
from app.auth.passwords import hash_password
from app.auth.permissions import Permission, Role
from app.auth.service import ensure_another_admin, revoke_tokens, set_password
from app.auth.shared import FICTIONAL_DOMAINS, HIDDEN_EMAIL, is_shared, visible_email
from app.errors import ApiError
from app.models import User
from app.schemas.common import Page
from app.schemas.users import (
    ResetPasswordRequest,
    RoleName,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])

Admin = Annotated[User, Depends(require(Permission.MANAGE_USERS))]


def find_user(user_id: int, session: SessionDep, _: Admin) -> User:
    """Load the user named in the path, or fail with 404."""
    user = session.get(User, user_id)
    if user is None:
        raise ApiError(404, "User not found.")
    return user


TargetUser = Annotated[User, Depends(find_user)]


@router.get("")
def list_users(
    session: SessionDep,
    admin: Admin,
    search: Annotated[str, Query(max_length=100)] = "",
    role: RoleName | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Page[UserResponse]:
    """List accounts, optionally searched and filtered."""
    conditions = []
    if is_shared(admin):
        # Also keeps a search from guessing a hidden email.
        conditions.append(
            or_(*(User.email.iendswith(domain) for domain in FICTIONAL_DOMAINS))
        )
    if search:
        conditions.append(
            or_(
                User.full_name.icontains(search, autoescape=True),
                User.email.icontains(search, autoescape=True),
            )
        )
    if role is not None:
        conditions.append(User.role == role)
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    total = session.scalar(select(func.count()).select_from(User).where(*conditions))
    users = session.scalars(
        select(User)
        .where(*conditions)
        .order_by(User.full_name, User.id)
        .limit(limit)
        .offset(offset)
    )
    return Page(
        items=[UserResponse.model_validate(user) for user in users], total=total
    )


@router.post("", status_code=201)
def create_user(body: UserCreate, session: SessionDep, _: Admin) -> UserResponse:
    """Create an account."""
    values = body.model_dump(exclude={"password"})
    user = User(**values, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    return UserResponse.model_validate(user)


@router.get("/{user_id}")
def read_user(user: TargetUser, admin: Admin) -> UserResponse:
    """Return one account."""
    if visible_email(admin, user.email) == HIDDEN_EMAIL:
        raise ApiError(404, "User not found.")
    return UserResponse.model_validate(user)


@router.put("/{user_id}")
def update_user(
    body: UserUpdate, user: TargetUser, admin: Admin, session: SessionDep
) -> UserResponse:
    """Update an account. Role or status changes sign the user out."""
    access_changed = (user.role, user.is_active) != (body.role, body.is_active)
    if access_changed and user.id == admin.id:
        raise ApiError(409, "You cannot change your own role or status.")
    if access_changed and user.role == Role.ADMIN:
        ensure_another_admin(session, user)
    for field, value in body.model_dump().items():
        setattr(user, field, value)
    if access_changed:
        revoke_tokens(user)
    session.commit()
    return UserResponse.model_validate(user)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(
    body: ResetPasswordRequest, user: TargetUser, session: SessionDep
) -> None:
    """Set a user's password and sign them out."""
    set_password(user, body.new_password)
    session.commit()


@router.delete("/{user_id}", status_code=204)
def delete_user(user: TargetUser, admin: Admin, session: SessionDep) -> None:
    """Delete an account that manages no projects."""
    if user.id == admin.id:
        raise ApiError(409, "You cannot delete your own account.")
    if user.role == Role.ADMIN:
        ensure_another_admin(session, user)
    session.delete(user)
    session.commit()
