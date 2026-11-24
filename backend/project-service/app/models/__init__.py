"""Database models. Importing this package registers every table."""

from app.models.base import Base
from app.models.budget import Expense, ExpenseCategory
from app.models.deliverables import Deliverable, DeliverableDependency, Milestone
from app.models.people import Department, Resource, User
from app.models.projects import Project, ProjectAssignment
from app.models.settings import AppSetting

__all__ = [
    "AppSetting",
    "Base",
    "Deliverable",
    "DeliverableDependency",
    "Department",
    "Expense",
    "ExpenseCategory",
    "Milestone",
    "Project",
    "ProjectAssignment",
    "Resource",
    "User",
]
