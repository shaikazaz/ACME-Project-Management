"""Limits for the shared demo accounts of a public deployment.

Their passwords are shown on the sign-in page, so anyone can use them. They keep
the role they show, but cannot delete anything, change accounts or settings, see
the emails of real people, or stop other visitors from signing in.
"""

from fastapi import Request

from app.auth.dependencies import CurrentUser
from app.errors import ApiError
from app.models import User

# The example domain ".test" can never belong to a real person.
SHARED_ACCOUNTS = {
    "demo.admin@acme.test": ("Demo Admin", "admin"),
    "demo.manager@acme.test": ("Demo Project Manager", "project_manager"),
    "demo.member@acme.test": ("Demo Team Member", "team_member"),
}
FICTIONAL_DOMAINS = ("@acme.test", "@demo.acme.test")
HIDDEN_EMAIL = "Hidden in the demo"
READ_METHODS = ("GET", "HEAD", "OPTIONS")
CHANGE_METHODS = ("POST", "PUT", "PATCH")
# Everything else is read-only, including endpoints added later.
CHANGEABLE_PATHS = ("/projects", "/deliverables/", "/expenses/")
SIGN_OUT_PATH = "/auth/logout"


def is_shared(user: User) -> bool:
    """Check whether an account is a shared demo account."""
    return user.email.lower() in SHARED_ACCOUNTS


def visible_email(viewer: User, email: str) -> str:
    """Return an email, unless it may be real and the viewer is shared."""
    if is_shared(viewer) and not email.lower().endswith(FICTIONAL_DOMAINS):
        return HIDDEN_EMAIL
    return email


def limit_shared_accounts(request: Request, user: CurrentUser) -> None:
    """Refuse requests that a shared demo account must not make.

    Args:
        request: The request, whose route is already known.
        user: The signed-in user.

    Raises:
        ApiError: 403 when a shared account asks for a protected change.
    """
    if not is_shared(user) or request.method in READ_METHODS:
        return
    path = request.scope["route"].path
    changeable = path.startswith(CHANGEABLE_PATHS) or path == SIGN_OUT_PATH
    if request.method not in CHANGE_METHODS or not changeable:
        raise ApiError(
            403,
            "The shared demo accounts cannot do this. They can view everything, "
            "and add and edit project work.",
            "demo_account_limited",
        )
