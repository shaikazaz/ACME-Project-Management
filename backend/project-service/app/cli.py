"""Command line tool to create the first admin account.

There is no default account or password. The password is typed, not passed as
an argument, so it does not appear in the shell history.
"""

import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.auth.permissions import Role
from app.database import get_engine
from app.models import User
from app.schemas.users import UserCreate


def create_admin(session: Session, email: str, name: str, password: str) -> User:
    """Create an admin account using the same rules as the API.

    Args:
        session: Database session. The account is committed.
        email: The admin's email.
        name: The admin's full name.
        password: The plain password.

    Returns:
        The new account.
    """
    body = UserCreate(email=email, full_name=name, role=Role.ADMIN, password=password)
    values = body.model_dump(exclude={"password"})
    user = User(**values, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    return user


def main() -> int:
    """Run the command.

    Returns:
        The process exit code.
    """
    parser = argparse.ArgumentParser(description="Create an admin account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    options = parser.parse_args()
    password = getpass.getpass("Password (12+ characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("The passwords do not match.", file=sys.stderr)
        return 1
    try:
        with Session(get_engine()) as session:
            user = create_admin(session, options.email, options.name, password)
            print(f"Created admin {user.email}")
    except ValidationError as exc:
        for error in exc.errors():
            print(f"{error['loc'][0]}: {error['msg']}", file=sys.stderr)
        return 1
    except IntegrityError:
        print("An account with this email already exists.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
