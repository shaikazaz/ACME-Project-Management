"""Tasks for operators, run by invoking the Lambda function directly."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.service import set_password
from app.auth.shared import SHARED_ACCOUNTS
from app.cli import create_admin
from app.database import get_engine
from app.demo_data import DemoDataError, add_demo_data
from app.models import User
from app.schemas.users import UserCreate

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def run_task(event: dict) -> dict:
    """Run one task.

    Args:
        event: The task's name, and its options.

    Returns:
        The result. It never contains the options, which may hold a password.
    """
    task = event["task"]
    if task == "migrate":
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        return {"ok": True, "message": "The database is up to date."}
    if task == "create_admin":
        return _create_admin(event)
    if task == "add_demo_data":
        return _add_demo_data()
    if task == "set_shared_accounts":
        return _set_shared_accounts(event)
    return {"ok": False, "message": "Unknown task."}


def _create_admin(event: dict) -> dict:
    """Create an admin account."""
    try:
        with Session(get_engine()) as session:
            create_admin(session, event["email"], event["name"], event["password"])
    except (KeyError, ValidationError):
        # The error itself would repeat the password in the logs.
        return {"ok": False, "message": "Email, name or password is not valid."}
    except IntegrityError:
        return {"ok": False, "message": "An account with this email already exists."}
    return {"ok": True, "message": "The admin account was created."}


def _set_shared_accounts(event: dict) -> dict:
    """Create the shared demo accounts, or give them new passwords."""
    try:
        with Session(get_engine()) as session:
            for email, (name, role) in SHARED_ACCOUNTS.items():
                body = UserCreate(
                    email=email,
                    full_name=name,
                    role=role,
                    password=event["passwords"][email],
                )
                user = session.scalar(
                    select(User).where(func.lower(User.email) == email)
                )
                if user is None:
                    values = body.model_dump(exclude={"password"})
                    password_hash = hash_password(body.password)
                    session.add(User(**values, password_hash=password_hash))
                else:
                    user.role, user.is_active = role, True
                    set_password(user, body.password)
            session.commit()
    except (KeyError, TypeError, ValidationError):
        return {"ok": False, "message": "A password is missing or not valid."}
    return {"ok": True, "message": "The shared demo accounts are ready."}


def _add_demo_data() -> dict:
    """Add the missing demo records in one transaction."""
    try:
        with get_engine().begin() as connection:
            added, skipped = add_demo_data(connection)
    except DemoDataError as exc:
        return {"ok": False, "message": str(exc)}
    message = f"Added {added.total()} records; {skipped.total()} were already there."
    return {"ok": True, "message": message}
