"""Inventory repositories."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from app.domain.inventory.models import InventoryStock, StockMovement
from app.repositories.base import AbstractRepository


class InventoryRepository(AbstractRepository[InventoryStock]):
    model = InventoryStock

    async def get_stock(
        self,
        material_id: UUID,
        warehouse_id: UUID,
        storage_location_id: UUID | None = None,
        batch_number: str | None = None,
        stock_type: str = "UNRESTRICTED",
    ) -> InventoryStock | None:
        """Fetch exact stock record for given combination."""
        filters = [
            InventoryStock.material_id == material_id,
            InventoryStock.warehouse_id == warehouse_id,
            InventoryStock.stock_type == stock_type,
        ]
        if storage_location_id is not None:
            filters.append(InventoryStock.storage_location_id == storage_location_id)
        else:
            filters.append(InventoryStock.storage_location_id == None)  # noqa: E711
        if batch_number is not None:
            filters.append(InventoryStock.batch_number == batch_number)
        else:
            filters.append(InventoryStock.batch_number == None)  # noqa: E711

        stmt = select(InventoryStock).where(and_(*filters))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_stock_for_material(self, material_id: UUID) -> list[InventoryStock]:
        stmt = (
            select(InventoryStock)
            .where(InventoryStock.material_id == material_id)
            .options(
                selectinload(InventoryStock.warehouse),
                selectinload(InventoryStock.storage_location),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_all_stock_for_warehouse(self, warehouse_id: UUID) -> list[InventoryStock]:
        stmt = (
            select(InventoryStock)
            .where(InventoryStock.warehouse_id == warehouse_id)
            .options(selectinload(InventoryStock.material))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_low_stock_items(self) -> list[InventoryStock]:
        """Return stock records where quantity is below reorder point."""
        from app.domain.material.models import Material
        from sqlalchemy import join

        stmt = (
            select(InventoryStock)
            .join(Material, InventoryStock.material_id == Material.id)
            .where(
                InventoryStock.stock_type == "UNRESTRICTED",
                Material.reorder_point != None,  # noqa: E711
                InventoryStock.quantity <= Material.reorder_point,
            )
            .options(selectinload(InventoryStock.material), selectinload(InventoryStock.warehouse))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class StockMovementRepository(AbstractRepository[StockMovement]):
    model = StockMovement

    async def get_by_number(self, movement_number: str) -> StockMovement | None:
        return await self.get_by(movement_number=movement_number)

    async def get_for_material(
        self,
        material_id: UUID,
        page: int = 1,
        per_page: int = 50,
    ) -> list[StockMovement]:
        return list(
            await self.list(
                StockMovement.material_id == material_id,
                order_by=StockMovement.created_at.desc(),
                page=page,
                per_page=per_page,
            )
        )

    async def get_for_reference(
        self, doc_type: str, doc_id: UUID
    ) -> list[StockMovement]:
        return list(
            await self.list_all(
                StockMovement.reference_doc_type == doc_type,
                StockMovement.reference_doc_id == doc_id,
                order_by=StockMovement.created_at,
            )
        )
