"""FastAPI application factory."""

from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Request, Response

from app.auth.dependencies import get_current_user
from app.auth.shared import limit_shared_accounts
from app.errors import register_error_handlers
from app.routers import (
    assignments,
    auth,
    budgets,
    dashboard,
    deliverables,
    departments,
    expenses,
    health,
    insights,
    milestones,
    projects,
    resources,
    settings,
    users,
)

PUBLIC_ROUTERS = (health.router, auth.public_router)
PROTECTED_ROUTERS = (
    auth.router,
    users.router,
    departments.router,
    settings.router,
    projects.router,
    deliverables.router,
    milestones.router,
    resources.router,
    assignments.router,
    budgets.router,
    expenses.router,
    dashboard.router,
    insights.router,
)


def create_app() -> FastAPI:
    """Create and configure the application.

    Returns:
        The configured application.
    """
    application = FastAPI(
        title="ACME Project Management API",
        # Public API docs stay off: the Lambda URL is reachable by anyone.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    register_error_handlers(application)

    @application.middleware("http")
    async def prevent_caching(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Stop browsers and proxies from storing private responses."""
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    for router in PUBLIC_ROUTERS:
        application.include_router(router)
    # Sign-in is enforced here, so a new endpoint cannot forget it.
    for router in PROTECTED_ROUTERS:
        application.include_router(
            router,
            dependencies=[Depends(get_current_user), Depends(limit_shared_accounts)],
        )
    return application


app = create_app()
