"""Auth repositories."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.auth.models import Permission, Role, User
from app.repositories.base import AbstractRepository


class UserRepository(AbstractRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_employee_id(self, employee_id: str) -> User | None:
        stmt = select(User).where(User.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: UUID) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles).selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_users(self, page: int = 1, per_page: int = 20) -> list[User]:
        return list(
            await self.list(User.is_active == True, page=page, per_page=per_page)  # noqa: E712
        )

    async def search(self, query: str, page: int = 1, per_page: int = 20) -> list[User]:
        from sqlalchemy import or_
        stmt = (
            select(User)
            .where(
                or_(
                    User.full_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                    User.employee_id.ilike(f"%{query}%"),
                )
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_direct_reports(self, manager_id: UUID) -> list[User]:
        stmt = select(User).where(User.manager_id == manager_id, User.is_active == True)  # noqa: E712
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def email_exists(self, email: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(User).where(User.email == email.lower())
        if exclude_id:
            stmt = stmt.where(User.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None


class RoleRepository(AbstractRepository[Role]):
    model = Role

    async def get_by_name(self, name: str) -> Role | None:
        stmt = (
            select(Role)
            .where(Role.name == name)
            .options(selectinload(Role.permissions))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_with_permissions(self) -> list[Role]:
        stmt = select(Role).options(selectinload(Role.permissions))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_names(self, names: list[str]) -> list[Role]:
        stmt = select(Role).where(Role.name.in_(names))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class PermissionRepository(AbstractRepository[Permission]):
    model = Permission

    async def get_by_code(self, resource: str, action: str) -> Permission | None:
        stmt = select(Permission).where(
            Permission.resource == resource,
            Permission.action == action,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_resource(self, resource: str) -> list[Permission]:
        stmt = select(Permission).where(Permission.resource == resource)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
