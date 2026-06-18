"""
Security utilities: JWT encoding/decoding and bcrypt password hashing.
Access tokens (short-lived) + Refresh tokens (long-lived, rotated on use).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import InvalidToken, TokenExpired

# ── Password hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ── Token payloads ────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    subject: str,
    user_id: str,
    roles: list[str],
    permissions: list[str],
    extra: dict[str, Any] | None = None,
) -> str:
    """
    Create a short-lived JWT access token.

    Payload keys follow JWT standard claims + EPIMS custom claims:
      sub  — user identifier (email)
      uid  — UUID of the user row
      rls  — list of role names
      pms  — list of 'resource:action' permission strings
      jti  — unique token ID (used for revocation)
      iat  — issued at
      exp  — expiry
      type — 'access'
    """
    now = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "rls": roles,
        "pms": permissions,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str, user_id: str) -> str:
    """
    Create a long-lived refresh token.
    Stored token_id (jti) in Redis when issued; deleted on use/revoke.
    """
    now = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "uid": user_id,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises InvalidToken on bad signature/claims, TokenExpired on expiry.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError as exc:
        # jose raises ExpiredSignatureError (subclass of JWTError)
        if "expired" in str(exc).lower():
            raise TokenExpired() from exc
        raise InvalidToken() from exc

    token_type = payload.get("type")
    if token_type != expected_type:
        raise InvalidToken()

    return payload


def get_token_jti(token: str) -> str | None:
    """Extract jti from a token without full validation (used for revocation)."""
    try:
        payload = jwt.get_unverified_claims(token)
        return payload.get("jti")
    except Exception:
        return None


# ── Token data extraction helpers ─────────────────────────────────────────────

class TokenData:
    """Thin wrapper around the decoded JWT payload for type safety."""

    __slots__ = ("subject", "user_id", "roles", "permissions", "jti")

    def __init__(self, payload: dict[str, Any]) -> None:
        self.subject: str = payload["sub"]
        self.user_id: str = payload["uid"]
        self.roles: list[str] = payload.get("rls", [])
        self.permissions: list[str] = payload.get("pms", [])
        self.jti: str = payload.get("jti", "")

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if this token carries a specific permission."""
        return f"{resource}:{action}" in self.permissions

    def has_role(self, *roles: str) -> bool:
        """Check if token carries any of the given roles."""
        return bool(set(roles) & set(self.roles))
