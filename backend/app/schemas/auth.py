"""Auth request/response schemas."""
from __future__ import annotations

from uuid import UUID

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema


class LoginRequest(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseSchema):
    refresh_token: str


class LogoutRequest(BaseSchema):
    refresh_token: str | None = None


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserBrief"


class UserBrief(BaseSchema):
    id: UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]
    is_superuser: bool


class UserCreate(BaseSchema):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    employee_id: str = Field(min_length=2)
    department: str | None = None
    cost_center: str | None = None
    manager_id: UUID | None = None
    role_names: list[str] = []

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseSchema):
    full_name: str | None = None
    department: str | None = None
    cost_center: str | None = None
    manager_id: UUID | None = None
    is_active: bool | None = None


class UserResponse(BaseSchema):
    id: UUID
    employee_id: str
    email: str
    full_name: str
    department: str | None
    cost_center: str | None
    manager_id: UUID | None
    is_active: bool
    is_superuser: bool
    roles: list[str] = []

    @classmethod
    def from_orm_user(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            employee_id=user.employee_id,
            email=user.email,
            full_name=user.full_name,
            department=user.department,
            cost_center=user.cost_center,
            manager_id=user.manager_id,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            roles=user.get_role_names(),
        )


class ChangePasswordRequest(BaseSchema):
    old_password: str
    new_password: str = Field(min_length=8)


class AssignRolesRequest(BaseSchema):
    role_names: list[str]
