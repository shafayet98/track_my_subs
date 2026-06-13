"""Password hashing, JWT issuing/verification, and OAuth-token encryption."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.config import settings

# --- Passwords -------------------------------------------------------------
# bcrypt operates on at most 72 bytes; we truncate explicitly (the standard
# practice) so longer passwords don't raise.


def _pw_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), hashed.encode("utf-8"))
    except ValueError:
        return False


# --- JWT -------------------------------------------------------------------


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes or settings.jwt_expires_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) if the token is valid, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload.get("sub")


# --- OAuth state -----------------------------------------------------------
# The Gmail callback is hit by the browser (unauthenticated), so we carry the
# user id in a short-lived signed `state` JWT rather than a bearer token. The
# `purpose` claim keeps these tokens distinct from auth tokens.

_OAUTH_STATE_PURPOSE = "gmail_oauth_state"


def create_oauth_state(user_id: str, expires_minutes: int = 10) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=expires_minutes)
    payload: dict[str, Any] = {"sub": user_id, "purpose": _OAUTH_STATE_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_oauth_state(state: str) -> str | None:
    """Return the user id encoded in a valid OAuth state token, else None."""
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    if payload.get("purpose") != _OAUTH_STATE_PURPOSE:
        return None
    return payload.get("sub")


# --- OAuth-token encryption at rest ---------------------------------------


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not set")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Could not decrypt stored token") from exc
