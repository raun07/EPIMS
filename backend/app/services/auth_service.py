"""
Authentication & Authorization service.

Responsibilities:
  - Login: verify credentials, build token pair, store refresh jti in Redis
  - Refresh: rotate refresh token
  - Logout: blacklist access jti, delete refresh jti
  - Register user, assign roles
  - Permission resolution for token building
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import redis.asyncio as aioredis

from app.config import settings
from app.core.exceptions import (
    AccountDisabled,
    ConflictException,
    InvalidCredentials,
    InvalidToken,
    NotFoundException,
)
from app.core.security import (
    TokenData,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_jti,
    hash_password,
    verify_password,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.auth.models import User


class AuthService:
    def __init__(self, uow: UnitOfWork, redis: aioredis.Redis) -> None:
        self.uow = uow
        self.redis = redis

    async def login(self, email: str, password: str) -> dict:
        """
        Authenticate user. Returns access + refresh token pair.
        Stores refresh token jti in Redis for rotation validation.
        """
        user = await self.uow.users.get_by_email(email.lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentials()
        if not user.is_active:
            raise AccountDisabled()

        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> dict:
        """
        Rotate refresh token: validate old token, issue new pair, revoke old jti.
        """
        payload = decode_token(refresh_token, expected_type="refresh")
        jti = payload.get("jti", "")
        user_id = payload.get("uid")

        # Verify jti is in Redis (not already rotated or revoked)
        stored = await self.redis.get(f"refresh:{jti}")
        if not stored:
            raise InvalidToken()

        user = await self.uow.users.get_with_roles(UUID(user_id))
        if user is None or not user.is_active:
            raise AccountDisabled()

        # Revoke old refresh token
        await self.redis.delete(f"refresh:{jti}")

        return await self._issue_tokens(user)

    async def logout(self, access_token: str, refresh_token: str | None = None) -> None:
        """
        Blacklist the access token jti and revoke the refresh token.
        """
        access_jti = get_token_jti(access_token)
        if access_jti:
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60 + 60
            await self.redis.setex(f"token:blacklist:{access_jti}", ttl, "1")

        if refresh_token:
            refresh_jti = get_token_jti(refresh_token)
            if refresh_jti:
                await self.redis.delete(f"refresh:{refresh_jti}")

    async def register_user(
        self,
        email: str,
        password: str,
        full_name: str,
        employee_id: str,
        role_names: list[str] | None = None,
        department: str | None = None,
        cost_center: str | None = None,
        manager_id: UUID | None = None,
        created_by_id: UUID | None = None,
    ) -> User:
        """Create a new user account and assign roles."""
        # Uniqueness checks
        if await self.uow.users.email_exists(email):
            raise ConflictException(f"Email '{email}' is already registered")

        if await self.uow.users.get_by_employee_id(employee_id):
            raise ConflictException(f"Employee ID '{employee_id}' is already in use")

        user = await self.uow.users.create(
            {
                "email": email.lower(),
                "hashed_password": hash_password(password),
                "full_name": full_name,
                "employee_id": employee_id,
                "department": department,
                "cost_center": cost_center,
                "manager_id": manager_id,
            }
        )

        if role_names:
            roles = await self.uow.roles.get_by_names(role_names)
            user.roles = roles
            await self.uow.session.flush()

        # Emit domain event
        from app.core.events import UserCreatedEvent, event_dispatcher
        await event_dispatcher.emit(
            UserCreatedEvent(
                user_id=str(user.id),
                email=user.email,
                full_name=user.full_name,
                created_by_id=str(created_by_id) if created_by_id else "",
            )
        )

        return user

    async def change_password(
        self, user_id: UUID, old_password: str, new_password: str
    ) -> None:
        user = await self.uow.users.get_or_raise(user_id)
        if not verify_password(old_password, user.hashed_password):
            raise InvalidCredentials()
        user.hashed_password = hash_password(new_password)
        await self.uow.users.save(user)

    async def assign_roles(self, user_id: UUID, role_names: list[str]) -> User:
        user = await self.uow.users.get_with_roles(user_id)
        if user is None:
            raise NotFoundException("User", str(user_id))
        roles = await self.uow.roles.get_by_names(role_names)
        user.roles = roles
        await self.uow.session.flush()
        await self.uow.session.refresh(user)
        return user

    async def update_user(self, user_id: UUID, data: dict) -> User:
        user = await self.uow.users.get_or_raise(user_id)
        allowed_fields = {
            "full_name", "department", "cost_center",
            "manager_id", "is_active",
        }
        filtered = {k: v for k, v in data.items() if k in allowed_fields}
        return await self.uow.users.update(user, filtered)

    async def get_me(self, user_id: UUID) -> User:
        user = await self.uow.users.get_with_roles(user_id)
        if user is None:
            raise NotFoundException("User", str(user_id))
        return user

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _issue_tokens(self, user: User) -> dict:
        """Create access + refresh token pair and persist refresh jti."""
        roles = user.get_role_names()
        permissions = user.get_permission_codes()

        access_token = create_access_token(
            subject=user.email,
            user_id=str(user.id),
            roles=roles,
            permissions=permissions,
        )
        refresh_token = create_refresh_token(
            subject=user.email,
            user_id=str(user.id),
        )

        # Persist refresh jti in Redis
        refresh_jti = get_token_jti(refresh_token)
        if refresh_jti:
            await self.redis.setex(
                f"refresh:{refresh_jti}",
                settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
                str(user.id),
            )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "roles": roles,
                "permissions": permissions,
                "is_superuser": user.is_superuser,
            },
        }
