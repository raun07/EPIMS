"""
FastAPI dependency functions.

  get_db          — yields an AsyncSession (commits/rolls back automatically)
  get_redis       — yields a Redis client
  get_current_user — decodes JWT, validates, returns User ORM object
  get_current_active_user — same + checks is_active
  require_permission(resource, action) — RBAC guard, raises 403
  require_roles(*roles) — role-based guard

Usage in routers:
    @router.get("/purchase-orders")
    async def list_pos(
        user: User = Depends(get_current_active_user),
        _: None = Depends(require_permission("purchase_orders", "read")),
        db: AsyncSession = Depends(get_db),
    ): ...
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import (
    AccountDisabled,
    InvalidToken,
    NotFoundException,
    PermissionDenied,
)
from app.core.security import TokenData, decode_token
from app.database import get_db
from app.domain.auth.models import User

# Re-export get_db for convenience
__all__ = [
    "get_db",
    "get_redis",
    "get_current_user",
    "get_current_active_user",
    "require_permission",
    "require_roles",
    "CurrentUser",
    "DBSession",
    "RedisClient",
]

# ── Bearer token extractor ────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=True)


# ── Redis pool (module-level singleton) ───────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    yield _redis_pool


# ── Token → TokenData ─────────────────────────────────────────────────────────

async def _get_token_data(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    redis: aioredis.Redis = Depends(get_redis),
) -> TokenData:
    """
    Decode the Bearer token and check revocation list.
    Raises InvalidToken if token is blacklisted (logged-out / rotated).
    """
    token = credentials.credentials
    payload = decode_token(token, expected_type="access")
    token_data = TokenData(payload)

    # Check revocation list (logout or refresh-rotation)
    blacklisted = await redis.get(f"token:blacklist:{token_data.jti}")
    if blacklisted:
        raise InvalidToken()

    return token_data


# ── TokenData → User ORM object ───────────────────────────────────────────────

async def get_current_user(
    token_data: TokenData = Depends(_get_token_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve token subject to a User ORM instance."""
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.id == UUID(token_data.user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundException("User", token_data.user_id)
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Same as get_current_user + is_active check."""
    if not user.is_active:
        raise AccountDisabled()
    return user


# ── RBAC guards ───────────────────────────────────────────────────────────────

def require_permission(resource: str, action: str):
    """
    Returns a FastAPI dependency that checks the caller has
    the given resource:action permission.

    Superusers bypass all permission checks.
    """

    async def _check(
        token_data: TokenData = Depends(_get_token_data),
        user: User = Depends(get_current_active_user),
    ) -> None:
        if user.is_superuser:
            return
        if not token_data.has_permission(resource, action):
            raise PermissionDenied(action=action, resource=resource)

    return Depends(_check)


def require_roles(*roles: str):
    """
    Returns a FastAPI dependency that checks the caller has
    at least one of the specified roles.

    Superusers bypass all role checks.
    """

    async def _check(
        token_data: TokenData = Depends(_get_token_data),
        user: User = Depends(get_current_active_user),
    ) -> None:
        if user.is_superuser:
            return
        if not token_data.has_role(*roles):
            raise PermissionDenied(
                action=f"requires one of roles: {', '.join(roles)}"
            )

    return Depends(_check)


# ── Typed aliases for cleaner router signatures ───────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_active_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]
