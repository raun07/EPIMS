"""
Authentication & Authorization domain models.

Tables: auth_users, auth_roles, auth_permissions,
        auth_role_permissions, auth_user_roles
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Table,
    Column,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ── Junction tables (many-to-many, no ORM class needed) ──────────────────────

role_permissions = Table(
    "auth_role_permissions",
    Base.metadata,
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("auth_roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("auth_permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

user_roles = Table(
    "auth_user_roles",
    Base.metadata,
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("auth_users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("auth_roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ── Permission ────────────────────────────────────────────────────────────────

class Permission(Base):
    __tablename__ = "auth_permissions"
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_auth_permissions_resource_action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )

    @property
    def code(self) -> str:
        return f"{self.resource}:{self.action}"

    def __repr__(self) -> str:
        return f"<Permission {self.code}>"


# ── Role ──────────────────────────────────────────────────────────────────────

class Role(Base):
    __tablename__ = "auth_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )
    users: Mapped[list[User]] = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "auth_users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    employee_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    department: Mapped[str | None] = mapped_column(String(100))
    cost_center: Mapped[str | None] = mapped_column(String(20))
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )
    manager: Mapped[User | None] = relationship(
        "User", remote_side="User.id", foreign_keys=[manager_id]
    )
    direct_reports: Mapped[list[User]] = relationship(
        "User", foreign_keys=[manager_id]
    )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_role_names(self) -> list[str]:
        return [r.name for r in self.roles]

    def get_permission_codes(self) -> list[str]:
        codes: set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                codes.add(perm.code)
        return sorted(codes)

    def has_permission(self, resource: str, action: str) -> bool:
        if self.is_superuser:
            return True
        code = f"{resource}:{action}"
        return code in self.get_permission_codes()

    def has_role(self, *role_names: str) -> bool:
        if self.is_superuser:
            return True
        return bool(set(role_names) & set(self.get_role_names()))

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ── Refresh Token (stored in Redis, not DB) ───────────────────────────────────
# Refresh tokens are stored in Redis as:
#   key: "refresh:{jti}" → value: user_id, TTL = REFRESH_TOKEN_EXPIRE_DAYS
# This is handled in AuthService, not here.
