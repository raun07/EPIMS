"""Material repositories."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.domain.material.models import Material, MaterialGroup, UnitOfMeasure
from app.repositories.base import AbstractRepository


class MaterialGroupRepository(AbstractRepository[MaterialGroup]):
    model = MaterialGroup

    async def get_root_groups(self) -> list[MaterialGroup]:
        stmt = select(MaterialGroup).where(MaterialGroup.parent_id == None)  # noqa: E711
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_code(self, code: str) -> MaterialGroup | None:
        return await self.get_by(code=code)


class MaterialRepository(AbstractRepository[Material]):
    model = Material

    async def get_by_number(self, material_number: str) -> Material | None:
        return await self.get_by(material_number=material_number)

    async def search(self, query: str, page: int = 1, per_page: int = 20) -> list[Material]:
        stmt = (
            select(Material)
            .where(
                or_(
                    Material.material_number.ilike(f"%{query}%"),
                    Material.description.ilike(f"%{query}%"),
                )
            )
            .where(Material.is_active == True)  # noqa: E712
            .options(
                selectinload(Material.material_group),
                selectinload(Material.base_uom),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self, page: int = 1, per_page: int = 20) -> list[Material]:
        return list(
            await self.list(
                Material.is_active == True,  # noqa: E712
                page=page,
                per_page=per_page,
            )
        )

    async def number_exists(self, number: str) -> bool:
        return await self.exists(material_number=number)

    async def get_by_group(self, group_id, page: int = 1, per_page: int = 20) -> list[Material]:
        return list(
            await self.list(
                Material.material_group_id == group_id,
                Material.is_active == True,  # noqa: E712
                page=page,
                per_page=per_page,
            )
        )


class UOMRepository(AbstractRepository[UnitOfMeasure]):
    model = UnitOfMeasure

    async def get_by_code(self, code: str) -> UnitOfMeasure | None:
        return await self.get_by(code=code)

    async def get_all(self) -> list[UnitOfMeasure]:
        return list(await self.list_all())
