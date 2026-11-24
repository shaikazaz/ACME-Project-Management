"""AI insight formats."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import ResponseModel
from app.schemas.projects import RiskLevel

Level = Literal["High", "Medium", "Low"]
NoticeCode = Literal[
    "not_configured",
    "timeout",
    "rate_limited",
    "unavailable",
    "invalid_response",
]


class Action(BaseModel):
    """A recommended action. A person decides whether to do it."""

    model_config = ConfigDict(extra="forbid")

    action: str
    reason: str
    priority: Level


class Insights(BaseModel):
    """What the AI provider must return, and what the user sees."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    deadline: list[str]
    budget: list[str]
    resources: list[str]
    deliverables: list[str]
    actions: list[Action]


class Metric(ResponseModel):
    """A figure calculated by the existing business rules."""

    label: str
    value: str


class Notice(ResponseModel):
    """Why the AI provider was not used."""

    code: NoticeCode
    message: str


class InsightsResponse(ResponseModel):
    """Insights, and where they come from."""

    source: Literal["ai", "rules"]
    model: str | None
    notice: Notice | None
    generated_at: datetime
    risk_level: RiskLevel | None
    metrics: list[Metric]
    unavailable: list[str]
    insights: Insights
