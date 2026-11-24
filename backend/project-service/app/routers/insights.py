"""AI insight endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, SessionDep
from app.auth.permissions import Permission
from app.auth.scopes import managed_project
from app.models import Project
from app.schemas.insights import InsightsResponse
from app.services import insights as service

router = APIRouter(tags=["insights"])

ManagedProject = Annotated[Project, Depends(managed_project(Permission.VIEW_REPORTS))]


@router.post("/projects/{project_id}/insights")
def generate_insights(
    project: ManagedProject, session: SessionDep, user: CurrentUser
) -> InsightsResponse:
    """Explain the latest data of a project the user manages. Saves nothing."""
    facts = service.collect_facts(session, user, project)
    # Free the database connection while waiting for the AI provider.
    session.rollback()
    return service.generate(facts)
