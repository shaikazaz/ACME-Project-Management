"""Service configuration, read from environment variables."""

import os
from dataclasses import dataclass, field

SERVICE_NAME = "project-service"
API_BASE_PATH = f"/api/{SERVICE_NAME}"
MIN_JWT_SECRET_LENGTH = 32


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL connection settings."""

    host: str
    port: int
    name: str
    user: str
    password: str = field(repr=False)  # Keep the password out of logs
    require_ssl: bool = True


def load_database_settings() -> DatabaseSettings:
    """Build database settings from the variables Terraform injects.

    Returns:
        The settings. SSL is required unless IS_LOCAL is "true".
    """
    return DatabaseSettings(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        name=os.getenv("POSTGRES_NAME", "postgres"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASS", ""),
        require_ssl=os.getenv("IS_LOCAL", "false") != "true",
    )


def load_jwt_secret() -> str:
    """Return the key that signs tokens.

    Returns:
        The key from JWT_SECRET.

    Raises:
        RuntimeError: The key is missing or too short. There is no default.
    """
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters")
    return secret
