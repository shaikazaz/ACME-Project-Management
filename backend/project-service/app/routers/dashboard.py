"""Dashboard endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import SessionDep, require
from app.auth.permissions import Permission
from app.models import User
from app.schemas.dashboard import Dashboard
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Reporter = Annotated[User, Depends(require(Permission.VIEW_REPORTS))]


@router.get("")
def read_dashboard(user: Reporter, session: SessionDep) -> Dashboard:
    """Return the dashboard of the projects the user manages."""
    return build_dashboard(session, user)
