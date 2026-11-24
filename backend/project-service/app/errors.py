"""One consistent JSON shape for every API error."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, OperationalError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)

ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "access_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    503: "service_unavailable",
}


# Friendly messages for the database rules users are most likely to meet.
CONSTRAINT_MESSAGES = {
    "uq_users_email_lower": "An account with this email already exists.",
    "uq_departments_name_lower": "A department with this name already exists.",
    "uq_projects_code_lower": "A project with this code already exists.",
    "fk_expenses_project_id": "This project has expenses, so it cannot be deleted.",
    "uq_deliverables_project_id_name": (
        "This project already has a deliverable with this name."
    ),
    "uq_milestones_project_id_name": (
        "This project already has a milestone with this name."
    ),
    "pk_deliverable_dependencies": "This dependency already exists.",
    "deliverable_dependencies_no_cycle": ("This would create a circular dependency."),
    "uq_resources_employee_code": "This employee code is already used.",
    "uq_resources_email_lower": "A resource with this email already exists.",
    "uq_resources_user_id": "This account is already linked to a resource.",
    "uq_project_resource_assignments_project_id_resource_id": (
        "This person is already assigned to the project."
    ),
    "fk_project_resource_assignments_resource_id": (
        "This person still has project assignments."
    ),
    "fk_deliverables_owner_id": "This person still owns deliverables.",
    "uq_expense_categories_name": "A category with this name already exists.",
    "uq_expense_categories_name_lower": "A category with this name already exists.",
    "fk_expenses_category_id": "This category is used by expenses.",
    "fk_projects_manager_id": "This user still manages projects.",
    "fk_projects_department_id": "The department is used by projects.",
    "fk_resources_department_id": "The department is used by resources.",
}
# The form field to highlight for each duplicate.
CONSTRAINT_FIELDS = {
    "uq_users_email_lower": "email",
    "uq_departments_name_lower": "name",
    "uq_projects_code_lower": "code",
    "uq_expense_categories_name": "name",
    "uq_expense_categories_name_lower": "name",
    "uq_resources_employee_code": "employee_code",
    "uq_resources_email_lower": "email",
    "uq_resources_user_id": "user_id",
    "uq_project_resource_assignments_project_id_resource_id": "resource_id",
    "uq_deliverables_project_id_name": "name",
    "uq_milestones_project_id_name": "name",
    "pk_deliverable_dependencies": "predecessor_id",
    "deliverable_dependencies_no_cycle": "predecessor_id",
}
NO_CYCLE = "deliverable_dependencies_no_cycle"
UNIQUE_VIOLATION, FOREIGN_KEY_VIOLATION = "23505", "23503"
RESTRICT_VIOLATION = "23001"


class ApiError(Exception):
    """A deliberate error with a message that is safe to show to users."""

    def __init__(
        self,
        status: int,
        message: str,
        code: str | None = None,
        headers: dict[str, str] | None = None,
        field: str | None = None,
    ) -> None:
        """Store the response details.

        Args:
            status: HTTP status code.
            message: Message for the user.
            code: Machine-readable code; derived from the status when omitted.
            headers: Extra response headers.
            field: The input field at fault, if any.
        """
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code
        self.headers = headers
        self.details = [{"field": field, "message": message}] if field else []


def error_response(
    status: int,
    message: str,
    code: str | None = None,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an error response.

    Args:
        status: HTTP status code.
        message: Message that is safe to show to users.
        code: Machine-readable code; derived from the status when omitted.
        details: Per-field problems, if any.
        headers: Extra response headers.

    Returns:
        The JSON response.
    """
    body = {
        "code": code or ERROR_CODES.get(status, "error"),
        "message": message,
        "details": details or [],
    }
    return JSONResponse({"error": body}, status_code=status, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    """Attach the shared error handlers to an application.

    Args:
        app: The application to configure.
    """

    @app.exception_handler(HTTPException)
    async def on_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        """Handle deliberate HTTP errors, including unknown routes."""
        return error_response(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def on_invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle invalid input. The submitted values are not echoed back."""
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"]),
                "message": err["msg"].removeprefix("Value error, "),
            }
            for err in exc.errors()
        ]
        return error_response(
            400, "Some fields are invalid.", "validation_error", details
        )

    @app.exception_handler(ApiError)
    async def on_api_error(_: Request, exc: ApiError) -> JSONResponse:
        """Handle errors raised on purpose by the application."""
        return error_response(
            exc.status, exc.message, exc.code, exc.details, exc.headers
        )

    @app.exception_handler(IntegrityError)
    async def on_rule_broken(_: Request, exc: IntegrityError) -> JSONResponse:
        """Handle values that break a database rule."""
        diagnostics = exc.orig.diag
        message = CONSTRAINT_MESSAGES.get(diagnostics.constraint_name or "")
        field = CONSTRAINT_FIELDS.get(diagnostics.constraint_name or "")

        def details_for(text: str) -> list[dict[str, Any]]:
            """Point at the form field, when one is known."""
            return [{"field": field, "message": text}] if field else []

        if diagnostics.constraint_name == NO_CYCLE:
            return error_response(
                409, message, "circular_dependency", details_for(message)
            )
        if diagnostics.sqlstate == UNIQUE_VIOLATION:
            message = message or "This record already exists."
            return error_response(409, message, details=details_for(message))
        if diagnostics.sqlstate in (FOREIGN_KEY_VIOLATION, RESTRICT_VIOLATION):
            fallback = "This record is linked to another record."
            return error_response(409, message or fallback)
        return error_response(400, message or "The values break a data rule.")

    @app.exception_handler(DataError)
    async def on_bad_data(_: Request, exc: DataError) -> JSONResponse:
        """Handle values the database cannot store."""
        logger.info("Rejected data: %s", type(exc.orig).__name__)
        return error_response(400, "Some values cannot be stored.")

    @app.exception_handler(OperationalError)
    async def on_database_down(_: Request, exc: OperationalError) -> JSONResponse:
        """Handle an unreachable database without exposing connection details."""
        logger.error("Database unavailable: %s", exc)
        return error_response(503, "The database is currently unavailable.")

    @app.exception_handler(Exception)
    async def on_unexpected(_: Request, exc: Exception) -> JSONResponse:
        """Handle anything else as a generic server error."""
        logger.error("Unexpected error", exc_info=exc)
        return error_response(500, "An unexpected error occurred.", "server_error")
