"""Warehouse and Storage Location service."""
from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ConflictException, NotFoundException
from app.core.unit_of_work import UnitOfWork
from app.domain.warehouse.models import StorageLocation, Warehouse


class WarehouseService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_warehouse(self, data: dict, created_by_id: UUID) -> Warehouse:
        existing = await self.uow.warehouses.get_by_code(data["code"])
        if existing:
            raise ConflictException(f"Warehouse code '{data['code']}' already exists")

        warehouse = await self.uow.warehouses.create(data)

        await self.uow.audit.log(
            entity_type="Warehouse",
            entity_id=warehouse.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={"code": data["code"], "name": data.get("name")},
        )

        return warehouse

    async def update_warehouse(
        self, warehouse_id: UUID, data: dict, updated_by_id: UUID
    ) -> Warehouse:
        warehouse = await self.uow.warehouses.get_or_raise(warehouse_id)
        allowed = {"name", "warehouse_type", "address", "manager_id", "is_active"}
        filtered = {k: v for k, v in data.items() if k in allowed}
        return await self.uow.warehouses.update(warehouse, filtered)

    async def get_warehouse(self, warehouse_id: UUID) -> Warehouse:
        wh = await self.uow.warehouses.get_with_locations(warehouse_id)
        if wh is None:
            raise NotFoundException("Warehouse", str(warehouse_id))
        return wh

    async def list_warehouses(self) -> list[Warehouse]:
        return await self.uow.warehouses.get_active()

    async def create_storage_location(
        self, warehouse_id: UUID, data: dict, created_by_id: UUID
    ) -> StorageLocation:
        warehouse = await self.uow.warehouses.get_or_raise(warehouse_id)
        data["warehouse_id"] = warehouse_id
        location = await self.uow.storage_locations.create(data)
        return location

    async def list_storage_locations(self, warehouse_id: UUID) -> list[StorageLocation]:
        return await self.uow.storage_locations.get_active_for_warehouse(warehouse_id)
