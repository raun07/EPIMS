"""
Inventory service — stock queries, transfers, manual adjustments.

Stock movements beyond GRN posting (handled in GRNService):
  - Transfer: warehouse-to-warehouse (type 301) or location-to-location (type 311)
  - QI release: quality inspection → unrestricted (type 321)
  - Manual adjustment: initial stock load (type 561) or correction (type 551)
  - Goods issue: to cost centre (type 201) or production (type 261)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from app.core.events import LowStockEvent, event_dispatcher
from app.core.exceptions import (
    DomainException,
    InsufficientStock,
    NotFoundException,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.inventory.models import (
    InventoryStock,
    MovementType,
    StockMovement,
    StockType,
)
from app.utils.number_gen import generate_movement_number


class InventoryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ── Stock queries ─────────────────────────────────────────────────────────

    async def get_stock_overview(
        self, material_id: UUID
    ) -> list[InventoryStock]:
        """Return all stock records for a material across all warehouses."""
        return await self.uow.inventory.get_all_stock_for_material(material_id)

    async def get_warehouse_stock(
        self, warehouse_id: UUID
    ) -> list[InventoryStock]:
        return await self.uow.inventory.get_all_stock_for_warehouse(warehouse_id)

    async def get_low_stock_alerts(self) -> list[dict]:
        """Return all materials below their reorder point."""
        low_stock = await self.uow.inventory.get_low_stock_items()
        alerts = []
        for stock in low_stock:
            alert = {
                "material_id": str(stock.material_id),
                "material_number": stock.material.material_number if stock.material else None,
                "warehouse_id": str(stock.warehouse_id),
                "warehouse_code": stock.warehouse.code if stock.warehouse else None,
                "current_qty": float(stock.quantity),
                "reorder_point": float(stock.material.reorder_point) if stock.material else 0,
                "deficit": float(stock.material.reorder_point - stock.quantity) if stock.material else 0,
            }
            alerts.append(alert)

            # Emit event for notification
            await event_dispatcher.emit(
                LowStockEvent(
                    material_id=str(stock.material_id),
                    material_number=stock.material.material_number if stock.material else "",
                    warehouse_id=str(stock.warehouse_id),
                    current_qty=float(stock.quantity),
                    reorder_point=float(stock.material.reorder_point) if stock.material and stock.material.reorder_point else 0,
                )
            )

        return alerts

    async def get_stock_movements(
        self,
        material_id: UUID,
        page: int = 1,
        per_page: int = 50,
    ) -> list[StockMovement]:
        return await self.uow.stock_movements.get_for_material(
            material_id, page=page, per_page=per_page
        )

    # ── Stock transfer ────────────────────────────────────────────────────────

    async def transfer_stock(
        self,
        material_id: UUID,
        quantity: Decimal,
        from_warehouse_id: UUID,
        to_warehouse_id: UUID,
        transferred_by_id: UUID,
        from_location_id: UUID | None = None,
        to_location_id: UUID | None = None,
        batch_number: str | None = None,
        reason: str | None = None,
    ) -> StockMovement:
        """
        Transfer stock between warehouses (type 301) or locations (type 311).
        Validates sufficient stock exists at source.
        """
        if from_warehouse_id == to_warehouse_id and from_location_id == to_location_id:
            raise DomainException("Source and destination cannot be the same")

        # Check source stock
        source_stock = await self.uow.inventory.get_stock(
            material_id=material_id,
            warehouse_id=from_warehouse_id,
            storage_location_id=from_location_id,
            batch_number=batch_number,
            stock_type="UNRESTRICTED",
        )

        if source_stock is None or source_stock.quantity < quantity:
            raise InsufficientStock(
                str(material_id),
                float(quantity),
                float(source_stock.quantity) if source_stock else 0,
            )

        # Deduct from source
        source_stock.quantity -= quantity
        source_stock.last_movement_date = date.today()

        # Add to destination
        dest_stock = await self.uow.inventory.get_stock(
            material_id=material_id,
            warehouse_id=to_warehouse_id,
            storage_location_id=to_location_id,
            batch_number=batch_number,
            stock_type="UNRESTRICTED",
        )

        if dest_stock is None:
            dest_stock = InventoryStock(
                material_id=material_id,
                warehouse_id=to_warehouse_id,
                storage_location_id=to_location_id,
                batch_number=batch_number,
                stock_type="UNRESTRICTED",
                quantity=Decimal("0"),
                uom_id=source_stock.uom_id,
                valuation_price=source_stock.valuation_price,
                currency=source_stock.currency,
            )
            self.uow.session.add(dest_stock)
            await self.uow.session.flush()

        dest_stock.quantity += quantity
        dest_stock.last_movement_date = date.today()
        await self.uow.session.flush()

        # Movement type: 311 if same warehouse, 301 if different
        mov_type = (
            MovementType.TRANSFER_SLOC
            if from_warehouse_id == to_warehouse_id
            else MovementType.TRANSFER_PLANT
        )

        movement_number = await generate_movement_number(self.uow.session)
        movement = StockMovement(
            movement_number=movement_number,
            movement_type=mov_type,
            movement_date=date.today(),
            material_id=material_id,
            from_warehouse_id=from_warehouse_id,
            from_location_id=from_location_id,
            to_warehouse_id=to_warehouse_id,
            to_location_id=to_location_id,
            quantity=quantity,
            uom_id=source_stock.uom_id,
            unit_price=source_stock.valuation_price,
            total_value=(quantity * source_stock.valuation_price) if source_stock.valuation_price else None,
            currency=source_stock.currency,
            batch_number=batch_number,
            reason=reason,
            posted_by=transferred_by_id,
        )
        self.uow.session.add(movement)
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="StockMovement",
            entity_id=movement.id,
            action="CREATE",
            performed_by=transferred_by_id,
            new_values={
                "movement_type": mov_type,
                "material_id": str(material_id),
                "quantity": str(quantity),
                "from_warehouse": str(from_warehouse_id),
                "to_warehouse": str(to_warehouse_id),
            },
        )

        return movement

    # ── Goods issue ───────────────────────────────────────────────────────────

    async def issue_stock(
        self,
        material_id: UUID,
        quantity: Decimal,
        warehouse_id: UUID,
        issued_by_id: UUID,
        movement_type: str = MovementType.GI_COST_CENTER,
        location_id: UUID | None = None,
        batch_number: str | None = None,
        reference_doc_type: str | None = None,
        reference_doc_id: UUID | None = None,
        reason: str | None = None,
    ) -> StockMovement:
        """Goods issue (type 201 = cost centre, 261 = production)."""
        stock = await self.uow.inventory.get_stock(
            material_id=material_id,
            warehouse_id=warehouse_id,
            storage_location_id=location_id,
            batch_number=batch_number,
            stock_type="UNRESTRICTED",
        )

        if stock is None or stock.quantity < quantity:
            raise InsufficientStock(
                str(material_id),
                float(quantity),
                float(stock.quantity) if stock else 0,
            )

        stock.quantity -= quantity
        stock.last_movement_date = date.today()
        await self.uow.session.flush()

        movement_number = await generate_movement_number(self.uow.session)
        movement = StockMovement(
            movement_number=movement_number,
            movement_type=movement_type,
            movement_date=date.today(),
            material_id=material_id,
            from_warehouse_id=warehouse_id,
            from_location_id=location_id,
            quantity=quantity,
            uom_id=stock.uom_id,
            unit_price=stock.valuation_price,
            total_value=(quantity * stock.valuation_price) if stock.valuation_price else None,
            currency=stock.currency,
            reference_doc_type=reference_doc_type,
            reference_doc_id=reference_doc_id,
            batch_number=batch_number,
            reason=reason,
            posted_by=issued_by_id,
        )
        self.uow.session.add(movement)
        await self.uow.session.flush()

        return movement

    # ── Initial stock load / manual adjustment ────────────────────────────────

    async def post_initial_stock(
        self,
        material_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        unit_price: Decimal,
        currency: str,
        posted_by_id: UUID,
        location_id: UUID | None = None,
        batch_number: str | None = None,
        uom_id: UUID | None = None,
    ) -> StockMovement:
        """
        Post initial stock (type 561) — used when first going live.
        Upserts the stock record.
        """
        stock = await self.uow.inventory.get_stock(
            material_id=material_id,
            warehouse_id=warehouse_id,
            storage_location_id=location_id,
            batch_number=batch_number,
            stock_type="UNRESTRICTED",
        )

        if stock is None:
            stock = InventoryStock(
                material_id=material_id,
                warehouse_id=warehouse_id,
                storage_location_id=location_id,
                batch_number=batch_number,
                stock_type="UNRESTRICTED",
                quantity=quantity,
                uom_id=uom_id,
                valuation_price=unit_price,
                currency=currency,
                last_movement_date=date.today(),
            )
            self.uow.session.add(stock)
        else:
            stock.quantity += quantity
            stock.last_movement_date = date.today()

        await self.uow.session.flush()

        movement_number = await generate_movement_number(self.uow.session)
        movement = StockMovement(
            movement_number=movement_number,
            movement_type=MovementType.INITIAL_STOCK,
            movement_date=date.today(),
            material_id=material_id,
            to_warehouse_id=warehouse_id,
            to_location_id=location_id,
            quantity=quantity,
            uom_id=uom_id,
            unit_price=unit_price,
            total_value=quantity * unit_price,
            currency=currency,
            batch_number=batch_number,
            posted_by=posted_by_id,
        )
        self.uow.session.add(movement)
        await self.uow.session.flush()

        return movement
