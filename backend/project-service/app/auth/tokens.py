"""Signed access and refresh tokens (JWT)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.config import SERVICE_NAME, load_jwt_secret

ALGORITHM = "HS256"
LIFETIMES = {"access": timedelta(minutes=30), "refresh": timedelta(hours=8)}

Purpose = Literal["access", "refresh"]


class TokenError(Exception):
    """The token cannot be accepted."""


class TokenExpiredError(TokenError):
    """The token was valid but has expired."""


@dataclass(frozen=True)
class TokenClaims:
    """What a verified token says."""

    user_id: int
    version: int


def create_token(user_id: int, version: int, purpose: Purpose) -> str:
    """Create a signed token.

    Args:
        user_id: The account the token belongs to.
        version: The account's current token version.
        purpose: "access" for API calls, "refresh" to get a new access token.

    Returns:
        The encoded token. It contains no role, so roles are always read fresh.
    """
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "ver": version,
        "use": purpose,
        "iss": SERVICE_NAME,
        "aud": SERVICE_NAME,
        "iat": now,
        "exp": now + LIFETIMES[purpose],
    }
    return jwt.encode(claims, load_jwt_secret(), algorithm=ALGORITHM)


def read_token(token: str, purpose: Purpose) -> TokenClaims:
    """Verify a token's signature, expiry and purpose.

    Args:
        token: The encoded token.
        purpose: The purpose the token must have.

    Returns:
        The verified claims.

    Raises:
        TokenExpiredError: The token has expired.
        TokenError: The token is invalid for any other reason.
    """
    try:
        claims = jwt.decode(
            token,
            load_jwt_secret(),
            algorithms=[ALGORITHM],
            issuer=SERVICE_NAME,
            audience=SERVICE_NAME,
            options={"require": ["sub", "ver", "use", "iss", "aud", "iat", "exp"]},
        )
        if claims["use"] != purpose:
            raise TokenError("Wrong token type")
        return TokenClaims(user_id=int(claims["sub"]), version=int(claims["ver"]))
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Token expired") from exc
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise TokenError("Invalid token") from exc
