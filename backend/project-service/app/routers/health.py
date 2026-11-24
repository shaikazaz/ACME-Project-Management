"""Health check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import SERVICE_NAME
from app.database import get_session, ping

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def check_live() -> dict[str, str]:
    """Report that the service is running, without using the database."""
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/ready")
def check_ready(session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    """Report that the service can query PostgreSQL (503 when it cannot)."""
    ping(session)
    return {"status": "ok", "service": SERVICE_NAME, "database": "connected"}
