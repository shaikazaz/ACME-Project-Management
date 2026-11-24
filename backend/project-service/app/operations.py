"""Tasks for operators, run by invoking the Lambda function directly."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.cli import create_admin
from app.database import get_engine

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
