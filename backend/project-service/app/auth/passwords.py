"""Password hashing with scrypt, from the Python standard library."""

import base64
import hashlib
import hmac
import os

# OWASP-recommended settings that fit a small Lambda (16 MB per hash).
COST, BLOCK_SIZE, PARALLELISM = 2**14, 8, 5
SALT_BYTES, KEY_BYTES = 16, 32


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    """Run scrypt with the given settings."""
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES)


def hash_password(password: str) -> str:
    """Hash a password with a new random salt.

    Args:
        password: The plain password, which is never stored.

    Returns:
        Text holding the settings, salt and hash.
    """
    salt = os.urandom(SALT_BYTES)
    key = _derive(password, salt, COST, BLOCK_SIZE, PARALLELISM)
    encoded = [base64.b64encode(part).decode() for part in (salt, key)]
    return "$".join(["scrypt", str(COST), str(BLOCK_SIZE), str(PARALLELISM), *encoded])


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash in constant time.

    Args:
        password: The password to check.
        stored: The result of hash_password.

    Returns:
        True when the password matches.
    """
    try:
        scheme, n, r, p, salt, key = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(key)
        actual = _derive(password, base64.b64decode(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


# Checked when an account does not exist, so response time reveals nothing.
DUMMY_HASH = hash_password(os.urandom(16).hex())
