"""
Goods Receipt Note (GRN) service.

Core flow:
  1. create_grn()  — draft GRN linked to a PO
  2. post_grn()    — post the GRN:
       a. For each accepted line → upsert InventoryStock
       b. Create StockMovement (type 101 = GR vs PO)
       c. Update POItem.qty_received
       d. Update PO status (PARTIALLY_RECEIVED or RECEIVED)
       e. Emit GRNPostedEvent
  3. reverse_grn() — reverse a posted GRN (StockMovement type 122)

Posting is idempotent for accepted qty — rejections create no stock.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from app.core.events import GRNPostedEvent, event_dispatcher
from app.core.exceptions import (
    DomainException,
    InsufficientStock,
    InvalidStatusTransition,
    NotFoundException,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.inventory.models import InventoryStock, MovementType, StockMovement
from app.domain.procurement.models import (
    GRNStatus,
    GoodsReceipt,
    GRNItem,
    POStatus,
    PurchaseOrder,
)
from app.utils.number_gen import generate_grn_number, generate_movement_number


class GRNService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ── Create draft GRN ──────────────────────────────────────────────────────

    async def create_grn(
        self,
        po_id: UUID,
        warehouse_id: UUID,
        items: list[dict],
        created_by_id: UUID,
        receipt_date: date | None = None,
        delivery_note: str | None = None,
        vehicle_number: str | None = None,
        driver_name: str | None = None,
        notes: str | None = None,
    ) -> GoodsReceipt:
        """Create a draft GRN for a PO. Does NOT post stock yet."""
        po = await self.uow.purchase_orders.get_with_items(po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(po_id))

        if po.status not in (
            POStatus.RELEASED, POStatus.SENT, POStatus.PARTIALLY_RECEIVED
        ):
            raise DomainException(
                f"PO '{po.po_number}' is in status '{po.status}'. "
                "GRN can only be created for RELEASED, SENT, or PARTIALLY_RECEIVED orders."
            )

        warehouse = await self.uow.warehouses.get(warehouse_id)
        if warehouse is None:
            raise NotFoundException("Warehouse", str(warehouse_id))

        grn_number = await generate_grn_number(self.uow.session)

        grn = GoodsReceipt(
            grn_number=grn_number,
            po_id=po_id,
            vendor_id=po.vendor_id,
            warehouse_id=warehouse_id,
            status=GRNStatus.DRAFT,
            receipt_date=receipt_date or date.today(),
            delivery_note=delivery_note,
            vehicle_number=vehicle_number,
            driver_name=driver_name,
            currency=po.currency,
            notes=notes,
        )
        self.uow.session.add(grn)
        await self.uow.session.flush()

        # Build line items
        total_value = Decimal("0")
        po_items_map = {str(item.id): item for item in po.items}

        for idx, item_data in enumerate(items, start=1):
            po_item_id = item_data.get("po_item_id")
            po_item = po_items_map.get(str(po_item_id)) if po_item_id else None

            quantity_delivered = Decimal(str(item_data["quantity_delivered"]))
            quantity_accepted = Decimal(str(item_data.get("quantity_accepted", item_data["quantity_delivered"])))
            quantity_rejected = quantity_delivered - quantity_accepted

            unit_price = (
                Decimal(str(item_data["unit_price"]))
                if item_data.get("unit_price")
                else (po_item.unit_price if po_item else Decimal("0"))
            )
            net_value = quantity_accepted * unit_price

            grn_item = GRNItem(
                grn_id=grn.id,
                po_item_id=po_item_id,
                line_number=idx,
                material_id=(po_item.material_id if po_item else item_data.get("material_id")),
                quantity_delivered=quantity_delivered,
                quantity_accepted=quantity_accepted,
                quantity_rejected=quantity_rejected,
                uom_id=(po_item.uom_id if po_item else item_data.get("uom_id")),
                unit_price=unit_price,
                net_value=net_value,
                storage_location_id=item_data.get("storage_location_id"),
                batch_number=item_data.get("batch_number"),
                expiry_date=item_data.get("expiry_date"),
                inspection_note=item_data.get("inspection_note"),
                rejection_reason=item_data.get("rejection_reason"),
            )
            self.uow.session.add(grn_item)
            total_value += net_value

        grn.total_value = total_value
        await self.uow.session.flush()
        await self.uow.session.refresh(grn)

        await self.uow.audit.log(
            entity_type="GoodsReceipt",
            entity_id=grn.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={"grn_number": grn_number, "po_id": str(po_id)},
        )

        return grn

    # ── Post GRN (stock movements) ────────────────────────────────────────────

    async def post_grn(self, grn_id: UUID, posted_by_id: UUID) -> GoodsReceipt:
        """
        Post a draft GRN:
          1. For each accepted GRN line → upsert InventoryStock
          2. Create StockMovement document (type 101)
          3. Update POItem.qty_received
          4. Advance PO status
          5. Emit GRNPostedEvent
        """
        grn = await self.uow.goods_receipts.get_with_items(grn_id)
        if grn is None:
            raise NotFoundException("GoodsReceipt", str(grn_id))

        if grn.status != GRNStatus.DRAFT:
            raise DomainException(f"GRN '{grn.grn_number}' is already {grn.status}")

        po = await self.uow.purchase_orders.get_with_items(grn.po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(grn.po_id))

        movement_number = await generate_movement_number(self.uow.session)

        # Process each GRN line
        for grn_item in grn.items:
            if grn_item.quantity_accepted <= 0:
                continue  # Skip fully rejected lines

            # ── 1. Upsert inventory stock ──────────────────────────────────
            stock = await self.uow.inventory.get_stock(
                material_id=grn_item.material_id,
                warehouse_id=grn.warehouse_id,
                storage_location_id=grn_item.storage_location_id,
                batch_number=grn_item.batch_number,
                stock_type="UNRESTRICTED",
            )

            if stock is None:
                # First receipt for this combination — create new stock record
                from app.domain.material.models import Material
                material = await self.uow.session.get(Material, grn_item.material_id)
                stock = InventoryStock(
                    material_id=grn_item.material_id,
                    warehouse_id=grn.warehouse_id,
                    storage_location_id=grn_item.storage_location_id,
                    batch_number=grn_item.batch_number,
                    stock_type="UNRESTRICTED",
                    quantity=Decimal("0"),
                    uom_id=grn_item.uom_id,
                    valuation_price=grn_item.unit_price,
                    currency=grn.currency,
                )
                self.uow.session.add(stock)
                await self.uow.session.flush()
            else:
                # Update moving average price
                if grn_item.unit_price and stock.valuation_price:
                    total_old = stock.quantity * stock.valuation_price
                    total_new = grn_item.quantity_accepted * grn_item.unit_price
                    new_qty = stock.quantity + grn_item.quantity_accepted
                    if new_qty > 0:
                        stock.valuation_price = (total_old + total_new) / new_qty

            # Add accepted quantity
            stock.quantity += grn_item.quantity_accepted
            stock.last_movement_date = grn.receipt_date
            await self.uow.session.flush()

            # ── 2. Create stock movement (immutable ledger entry) ──────────
            movement = StockMovement(
                movement_number=movement_number,
                movement_type=MovementType.GR_VS_PO,
                movement_date=grn.receipt_date,
                material_id=grn_item.material_id,
                to_warehouse_id=grn.warehouse_id,
                to_location_id=grn_item.storage_location_id,
                quantity=grn_item.quantity_accepted,
                uom_id=grn_item.uom_id,
                unit_price=grn_item.unit_price,
                total_value=grn_item.net_value,
                currency=grn.currency,
                reference_doc_type="GRN",
                reference_doc_id=grn.id,
                batch_number=grn_item.batch_number,
                posted_by=posted_by_id,
            )
            self.uow.session.add(movement)

            # Each line gets its own movement number in production
            # (re-generate only if multiple items — simplified here)
            movement_number = await generate_movement_number(self.uow.session)

            # ── 3. Update POItem.qty_received ──────────────────────────────
            if grn_item.po_item_id:
                po_item = next(
                    (i for i in po.items if i.id == grn_item.po_item_id), None
                )
                if po_item:
                    po_item.qty_received += grn_item.quantity_accepted
                    # Mark PO item as fully received if applicable
                    if po_item.qty_received >= po_item.quantity:
                        po_item.status = "CLOSED"
                    await self.uow.session.flush()

        # ── 4. Mark GRN as posted ─────────────────────────────────────────
        grn.status = GRNStatus.POSTED
        grn.posted_by = posted_by_id
        grn.posted_at = datetime.now(UTC)
        await self.uow.session.flush()

        # ── 5. Advance PO status ──────────────────────────────────────────
        await self._update_po_receipt_status(po)

        await self.uow.audit.log(
            entity_type="GoodsReceipt",
            entity_id=grn.id,
            action="STATUS_CHANGE",
            performed_by=posted_by_id,
            old_values={"status": GRNStatus.DRAFT},
            new_values={"status": GRNStatus.POSTED},
        )

        await event_dispatcher.emit(
            GRNPostedEvent(
                grn_id=str(grn.id),
                grn_number=grn.grn_number,
                po_id=str(grn.po_id),
                warehouse_id=str(grn.warehouse_id),
                posted_by_id=str(posted_by_id),
                total_value=float(grn.total_value),
            )
        )

        return grn

    # ── Reverse GRN ───────────────────────────────────────────────────────────

    async def reverse_grn(self, grn_id: UUID, reversed_by_id: UUID, reason: str) -> GoodsReceipt:
        """
        Reverse a posted GRN:
          1. Deduct stock (StockMovement type 122 = return to vendor)
          2. Update POItem.qty_received
          3. Mark GRN as REVERSED
        """
        grn = await self.uow.goods_receipts.get_with_items(grn_id)
        if grn is None:
            raise NotFoundException("GoodsReceipt", str(grn_id))

        if grn.status != GRNStatus.POSTED:
            raise DomainException(f"Only POSTED GRNs can be reversed. Current: {grn.status}")

        po = await self.uow.purchase_orders.get_with_items(grn.po_id)

        for grn_item in grn.items:
            if grn_item.quantity_accepted <= 0:
                continue

            stock = await self.uow.inventory.get_stock(
                material_id=grn_item.material_id,
                warehouse_id=grn.warehouse_id,
                storage_location_id=grn_item.storage_location_id,
                batch_number=grn_item.batch_number,
                stock_type="UNRESTRICTED",
            )

            if stock is None or stock.quantity < grn_item.quantity_accepted:
                raise InsufficientStock(
                    str(grn_item.material_id),
                    float(grn_item.quantity_accepted),
                    float(stock.quantity) if stock else 0,
                )

            # Deduct stock
            stock.quantity -= grn_item.quantity_accepted
            await self.uow.session.flush()

            # Reversal movement (type 122)
            movement_number = await generate_movement_number(self.uow.session)
            reversal = StockMovement(
                movement_number=movement_number,
                movement_type=MovementType.GR_RETURN,
                movement_date=date.today(),
                material_id=grn_item.material_id,
                from_warehouse_id=grn.warehouse_id,
                from_location_id=grn_item.storage_location_id,
                quantity=grn_item.quantity_accepted,
                uom_id=grn_item.uom_id,
                unit_price=grn_item.unit_price,
                total_value=grn_item.net_value,
                currency=grn.currency,
                reference_doc_type="GRN_REVERSAL",
                reference_doc_id=grn.id,
                batch_number=grn_item.batch_number,
                reason=reason,
                posted_by=reversed_by_id,
            )
            self.uow.session.add(reversal)

            # Update PO item qty
            if grn_item.po_item_id and po:
                po_item = next((i for i in po.items if i.id == grn_item.po_item_id), None)
                if po_item:
                    po_item.qty_received -= grn_item.quantity_accepted
                    po_item.status = "OPEN"
                    await self.uow.session.flush()

        grn.status = GRNStatus.REVERSED
        await self.uow.session.flush()

        if po:
            await self._update_po_receipt_status(po)

        await self.uow.audit.log(
            entity_type="GoodsReceipt",
            entity_id=grn.id,
            action="STATUS_CHANGE",
            performed_by=reversed_by_id,
            old_values={"status": GRNStatus.POSTED},
            new_values={"status": GRNStatus.REVERSED, "reason": reason},
        )

        return grn

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_grn(self, grn_id: UUID) -> GoodsReceipt:
        grn = await self.uow.goods_receipts.get_with_items(grn_id)
        if grn is None:
            raise NotFoundException("GoodsReceipt", str(grn_id))
        return grn

    async def list_grns(
        self,
        po_id: UUID | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[GoodsReceipt], int]:
        filters = []
        if po_id:
            filters.append(GoodsReceipt.po_id == po_id)

        items = await self.uow.goods_receipts.list(
            *filters,
            order_by=GoodsReceipt.created_at.desc(),
            page=page,
            per_page=per_page,
        )
        total = await self.uow.goods_receipts.count(*filters)
        return list(items), total

    # ── Internals ─────────────────────────────────────────────────────────────

    async def _update_po_receipt_status(self, po: PurchaseOrder) -> None:
        """Advance PO to PARTIALLY_RECEIVED or RECEIVED based on line completion."""
        po_items = po.items
        if not po_items:
            return

        total_qty = sum(i.quantity for i in po_items)
        total_received = sum(i.qty_received for i in po_items)

        if total_received >= total_qty:
            po.status = POStatus.RECEIVED
        elif total_received > 0:
            po.status = POStatus.PARTIALLY_RECEIVED

        await self.uow.session.flush()
