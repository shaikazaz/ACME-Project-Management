#!/usr/bin/env python3
"""Add fictional demo data to the local development database.

Usage (from the repository root):

    export IS_LOCAL=true POSTGRES_PASS=<local password>
    .venv/bin/python bin/seed-demo.py            # Dry run: saves nothing
    .venv/bin/python bin/seed-demo.py --insert   # Adds the missing records

The script only adds records. It never updates or deletes one. A demo record
that already exists is skipped together with everything inside it, so running
the script again adds nothing. Everything is saved in one transaction through
the application's own rules, so an error saves nothing.

Demo records are marked: codes start with "DEMO-", emails end with
"@demo.acme.test", and expenses end with "(demo)". All names are fictional.
Dates are relative to the day the script runs.
"""

import argparse
import os
import secrets
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "project-service"))

from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.auth.passwords import hash_password  # noqa: E402
from app.config import load_database_settings  # noqa: E402
from app.database import get_engine  # noqa: E402
from app.dates import today  # noqa: E402
from app.models import (  # noqa: E402
    Deliverable,
    Department,
    Expense,
    ExpenseCategory,
    Milestone,
    Project,
    ProjectAssignment,
    Resource,
    User,
)
from app.schemas.admin import DepartmentRequest  # noqa: E402
from app.schemas.budgets import CategoryRequest, ExpenseRequest  # noqa: E402
from app.schemas.deliverables import (  # noqa: E402
    DeliverableRequest,
    MilestoneRequest,
)
from app.schemas.projects import ProjectRequest  # noqa: E402
from app.schemas.resources import AssignmentRequest, ResourceRequest  # noqa: E402
from app.schemas.users import UserCreate  # noqa: E402
from app.services.assignments import save_assignment  # noqa: E402
from app.services.deliverables import save_deliverable  # noqa: E402
from app.services.dependencies import add_dependency  # noqa: E402
from app.services.expenses import save_expense  # noqa: E402
from app.services.milestones import save_milestone  # noqa: E402
from app.services.projects import save_project  # noqa: E402
from app.services.resources import save_resource  # noqa: E402

DOMAIN = "demo.acme.test"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")

DEPARTMENTS = (
    "IT",
    "Finance",
    "HR",
    "Analytics",
    "Digital",
    "Security",
    "Sales",
    "Operations",
    "Innovation",
)
CATEGORIES = ("Personnel", "Consulting", "Hardware", "Testing", "Cloud Services")

# The Manager demo login manages some projects when it exists, else the admin.
LOGIN_MANAGER, LOGIN_MEMBER = "manager@acme.test", "member@acme.test"
MANAGERS = {
    "kavya": "Kavya Rao",
    "suresh": "Suresh Pillai",
    "anjali": "Anjali Bose",
}

# code: (name, department, job title, skills, capacity, availability)
RESOURCES = {
    "E01": ("Arjun Sharma", "IT", "Senior Developer", "Python, AWS, Docker", 100, "Available"),
    "E02": ("Priya Nair", "Analytics", "Data Analyst", "SQL, Python, Statistics", 100, "Available"),
    "E03": ("Rahul Verma", "Digital", "Software Engineer", "Kotlin, Swift, REST", 100, "Available"),
    "E04": ("Sneha Reddy", "Digital", "UX Designer", "Figma, Research", 100, "Available"),
    "E05": ("Karthik Iyer", "IT", "DevOps Engineer", "Terraform, AWS, Linux", 100, "Available"),
    "E06": ("Neha Kapoor", "IT", "QA Engineer", "Selenium, API testing", 100, "Available"),
    "E07": ("Aditya Rao", "Security", "Security Analyst", "Audit, SIEM", 100, "Available"),
    "E08": ("Divya Menon", "HR", "Business Analyst", "Requirements, Process", 100, "Available"),
    "E09": ("Vikram Singh", "IT", "Software Engineer", "React, Node.js, SQL", 100, "Available"),
    "E10": ("Ananya Das", "Analytics", "Data Analyst", "Power BI, SQL, ETL", 100, "Available"),
    "E11": ("Rohan Mehta", "Operations", "Project Manager", "Planning, Reporting", 100, "On Leave"),
    "E12": ("Meera Krishnan", "Innovation", "Senior Developer", "Python, NLP, APIs", 80, "Available"),
}

# Every day is relative to the day the script runs.
# work: (name, owner, start, due, hours, progress, priority, numbers it waits for)
# team: (person, percent, role) and optionally its own start and end
# Budgets and spending are in US dollars.
# spent: (amount, category, days ago, description)
PROJECTS = (
    {
        "code": "DEMO-01",
        "name": "Customer Portal Modernization",
        "department": "IT",
        "manager": LOGIN_MANAGER,
        "start": -60,
        "end": 30,
        "priority": "High",
        "budget": 2_500_000,
        "description": "Replace the legacy customer portal with a responsive site.",
        "milestone": ("Beta release", 8),
        "work": (
            ("Requirements Analysis", "E09", -60, -46, 40, 100, "High", ()),
            ("UX/UI Design", "E04", -45, -30, 40, 100, "Medium", (0,)),
            ("Frontend Development", "E09", -29, 6, 100, 70, "High", (1,)),
            ("Backend API Development", "E09", -29, 9, 100, 58, "High", (1,)),
            ("User Acceptance Testing", "E06", 10, 28, 40, 0, "High", (2, 3)),
        ),
        "team": (
            ("E04", 60, "UX lead"),
            ("E06", 40, "Tester"),
            ("E09", 50, "Developer"),
        ),
        "spent": (
            (600_000, "Personnel", 40, "Development team"),
            (500_000, "Software", 28, "Component and hosting licences"),
            (350_000, "Consulting", 12, "Accessibility review"),
        ),
    },
    {
        "code": "DEMO-02",
        "name": "Cloud Migration Phase 2",
        "department": "IT",
        "manager": LOGIN_MANAGER,
        "start": -75,
        "end": 25,
        "priority": "Critical",
        "budget": 4_000_000,
        "description": "Move the remaining applications and databases to the cloud.",
        "milestone": ("Migration complete", 20),
        "work": (
            ("Cloud Infrastructure Setup", "E05", -75, -50, 60, 100, "High", ()),
            ("Application Migration", "E01", -49, 3, 100, 48, "High", (0,)),
            ("Database Migration", "E05", -10, 10, 60, 0, "High", (1,)),
            ("Security Validation", "E07", 8, 17, 30, 0, "Medium", (2,)),
            ("Production Cutover", "E05", 18, 25, 20, 0, "High", (3,)),
        ),
        "team": (("E01", 60, "Migration lead"), ("E05", 50, "Cloud engineer")),
        "spent": (
            (900_000, "Cloud Services", 45, "Landing zone and compute"),
            (800_000, "Personnel", 30, "Migration team"),
            (400_000, "Consulting", 15, "Migration assessment"),
        ),
    },
    {
        "code": "DEMO-03",
        "name": "Fraud Detection Platform",
        "department": "Finance",
        "manager": "kavya",
        "start": -50,
        "end": 40,
        "priority": "High",
        "budget": 3_000_000,
        "description": "Score card transactions in real time to find likely fraud.",
        "milestone": ("Model approved", 28),
        "work": (
            ("Data Pipeline Design", "E02", -50, -25, 60, 100, "High", ()),
            ("Fraud Detection Model", "E02", -24, 12, 100, 75, "High", (0,)),
            ("API Integration", "E12", -20, 15, 60, 50, "Medium", ()),
            ("Model Validation", "E02", 13, 28, 40, 0, "High", (1,)),
            ("Production Deployment", "E12", 29, 40, 40, 0, "Medium", (3,)),
        ),
        "team": (("E02", 70, "Data analyst"), ("E12", 50, "Developer")),
        "spent": (
            (700_000, "Personnel", 35, "Data science team"),
            (500_000, "Software", 25, "Analytics licences"),
            (300_000, "Cloud Services", 10, "Model training compute"),
        ),
    },
    {
        "code": "DEMO-04",
        "name": "HR Self-Service Portal",
        "department": "HR",
        "manager": "suresh",
        "start": -70,
        "end": 15,
        "priority": "Medium",
        "budget": 1_200_000,
        "description": "Let employees manage their profile, leave and payroll.",
        "milestone": ("Go-live", 15),
        "work": (
            ("Employee Profile Module", "E08", -70, -45, 70, 100, "Medium", ()),
            ("Leave Management", "E08", -44, -20, 50, 100, "Medium", ()),
            ("Payroll Integration", "E08", -19, 5, 50, 80, "High", ()),
            ("User Acceptance Testing", "E11", 6, 14, 30, 0, "Medium", (2,)),
        ),
        "team": (("E08", 50, "Business analyst"), ("E11", 20, "Coordinator")),
        "spent": (
            (500_000, "Personnel", 50, "Portal team"),
            (220_000, "Software", 30, "HR platform licence"),
            (120_000, "Training", 7, "Administrator training"),
        ),
    },
    {
        "code": "DEMO-05",
        "name": "Data Warehouse Upgrade",
        "department": "Analytics",
        "manager": LOGIN_MANAGER,
        "start": -40,
        "end": 60,
        "priority": "High",
        "budget": 3_500_000,
        "description": "Upgrade the warehouse and rebuild the nightly data loads.",
        "milestone": ("Warehouse ready", 30),
        "work": (
            ("Data Source Mapping", "E10", -40, -25, 40, 100, "Medium", ()),
            ("ETL Pipeline", "E02", -24, -6, 100, 35, "Critical", ()),
            ("Warehouse Schema", "E10", -20, -3, 60, 50, "Medium", ()),
            ("Data Validation", "E10", 5, 30, 50, 0, "High", (1,)),
            ("Analytics Dashboard", "E10", 31, 60, 50, 0, "Medium", (3,)),
        ),
        "team": (("E02", 40, "ETL developer"), ("E10", 50, "Data analyst")),
        "spent": (
            (800_000, "Hardware", 30, "Storage and servers"),
            (460_000, "Personnel", 14, "Data engineering team"),
        ),
    },
    {
        "code": "DEMO-06",
        "name": "Mobile Banking Enhancement",
        "department": "Digital",
        "manager": "anjali",
        "start": -55,
        "end": 25,
        "priority": "High",
        "budget": 2_800_000,
        "description": "Improve sign-in, transfers and speed of the mobile app.",
        "milestone": ("App store release", 25),
        "work": (
            ("UI Design", "E04", -55, -40, 40, 100, "Medium", ()),
            ("Authentication Enhancement", "E03", -39, -15, 60, 100, "High", ()),
            ("Mobile API Integration", "E03", -14, 4, 80, 85, "High", ()),
            ("Performance Testing", "E03", 5, 16, 40, 0, "Medium", (2,)),
            ("App Release", "E03", 17, 25, 20, 0, "High", (3,)),
        ),
        "team": (("E03", 50, "Mobile developer"), ("E04", 40, "Designer")),
        "spent": (
            (900_000, "Personnel", 40, "Mobile team"),
            (640_000, "Software", 25, "Mobile tooling"),
            (250_000, "Testing", 8, "Device testing lab"),
        ),
    },
    {
        "code": "DEMO-07",
        "name": "Cybersecurity Compliance",
        "department": "Security",
        "manager": LOGIN_MANAGER,
        "start": -45,
        "end": 50,
        "priority": "Critical",
        "budget": 1_800_000,
        "description": "Close audit findings and prepare the compliance evidence.",
        "milestone": ("Audit ready", 45),
        "work": (
            ("Security Assessment", "E07", -45, -25, 50, 100, "High", ()),
            ("Vulnerability Remediation", "E01", -24, 7, 100, 60, "Critical", (0,)),
            ("Compliance Documentation", "E07", 8, 25, 60, 0, "Critical", (1,)),
            ("Audit Evidence", "E07", -10, 20, 40, 40, "Medium", ()),
            ("Final Compliance Review", "E07", 30, 50, 30, 0, "High", (2,)),
        ),
        "team": (("E01", 50, "Remediation lead"), ("E07", 60, "Security analyst")),
        "spent": (
            (420_000, "Consulting", 30, "Penetration test"),
            (300_000, "Software", 12, "Scanner licence"),
        ),
    },
    {
        "code": "DEMO-08",
        "name": "CRM Integration",
        "department": "Sales",
        "manager": "suresh",
        "start": -40,
        "end": 48,
        "priority": "Medium",
        "budget": 1_500_000,
        "status": "On Hold",
        "description": "Connect the CRM to billing. Waiting for the vendor API.",
        "work": (
            ("CRM API Analysis", "E08", -40, 5, 80, 62.5, "High", ()),
            ("Data Mapping", "E08", 6, 18, 40, 0, "Medium", (0,)),
            ("Integration Development", "E08", 19, 38, 50, 0, "High", (1,)),
            ("Integration Testing", "E08", 39, 48, 30, 0, "Medium", (2,)),
        ),
        "team": (("E08", 30, "Business analyst"),),
        "spent": ((270_000, "Consulting", 20, "Vendor API workshops"),),
    },
    {
        "code": "DEMO-09",
        "name": "Payment Gateway Upgrade",
        "department": "Finance",
        "manager": "kavya",
        "start": -90,
        "end": -4,
        "priority": "High",
        "budget": 2_000_000,
        "description": "Upgrade the payment gateway and renew its certification.",
        "milestone": ("Production release", -4),
        "work": (
            ("Gateway API Integration", "E03", -90, -50, 60, 100, "High", ()),
            ("Payment Testing", "E06", -49, -25, 60, 100, "High", ()),
            ("Security Testing", "E06", -24, -10, 40, 100, "Medium", ()),
            ("Production Release", "E03", -9, -4, 40, 50, "High", ()),
        ),
        # The team stays a little longer, because the project is late.
        "team": (("E03", 30, "Developer", -90, 7), ("E06", 30, "Tester", -90, 7)),
        "spent": (
            (900_000, "Personnel", 60, "Payments team"),
            (540_000, "Software", 40, "Gateway licence"),
            (400_000, "Testing", 12, "Security certification"),
        ),
    },
    {
        "code": "DEMO-10",
        "name": "Supply Chain Dashboard",
        "department": "Operations",
        "manager": LOGIN_MANAGER,
        "start": -30,
        "end": 60,
        "priority": "Medium",
        "budget": 1_000_000,
        "description": "Show stock, supplier and delivery figures in one place.",
        "work": (
            ("Data Collection", "E10", -30, -10, 40, 100, "Medium", ()),
            ("Dashboard Design", "E09", -9, 12, 50, 40, "Medium", ()),
            ("KPI Implementation", "E09", 13, 40, 60, 0, "High", ()),
            ("User Testing", "E10", 41, 60, 50, 0, "Medium", ()),
        ),
        "team": (("E09", 40, "Developer"), ("E10", 30, "Data analyst")),
        "spent": (
            (600_000, "Software", 22, "Dashboard platform"),
            (340_000, "Consulting", 14, "Supplier data onboarding"),
            (180_000, "Travel", 5, "Warehouse site visits"),
        ),
    },
    {
        "code": "DEMO-11",
        "name": "Employee Analytics Platform",
        "department": "HR",
        "manager": "suresh",
        "start": -150,
        "end": -20,
        "priority": "Low",
        "budget": 800_000,
        "status": "Completed",
        "completed": -25,
        "description": "Workforce reporting for HR leaders. Delivered and closed.",
        "work": (
            ("Data Collection", "E10", -150, -115, 40, 100, "Medium", ()),
            ("Analytics Implementation", "E10", -114, -70, 60, 100, "High", (0,)),
            ("Dashboard", "E10", -69, -40, 40, 100, "Medium", (1,)),
            ("Final Validation", "E10", -39, -25, 20, 100, "Medium", ()),
        ),
        "team": (("E10", 40, "Data analyst", -150, -25),),
        "spent": (
            (450_000, "Personnel", 120, "Analytics team"),
            (210_000, "Software", 90, "Reporting licence"),
            (100_000, "Training", 30, "Manager training"),
        ),
    },
    {
        "code": "DEMO-12",
        "name": "AI Document Processing",
        "department": "Innovation",
        "manager": "anjali",
        "start": -15,
        "end": 90,
        "priority": "Low",
        "budget": 2_200_000,
        "description": "Early study of reading supplier documents automatically.",
        "work": (
            ("Requirements", "E12", -15, -4, 40, 100, "High", ()),
            ("Document Ingestion", "E05", -3, 25, 80, 20, "Medium", ()),
            ("Processing Pipeline", "E12", 26, 65, 100, 0, "Medium", ()),
            ("Validation", "E12", 66, 90, 60, 0, "Low", ()),
        ),
        "team": (("E05", 30, "Platform engineer"), ("E12", 30, "Developer")),
        "spent": ((132_000, "Cloud Services", 6, "Trial environment"),),
    },
)


def require_local(session: Session) -> None:
    """Refuse any database that is not the local development database.

    Args:
        session: Database session.

    Raises:
        SystemExit: The database is not local.
    """
    settings = load_database_settings()
    server = session.scalar(text("SELECT host(inet_server_addr())"))
    cloud = session.scalar(
        text("SELECT count(*) FROM pg_settings WHERE name LIKE 'rds.%'")
    )
    if (
        os.getenv("IS_LOCAL") != "true"
        or settings.host not in LOCAL_HOSTS
        or server not in (None, *LOCAL_HOSTS)
        or cloud
    ):
        sys.exit("Refused: this is not the local development database.")


def has_open_access(session: Session) -> bool:
    """Check whether PostgreSQL accepts network logins without a password.

    Args:
        session: Database session of a superuser.

    Returns:
        True when an access rule trusts another machine.
    """
    rules = session.scalar(
        text(
            "SELECT count(*) FROM pg_hba_file_rules WHERE type LIKE 'host%'"
            " AND auth_method = 'trust'"
            " AND address NOT IN ('127.0.0.1', '::1', 'localhost', 'samehost')"
        )
    )
    return bool(rules)


def find(session: Session, model: type, column: object, value: str) -> object:
    """Find a record by a name, ignoring case."""
    return session.scalar(select(model).where(func.lower(column) == value.lower()))


class Seeder:
    """Adds the demo records that do not exist yet."""

    def __init__(self, session: Session) -> None:
        """Prepare the seeder.

        Args:
            session: Database session. Nothing is final until its outer
                transaction is committed.
        """
        self.session = session
        self.added: Counter = Counter()
        self.skipped: Counter = Counter()
        self.day = today()
        self.admin = session.scalars(
            select(User).where(User.role == "admin", User.is_active).order_by(User.id)
        ).first()
        if self.admin is None:
            sys.exit("Refused: create an admin account first.")
        self.departments: dict[str, int] = {}
        self.categories: dict[str, int] = {}
        self.managers: dict[str, int] = {}
        self.resources: dict[str, int] = {}

    def date(self, offset: int) -> date:
        """Return a date relative to today."""
        return self.day + timedelta(days=offset)

    def add(self, kind: str, row: object) -> object:
        """Insert a simple record."""
        self.session.add(row)
        self.session.commit()
        self.added[kind] += 1
        return row

    def run(self) -> None:
        """Add everything that is missing."""
        for name in DEPARTMENTS:
            row = find(self.session, Department, Department.name, name)
            if row is None:
                body = DepartmentRequest(name=name, description="Sample department")
                row = self.add("departments", Department(**body.model_dump()))
            else:
                self.skipped["departments"] += 1
            self.departments[name] = row.id
        for name in CATEGORIES:
            if find(self.session, ExpenseCategory, ExpenseCategory.name, name):
                self.skipped["expense categories"] += 1
            else:
                body = CategoryRequest(name=name)
                self.add("expense categories", ExpenseCategory(name=body.name))
        for row in self.session.scalars(select(ExpenseCategory)):
            self.categories[row.name.lower()] = row.id
        self.add_managers()
        for code, values in RESOURCES.items():
            self.add_resource(code, values)
        for plan in PROJECTS:
            self.add_project(plan)

    def add_managers(self) -> None:
        """Add the fictional managers. Nobody knows their random passwords."""
        for key, name in MANAGERS.items():
            email = f"{key}@{DOMAIN}"
            row = find(self.session, User, User.email, email)
            if row is None:
                body = UserCreate(
                    email=email,
                    full_name=name,
                    role="project_manager",
                    password=secrets.token_urlsafe(32),
                )
                values = body.model_dump(exclude={"password"})
                password_hash = hash_password(body.password)
                row = self.add(
                    "project managers", User(**values, password_hash=password_hash)
                )
            else:
                self.skipped["project managers"] += 1
            self.managers[key] = row.id
        login = find(self.session, User, User.email, LOGIN_MANAGER)
        usable = login is not None and login.is_active and login.role != "team_member"
        self.managers[LOGIN_MANAGER] = login.id if usable else self.admin.id

    def add_resource(self, code: str, values: tuple) -> None:
        """Add one person."""
        full_code = f"DEMO-{code}"
        row = find(self.session, Resource, Resource.employee_code, full_code)
        if row is None:
            name, department, title, skills, capacity, availability = values
            body = ResourceRequest(
                employee_code=full_code,
                full_name=name,
                email=f"{name.lower().replace(' ', '.')}@{DOMAIN}",
                department_id=self.departments[department],
                job_title=title,
                skills=[skill.strip() for skill in skills.split(",")],
                capacity_percent=capacity,
                availability=availability,
                user_id=self.free_member_login() if code == "E01" else None,
            )
            row = Resource()
            save_resource(self.session, row, body)
            self.added["resources"] += 1
        else:
            self.skipped["resources"] += 1
        self.resources[code] = row.id

    def free_member_login(self) -> int | None:
        """Return the Team Member demo login, if no resource uses it yet.

        Linking it gives that login something to see.
        """
        login = find(self.session, User, User.email, LOGIN_MEMBER)
        if login is None:
            return None
        linked = self.session.scalar(
            select(Resource.id).where(Resource.user_id == login.id)
        )
        return None if linked else login.id

    def add_project(self, plan: dict) -> None:
        """Add one project with everything inside it."""
        if find(self.session, Project, Project.code, plan["code"]):
            self.skipped["projects"] += 1
            return
        values = {
            "code": plan["code"],
            "name": plan["name"],
            "description": plan["description"],
            "department_id": self.departments[plan["department"]],
            "manager_id": self.managers[plan["manager"]],
            "start_date": self.date(plan["start"]),
            "end_date": self.date(plan["end"]),
            # Closed projects accept no work, so they are closed at the end.
            "status": "Active",
            "priority": plan["priority"],
            "planned_budget": str(plan["budget"]),
        }
        project = Project()
        save_project(self.session, self.admin, project, ProjectRequest(**values))
        self.added["projects"] += 1
        self.add_work(project, plan)
        for person, percent, role, *dates in plan["team"]:
            start, end = dates or (plan["start"], plan["end"])
            body = AssignmentRequest(
                resource_id=self.resources[person],
                project_role=role,
                allocation_percent=percent,
                start_date=self.date(start),
                end_date=self.date(end),
            )
            save_assignment(self.session, project, ProjectAssignment(), body)
            self.added["assignments"] += 1
        for amount, category, days_ago, description in plan["spent"]:
            body = ExpenseRequest(
                category_id=self.categories[category.lower()],
                amount=str(amount),
                expense_date=self.date(-days_ago),
                description=f"{description} (demo)",
            )
            row = Expense(project_id=project.id, created_by_id=project.manager_id)
            save_expense(self.session, row, body)
            self.added["expenses"] += 1
        if "status" in plan:
            values["status"] = plan["status"]
            if "completed" in plan:
                values["actual_completion_date"] = self.date(plan["completed"])
            save_project(self.session, self.admin, project, ProjectRequest(**values))

    def add_work(self, project: Project, plan: dict) -> None:
        """Add a project's milestone, deliverables and dependencies."""
        milestone = None
        if "milestone" in plan:
            name, due = plan["milestone"]
            milestone = Milestone()
            body = MilestoneRequest(name=name, due_date=self.date(due))
            save_milestone(self.session, project, milestone, body)
            self.added["milestones"] += 1
        rows = []
        last = len(plan["work"]) - 1
        for number, item in enumerate(plan["work"]):
            name, owner, start, due, hours, progress, priority, _ = item
            status = {0: "Not Started", 100: "Completed"}.get(progress, "In Progress")
            body = DeliverableRequest(
                name=name,
                description=f"{name} for {plan['name']}.",
                milestone_id=milestone.id if milestone and number == last else None,
                owner_id=self.resources[owner],
                start_date=self.date(start),
                due_date=self.date(due),
                completion_date=self.date(due) if progress == 100 else None,
                status=status,
                priority=priority,
                progress_percent=str(progress),
                estimated_hours=hours,
                actual_hours=str(round(hours * progress / 100, 1)),
            )
            row = Deliverable()
            save_deliverable(self.session, project, row, body)
            self.added["deliverables"] += 1
            rows.append(row)
        for row, item in zip(rows, plan["work"], strict=True):
            for before in item[-1]:
                add_dependency(self.session, self.admin, row, rows[before].id)
                self.added["dependencies"] += 1


def seed(*, insert: bool) -> tuple[Counter, Counter]:
    """Add the demo data in one transaction.

    Args:
        insert: Whether to keep the result. A dry run undoes everything.

    Returns:
        How many records were added and skipped, by kind.

    Raises:
        SystemExit: Inserting would not be safe.
    """
    with get_engine().connect() as connection:
        outer = connection.begin()
        try:
            with Session(
                connection, join_transaction_mode="create_savepoint"
            ) as session:
                require_local(session)
                if has_open_access(session):
                    message = "PostgreSQL accepts network logins without a password."
                    if insert:
                        sys.exit(f"Refused: {message}")
                    print(f"Warning: {message} Inserting will be refused.")
                seeder = Seeder(session)
                seeder.run()
            if insert:
                outer.commit()
        finally:
            if outer.is_active:
                outer.rollback()
    return seeder.added, seeder.skipped


def main() -> int:
    """Run the command.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description="Add fictional demo data")
    parser.add_argument("--insert", action="store_true", help="save the records")
    options = parser.parse_args()
    added, skipped = seed(insert=options.insert)
    print("Added:" if options.insert else "Dry run, nothing saved. Would add:")
    for kind, count in sorted(added.items()):
        print(f"  {kind}: {count}")
    print(f"  total: {added.total()}; already there: {skipped.total()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
