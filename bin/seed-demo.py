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
The data itself is in backend/project-service/app/demo_data.py.
"""

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "project-service"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import load_database_settings  # noqa: E402
from app.database import get_engine  # noqa: E402
from app.demo_data import DemoDataError, add_demo_data  # noqa: E402

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


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
            added, skipped = add_demo_data(connection)
            if insert:
                outer.commit()
        finally:
            if outer.is_active:
                outer.rollback()
    return added, skipped


def main() -> int:
    """Run the command.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description="Add fictional demo data")
    parser.add_argument("--insert", action="store_true", help="save the records")
    options = parser.parse_args()
    try:
        added, skipped = seed(insert=options.insert)
    except DemoDataError as exc:
        sys.exit(f"Refused: {exc}")
    print("Added:" if options.insert else "Dry run, nothing saved. Would add:")
    for kind, count in sorted(added.items()):
        print(f"  {kind}: {count}")
    print(f"  total: {added.total()}; already there: {skipped.total()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
