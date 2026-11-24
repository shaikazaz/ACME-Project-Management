"""Shared request and response building blocks."""

from typing import Annotated, Generic, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


class RequestModel(BaseModel):
    """Base for request bodies: trims text and rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    """Base for responses built from database records."""

    model_config = ConfigDict(from_attributes=True)


Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    """One page of results."""

    items: list[Item]
    total: int


Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]
Name = Annotated[str, StringConstraints(min_length=1, max_length=120)]


def _check_password(value: str) -> str:
    """Reject passwords that are only one repeated character."""
    if len(set(value)) < 4:
        raise ValueError("Password must use at least 4 different characters")
    return value


# Passwords are used exactly as typed, so spaces are not trimmed.
NewPassword = Annotated[
    str,
    StringConstraints(strip_whitespace=False, min_length=12, max_length=128),
    AfterValidator(_check_password),
]
EnteredPassword = Annotated[
    str, StringConstraints(strip_whitespace=False, min_length=1, max_length=128)
]
