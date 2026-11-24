"""The single place that says which role may do what."""

from enum import StrEnum


class Role(StrEnum):
    """User roles."""

    ADMIN = "admin"
    PROJECT_MANAGER = "project_manager"
    TEAM_MEMBER = "team_member"


class Permission(StrEnum):
    """Actions that can be granted to a role.

    Project and deliverable permissions are also limited to specific records
    by the rules in app/auth/scopes.py.
    """

    MANAGE_USERS = "users:manage"
    MANAGE_DEPARTMENTS = "departments:manage"
    MANAGE_SETTINGS = "settings:manage"
    MANAGE_RESOURCES = "resources:manage"
    VIEW_RESOURCES = "resources:view"
    CREATE_PROJECTS = "projects:create"
    DELETE_PROJECTS = "projects:delete"
    EDIT_PROJECTS = "projects:edit"
    MANAGE_DELIVERABLES = "deliverables:manage"
    UPDATE_DELIVERABLE_STATUS = "deliverables:update_status"
    MANAGE_DEPENDENCIES = "dependencies:manage"
    ASSIGN_RESOURCES = "resources:assign"
    MANAGE_BUDGETS = "budgets:manage"
    VIEW_REPORTS = "reports:view"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),
    Role.PROJECT_MANAGER: frozenset(
        {
            Permission.VIEW_RESOURCES,
            Permission.EDIT_PROJECTS,
            Permission.MANAGE_DELIVERABLES,
            Permission.UPDATE_DELIVERABLE_STATUS,
            Permission.MANAGE_DEPENDENCIES,
            Permission.ASSIGN_RESOURCES,
            Permission.MANAGE_BUDGETS,
            Permission.VIEW_REPORTS,
        }
    ),
    Role.TEAM_MEMBER: frozenset({Permission.UPDATE_DELIVERABLE_STATUS}),
}


def has_permission(role: str, permission: Permission) -> bool:
    """Check whether a role includes a permission.

    Args:
        role: The user's role. Unknown roles have no permissions.
        permission: The permission to check.

    Returns:
        True when the role includes the permission.
    """
    try:
        return permission in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False
