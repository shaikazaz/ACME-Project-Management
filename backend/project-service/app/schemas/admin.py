"""Department and setting formats."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from app.schemas.common import Name, RequestModel, ResponseModel


class DepartmentRequest(RequestModel):
    """Department fields."""

    name: Name
    description: Annotated[str, Field(max_length=2000)] = ""


class DepartmentResponse(ResponseModel):
    """A department."""

    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class SettingRequest(RequestModel):
    """A new value for a setting."""

    value: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class SettingResponse(ResponseModel):
    """A setting."""

    key: str
    value: float
    description: str
    updated_at: datetime
