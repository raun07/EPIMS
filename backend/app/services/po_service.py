"""
Purchase Order service.

State machine:
  DRAFT → PENDING_APPROVAL → APPROVED → RELEASED → SENT
        → PARTIALLY_RECEIVED → RECEIVED → INVOICED → CLOSED

Business rules:
  - PO can be created directly or from an approved PR
  - Blocked vendors are rejected at PO creation time
  - Release triggers vendor notification (email task)
  - Auto-status advancement when all GRN items are received
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from app.core.events import POCreatedEvent, POReleasedEvent, event_dispatcher
from app.core.exceptions import (
    DomainException,
    InvalidStatusTransition,
    NotFoundException,
    VendorBlocked,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.procurement.models import (
    PO_STATUS_TRANSITIONS,
    POItem,
    POStatus,
    PRStatus,
    PurchaseOrder,
)
from app.utils.number_gen import generate_po_number


class POService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ── Creation ──────────────────────────────────────────────────────────────

    async def create_po(
        self,
        vendor_id: UUID,
        items: list[dict],
        created_by_id: UUID,
        pr_id: UUID | None = None,
        po_type: str = "STANDARD",
        delivery_date: date | None = None,
        warehouse_id: UUID | None = None,
        payment_terms: str | None = None,
        notes: str | None = None,
    ) -> PurchaseOrder:
        """Create a new PO. Validates vendor is not blocked."""
        vendor = await self.uow.vendors.get(vendor_id)
        if vendor is None:
            raise NotFoundException("Vendor", str(vendor_id))
        if vendor.is_blocked:
            raise VendorBlocked(vendor.name)

        # Validate PR linkage
        if pr_id:
            pr = await self.uow.purchase_requisitions.get(pr_id)
            if pr is None:
                raise NotFoundException("PurchaseRequisition", str(pr_id))
            if pr.status != PRStatus.APPROVED:
                raise DomainException(
                    f"PR '{pr.pr_number}' must be APPROVED before a PO can be created "
                    f"(current status: {pr.status})"
                )

        po_number = await generate_po_number(self.uow.session)

        po = PurchaseOrder(
            po_number=po_number,
            vendor_id=vendor_id,
            pr_id=pr_id,
            status=POStatus.DRAFT,
            po_type=po_type,
            order_date=date.today(),
            delivery_date=delivery_date,
            warehouse_id=warehouse_id,
            payment_terms=payment_terms or vendor.payment_terms,
            currency=vendor.currency,
            notes=notes,
            created_by=created_by_id,
        )
        self.uow.session.add(po)
        await self.uow.session.flush()

        # Build line items
        subtotal = Decimal("0")
        for idx, item_data in enumerate(items, start=1):
            unit_price = Decimal(str(item_data["unit_price"]))
            quantity = Decimal(str(item_data["quantity"]))
            discount_pct = Decimal(str(item_data.get("discount_pct", "0")))
            tax_pct = Decimal(str(item_data.get("tax_pct", "0")))

            base = quantity * unit_price
            discount_amount = base * (discount_pct / Decimal("100"))
            net_value = base - discount_amount

            po_item = POItem(
                po_id=po.id,
                pr_item_id=item_data.get("pr_item_id"),
                line_number=idx,
                material_id=item_data.get("material_id"),
                description=item_data["description"],
                quantity=quantity,
                uom_id=item_data.get("uom_id"),
                unit_price=unit_price,
                discount_pct=discount_pct,
                tax_pct=tax_pct,
                net_value=net_value,
                delivery_date=item_data.get("delivery_date"),
            )
            self.uow.session.add(po_item)
            subtotal += net_value

        # Set header totals
        po.subtotal = subtotal
        po.total_amount = subtotal  # tax calculated separately if needed
        await self.uow.session.flush()
        await self.uow.session.refresh(po)

        # Update PR status if linked
        if pr_id:
            pr = await self.uow.purchase_requisitions.get(pr_id)
            if pr:
                pr.status = PRStatus.PO_CREATED
                await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={
                "po_number": po_number,
                "vendor_id": str(vendor_id),
                "total_amount": str(po.total_amount),
            },
        )

        await event_dispatcher.emit(
            POCreatedEvent(
                po_id=str(po.id),
                po_number=po.po_number,
                vendor_id=str(vendor_id),
                total_amount=float(po.total_amount),
                currency=po.currency,
                created_by_id=str(created_by_id),
            )
        )

        return po

    # ── Workflow ──────────────────────────────────────────────────────────────

    async def submit_for_approval(
        self, po_id: UUID, submitted_by_id: UUID
    ) -> PurchaseOrder:
        po = await self.uow.purchase_orders.get_or_raise(po_id)
        if not po.can_transition_to(POStatus.PENDING_APPROVAL):
            raise InvalidStatusTransition("PurchaseOrder", po.status, POStatus.PENDING_APPROVAL)

        old_status = po.status
        po.status = POStatus.PENDING_APPROVAL
        await self.uow.session.flush()

        # Start approval workflow
        from app.services.approval_service import ApprovalService
        approval_svc = ApprovalService(self.uow)
        await approval_svc.start_workflow(
            document_type="PO",
            document_id=po.id,
            document_value=po.total_amount,
            requester_id=submitted_by_id,
        )

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="STATUS_CHANGE",
            performed_by=submitted_by_id,
            old_values={"status": old_status},
            new_values={"status": POStatus.PENDING_APPROVAL},
        )

        return po

    async def _mark_approved(self, po_id: UUID, approved_by_id: UUID) -> PurchaseOrder:
        """Called by approval engine when all approval steps pass."""
        po = await self.uow.purchase_orders.get_or_raise(po_id)
        if not po.can_transition_to(POStatus.APPROVED):
            raise InvalidStatusTransition("PurchaseOrder", po.status, POStatus.APPROVED)

        po.status = POStatus.APPROVED
        po.approved_by = approved_by_id
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="STATUS_CHANGE",
            performed_by=approved_by_id,
            old_values={"status": POStatus.PENDING_APPROVAL},
            new_values={"status": POStatus.APPROVED},
        )

        return po

    async def release_po(self, po_id: UUID, released_by_id: UUID) -> PurchaseOrder:
        """Release the PO (send to vendor). Triggers email task."""
        po = await self.uow.purchase_orders.get_with_items(po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(po_id))
        if not po.can_transition_to(POStatus.RELEASED):
            raise InvalidStatusTransition("PurchaseOrder", po.status, POStatus.RELEASED)

        old_status = po.status
        po.status = POStatus.RELEASED
        po.released_at = datetime.now(UTC)
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="STATUS_CHANGE",
            performed_by=released_by_id,
            old_values={"status": old_status},
            new_values={"status": POStatus.RELEASED},
        )

        # Trigger email to vendor (async Celery task)
        try:
            from app.tasks.email_tasks import send_po_to_vendor
            send_po_to_vendor.delay(str(po.id))
        except Exception:
            pass  # Task queue unavailable — log but don't fail the release

        await event_dispatcher.emit(
            POReleasedEvent(
                po_id=str(po.id),
                po_number=po.po_number,
                vendor_id=str(po.vendor_id),
                released_by_id=str(released_by_id),
            )
        )

        return po

    async def amend_po(
        self, po_id: UUID, amended_by_id: UUID, changes: dict
    ) -> PurchaseOrder:
        """Amend a DRAFT or APPROVED PO (not yet released)."""
        po = await self.uow.purchase_orders.get_with_items(po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(po_id))

        if po.status not in (POStatus.DRAFT, POStatus.APPROVED):
            raise DomainException(
                f"PO in status '{po.status}' cannot be amended. "
                "Only DRAFT or APPROVED POs can be modified."
            )

        allowed = {"delivery_date", "payment_terms", "notes", "internal_notes"}
        filtered = {k: v for k, v in changes.items() if k in allowed}
        old_values = {k: str(getattr(po, k)) for k in filtered}

        updated = await self.uow.purchase_orders.update(po, filtered)

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="UPDATE",
            performed_by=amended_by_id,
            old_values=old_values,
            new_values=filtered,
            changed_fields=list(filtered.keys()),
        )

        return updated

    async def cancel_po(self, po_id: UUID, cancelled_by_id: UUID) -> PurchaseOrder:
        po = await self.uow.purchase_orders.get_or_raise(po_id)
        if not po.can_transition_to(POStatus.CANCELLED):
            raise InvalidStatusTransition("PurchaseOrder", po.status, POStatus.CANCELLED)

        old_status = po.status
        po.status = POStatus.CANCELLED
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseOrder",
            entity_id=po.id,
            action="STATUS_CHANGE",
            performed_by=cancelled_by_id,
            old_values={"status": old_status},
            new_values={"status": POStatus.CANCELLED},
        )

        return po

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_po(self, po_id: UUID) -> PurchaseOrder:
        po = await self.uow.purchase_orders.get_with_items(po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(po_id))
        return po

    async def list_pos(
        self,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        vendor_id: UUID | None = None,
    ) -> tuple[list[PurchaseOrder], int]:
        filters = []
        if status:
            filters.append(PurchaseOrder.status == status)
        if vendor_id:
            filters.append(PurchaseOrder.vendor_id == vendor_id)

        items = await self.uow.purchase_orders.list(
            *filters,
            order_by=PurchaseOrder.created_at.desc(),
            page=page,
            per_page=per_page,
        )
        total = await self.uow.purchase_orders.count(*filters)
        return list(items), total
