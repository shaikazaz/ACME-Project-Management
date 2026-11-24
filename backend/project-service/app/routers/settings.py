"""Application settings, such as risk thresholds. Admins only."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.errors import ApiError
from app.models import AppSetting, User
from app.schemas.admin import SettingRequest, SettingResponse
from app.schemas.common import Page

router = APIRouter(prefix="/settings", tags=["settings"])

Admin = Annotated[User, Depends(require(Permission.MANAGE_SETTINGS))]


@router.get("")
def list_settings(session: SessionDep, _: Admin) -> Page[SettingResponse]:
    """List all settings."""
    rows = session.scalars(select(AppSetting).order_by(AppSetting.key)).all()
    items = [SettingResponse.model_validate(row) for row in rows]
    return Page(items=items, total=len(items))


@router.put("/{key}")
def update_setting(
    key: str, body: SettingRequest, session: SessionDep, _: Admin
) -> SettingResponse:
    """Change a setting's value."""
    setting = session.get(AppSetting, key)
    if setting is None:
        raise ApiError(404, "Setting not found.")
    setting.value = body.value
    session.commit()
    return SettingResponse.model_validate(setting)
