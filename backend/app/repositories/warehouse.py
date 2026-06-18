"""Warehouse repositories."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.warehouse.models import StorageLocation, Warehouse
from app.repositories.base import AbstractRepository


class WarehouseRepository(AbstractRepository[Warehouse]):
    model = Warehouse

    async def get_by_code(self, code: str) -> Warehouse | None:
        return await self.get_by(code=code)

    async def get_active(self) -> list[Warehouse]:
        return list(await self.list_all(Warehouse.is_active == True))  # noqa: E712

    async def get_with_locations(self, warehouse_id) -> Warehouse | None:
        stmt = (
            select(Warehouse)
            .where(Warehouse.id == warehouse_id)
            .options(selectinload(Warehouse.storage_locations))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class StorageLocationRepository(AbstractRepository[StorageLocation]):
    model = StorageLocation

    async def get_by_warehouse_and_code(
        self, warehouse_id, code: str
    ) -> StorageLocation | None:
        stmt = select(StorageLocation).where(
            StorageLocation.warehouse_id == warehouse_id,
            StorageLocation.code == code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_for_warehouse(self, warehouse_id) -> list[StorageLocation]:
        return list(
            await self.list_all(
                StorageLocation.warehouse_id == warehouse_id,
                StorageLocation.is_active == True,  # noqa: E712
                order_by=StorageLocation.code,
            )
        )
