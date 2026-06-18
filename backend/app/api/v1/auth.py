"""Auth API endpoints."""
from __future__ import annotations

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request, status

from app.core.dependencies import CurrentUser, DBSession, RedisClient, get_redis
from app.core.unit_of_work import UnitOfWork
from app.schemas.auth import (
    AssignRolesRequest,
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.schemas.common import SuccessResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: DBSession,
    redis: RedisClient,
):
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        result = await svc.login(body.email, body.password)
        await uow.commit()
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    redis: RedisClient,
):
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        result = await svc.refresh(body.refresh_token)
        await uow.commit()
    return result


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    request: Request,
    body: LogoutRequest,
    current_user: CurrentUser,
    redis: RedisClient,
):
    access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        await svc.logout(access_token, body.refresh_token)
        await uow.commit()
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    return UserResponse.from_orm_user(current_user)


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    redis: RedisClient,
):
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        await svc.change_password(
            current_user.id, body.old_password, body.new_password
        )
        await uow.commit()
    return {"success": True, "message": "Password changed successfully"}


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    body: UserCreate,
    current_user: CurrentUser,
    redis: RedisClient,
):
    """Superuser endpoint to create new users."""
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        user = await svc.register_user(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            employee_id=body.employee_id,
            role_names=body.role_names,
            department=body.department,
            cost_center=body.cost_center,
            manager_id=body.manager_id,
            created_by_id=current_user.id,
        )
        await uow.commit()
    return UserResponse.from_orm_user(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    current_user: CurrentUser,
    redis: RedisClient,
):
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        user = await svc.update_user(user_id, body.model_dump(exclude_none=True))
        await uow.commit()
    return UserResponse.from_orm_user(user)


@router.post("/users/{user_id}/roles", response_model=UserResponse)
async def assign_roles(
    user_id: UUID,
    body: AssignRolesRequest,
    current_user: CurrentUser,
    redis: RedisClient,
):
    async with UnitOfWork() as uow:
        svc = AuthService(uow, redis)
        user = await svc.assign_roles(user_id, body.role_names)
        await uow.commit()
    return UserResponse.from_orm_user(user)
