"""
Invoice Verification service — 3-way match engine.

3-way match: Invoice vs PO vs GRN
  ┌──────────────────────────────────────────────────────────┐
  │  For each invoice line:                                   │
  │    PO price vs Invoice price  → price variance %          │
  │    GRN qty   vs Invoice qty   → qty variance              │
  │    If both within tolerance_pct → MATCHED                 │
  │    Else if within tolerance_pct * 2 → WITHIN_TOLERANCE   │
  │    Else → FAILED (mark invoice DISPUTED)                  │
  └──────────────────────────────────────────────────────────┘

Default tolerance: 2% (configurable per invoice).
Zero-tolerance option for regulatory compliance.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.events import InvoiceCreatedEvent, InvoiceMatchedEvent, event_dispatcher
from app.core.exceptions import (
    DomainException,
    NotFoundException,
    ThreeWayMatchFailed,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.invoice.models import (
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    LineMatchFlag,
    MatchResult,
    MatchStatus,
    ThreeWayMatchResult,
)
from app.domain.procurement.models import POStatus
from app.utils.number_gen import generate_invoice_number


class InvoiceService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ── Create invoice ────────────────────────────────────────────────────────

    async def create_invoice(
        self,
        vendor_id: UUID,
        invoice_date,
        items: list[dict],
        created_by_id: UUID,
        po_id: UUID | None = None,
        vendor_invoice_number: str | None = None,
        due_date=None,
        notes: str | None = None,
        tolerance_pct: float = 2.0,
    ) -> Invoice:
        """Create a new invoice in PENDING_VERIFICATION status."""
        # Validate vendor
        vendor = await self.uow.vendors.get(vendor_id)
        if vendor is None:
            raise NotFoundException("Vendor", str(vendor_id))
        if vendor.is_blocked:
            from app.core.exceptions import VendorBlocked
            raise VendorBlocked(vendor.name)

        # Validate PO linkage
        if po_id:
            po = await self.uow.purchase_orders.get(po_id)
            if po is None:
                raise NotFoundException("PurchaseOrder", str(po_id))
            if po.vendor_id != vendor_id:
                raise DomainException(
                    "Invoice vendor does not match the PO vendor"
                )
            if po.status not in (
                POStatus.RECEIVED, POStatus.PARTIALLY_RECEIVED, POStatus.RELEASED, POStatus.SENT
            ):
                raise DomainException(
                    f"PO '{po.po_number}' must be RECEIVED or PARTIALLY_RECEIVED "
                    f"before invoicing. Current status: {po.status}"
                )

        invoice_number = await generate_invoice_number(self.uow.session)

        subtotal = Decimal("0")
        tax_total = Decimal("0")

        invoice = Invoice(
            invoice_number=invoice_number,
            vendor_invoice_number=vendor_invoice_number,
            vendor_id=vendor_id,
            po_id=po_id,
            status=InvoiceStatus.PENDING_VERIFICATION,
            invoice_date=invoice_date,
            due_date=due_date,
            currency=vendor.currency,
            subtotal=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal("0"),
            tolerance_pct=Decimal(str(tolerance_pct)),
            notes=notes,
            created_by=created_by_id,
        )
        self.uow.session.add(invoice)
        await self.uow.session.flush()

        # Build line items
        for idx, item_data in enumerate(items, start=1):
            quantity = Decimal(str(item_data["quantity"]))
            unit_price = Decimal(str(item_data["unit_price"]))
            net_value = quantity * unit_price

            inv_item = InvoiceItem(
                invoice_id=invoice.id,
                po_item_id=item_data.get("po_item_id"),
                grn_item_id=item_data.get("grn_item_id"),
                line_number=idx,
                material_id=item_data.get("material_id"),
                description=item_data.get("description"),
                quantity=quantity,
                unit_price=unit_price,
                net_value=net_value,
                match_flag=LineMatchFlag.UNMATCHED,
            )
            self.uow.session.add(inv_item)
            subtotal += net_value
            tax_total += Decimal(str(item_data.get("tax_amount", "0")))

        invoice.subtotal = subtotal
        invoice.tax_amount = tax_total
        invoice.total_amount = subtotal + tax_total
        await self.uow.session.flush()
        await self.uow.session.refresh(invoice)

        await self.uow.audit.log(
            entity_type="Invoice",
            entity_id=invoice.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={
                "invoice_number": invoice_number,
                "vendor_id": str(vendor_id),
                "total_amount": str(invoice.total_amount),
            },
        )

        await event_dispatcher.emit(
            InvoiceCreatedEvent(
                invoice_id=str(invoice.id),
                invoice_number=invoice_number,
                vendor_id=str(vendor_id),
                total_amount=float(invoice.total_amount),
                created_by_id=str(created_by_id),
            )
        )

        return invoice

    # ── 3-way match engine ────────────────────────────────────────────────────

    async def run_three_way_match(
        self, invoice_id: UUID, verified_by_id: UUID, force: bool = False
    ) -> ThreeWayMatchResult:
        """
        Run the 3-way match for an invoice.

        Algorithm:
          For each invoice line:
            1. Find matching PO line   → compare unit_price, quantity
            2. Find matching GRN line  → compare quantity_accepted
            3. Compute price_variance_pct and qty_variance_pct
            4. Flag line: MATCHED | PRICE_VARIANCE | QTY_VARIANCE | UNMATCHED

          Overall result:
            PASSED           → all lines MATCHED (0 variance)
            WITHIN_TOLERANCE → max variance ≤ tolerance_pct
            FAILED           → any line exceeds tolerance_pct
        """
        invoice = await self.uow.invoices.get_with_items(invoice_id)
        if invoice is None:
            raise NotFoundException("Invoice", str(invoice_id))

        if invoice.status != InvoiceStatus.PENDING_VERIFICATION and not force:
            raise DomainException(
                f"Invoice is already in status '{invoice.status}'. "
                "Pass force=True to re-run verification."
            )

        if not invoice.po_id:
            raise DomainException(
                "Cannot run 3-way match: invoice is not linked to a PO"
            )

        po = await self.uow.purchase_orders.get_with_items(invoice.po_id)
        if po is None:
            raise NotFoundException("PurchaseOrder", str(invoice.po_id))

        # Collect posted GRNs for this PO
        grns = await self.uow.goods_receipts.get_posted_by_po(invoice.po_id)
        grn_items_flat = []
        for grn in grns:
            for gi in (await self.uow.goods_receipts.get_with_items(grn.id)).items:
                grn_items_flat.append(gi)

        tolerance = invoice.tolerance_pct
        po_items_map = {str(item.id): item for item in po.items}
        grn_items_map = {str(gi.id): gi for gi in grn_items_flat}

        # Per-line results
        total_price_variance = Decimal("0")
        total_qty_variance = Decimal("0")
        total_value_variance = Decimal("0")
        line_results: list[str] = []
        match_notes: list[str] = []

        for inv_item in invoice.items:
            po_item = po_items_map.get(str(inv_item.po_item_id)) if inv_item.po_item_id else None
            grn_item = grn_items_map.get(str(inv_item.grn_item_id)) if inv_item.grn_item_id else None

            if po_item is None:
                inv_item.match_flag = LineMatchFlag.UNMATCHED
                match_notes.append(f"Line {inv_item.line_number}: No PO line found")
                line_results.append("UNMATCHED")
                continue

            # Price check
            price_variance_pct = Decimal("0")
            if po_item.unit_price != 0:
                price_diff = abs(inv_item.unit_price - po_item.unit_price)
                price_variance_pct = (price_diff / po_item.unit_price) * Decimal("100")

            # Qty check against GRN
            qty_variance = Decimal("0")
            if grn_item:
                qty_diff = abs(inv_item.quantity - grn_item.quantity_accepted)
                qty_variance = qty_diff
                grn_qty = grn_item.quantity_accepted
            else:
                # Fall back to PO qty if no GRN (2-way match)
                qty_diff = abs(inv_item.quantity - po_item.quantity)
                qty_variance = qty_diff
                grn_qty = po_item.quantity

            # Value variance
            expected_value = grn_qty * po_item.unit_price
            actual_value = inv_item.quantity * inv_item.unit_price
            value_variance = actual_value - expected_value

            # Accumulate
            total_price_variance += price_variance_pct
            total_qty_variance += qty_variance
            total_value_variance += abs(value_variance)

            # Tag line
            has_price_issue = price_variance_pct > tolerance
            has_qty_issue = qty_variance > 0

            if not has_price_issue and not has_qty_issue:
                inv_item.match_flag = LineMatchFlag.MATCHED
                line_results.append("MATCHED")
            elif has_price_issue and has_qty_issue:
                inv_item.match_flag = LineMatchFlag.PRICE_VARIANCE
                match_notes.append(
                    f"Line {inv_item.line_number}: price Δ {price_variance_pct:.2f}%, "
                    f"qty Δ {qty_variance}"
                )
                line_results.append("FAILED")
            elif has_price_issue:
                inv_item.match_flag = LineMatchFlag.PRICE_VARIANCE
                match_notes.append(
                    f"Line {inv_item.line_number}: price Δ {price_variance_pct:.2f}%"
                )
                line_results.append("PRICE_VARIANCE")
            else:
                inv_item.match_flag = LineMatchFlag.QTY_VARIANCE
                match_notes.append(
                    f"Line {inv_item.line_number}: qty Δ {qty_variance}"
                )
                line_results.append("QTY_VARIANCE")

            inv_item.variance_pct = price_variance_pct
            await self.uow.session.flush()

        # Overall determination
        failed_lines = [r for r in line_results if r in ("FAILED", "PRICE_VARIANCE", "QTY_VARIANCE", "UNMATCHED")]
        if not failed_lines:
            overall_result = MatchResult.PASSED
            invoice.status = InvoiceStatus.MATCHED
            invoice.match_status = MatchStatus.THREE_WAY
        elif total_price_variance / max(len(invoice.items), 1) <= tolerance:
            overall_result = MatchResult.WITHIN_TOLERANCE
            invoice.status = InvoiceStatus.MATCHED
            invoice.match_status = MatchStatus.THREE_WAY
        else:
            overall_result = MatchResult.FAILED
            invoice.status = InvoiceStatus.DISPUTED
            invoice.dispute_reason = "; ".join(match_notes)

        invoice.verified_by = verified_by_id
        invoice.verified_at = datetime.now(UTC)
        await self.uow.session.flush()

        # Save match result record
        match_record = ThreeWayMatchResult(
            invoice_id=invoice.id,
            po_id=invoice.po_id,
            grn_id=grns[0].id if grns else None,
            match_result=overall_result,
            price_variance=total_price_variance,
            qty_variance=total_qty_variance,
            value_variance=total_value_variance,
            tolerance_pct=tolerance,
            notes="; ".join(match_notes) if match_notes else None,
            checked_by=verified_by_id,
        )
        self.uow.session.add(match_record)
        await self.uow.session.flush()

        # Advance PO to INVOICED
        if overall_result != MatchResult.FAILED:
            po.status = POStatus.INVOICED
            await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="Invoice",
            entity_id=invoice.id,
            action="THREE_WAY_MATCH",
            performed_by=verified_by_id,
            new_values={
                "match_result": overall_result,
                "status": invoice.status,
                "price_variance_pct": str(total_price_variance),
            },
        )

        await event_dispatcher.emit(
            InvoiceMatchedEvent(
                invoice_id=str(invoice.id),
                invoice_number=invoice.invoice_number,
                match_result=overall_result,
                verified_by_id=str(verified_by_id),
            )
        )

        if overall_result == MatchResult.FAILED:
            raise ThreeWayMatchFailed(
                variances={
                    "price_variance_pct": str(total_price_variance),
                    "qty_variance": str(total_qty_variance),
                    "value_variance": str(total_value_variance),
                    "failed_lines": failed_lines,
                    "notes": match_notes,
                }
            )

        return match_record

    # ── Manual override ───────────────────────────────────────────────────────

    async def override_dispute(
        self,
        invoice_id: UUID,
        override_by_id: UUID,
        reason: str,
    ) -> Invoice:
        """Finance manager override to approve a disputed invoice."""
        invoice = await self.uow.invoices.get_or_raise(invoice_id)
        if invoice.status != InvoiceStatus.DISPUTED:
            raise DomainException(f"Invoice is not DISPUTED (current: {invoice.status})")

        old_status = invoice.status
        invoice.status = InvoiceStatus.APPROVED
        invoice.verified_by = override_by_id
        invoice.verified_at = datetime.now(UTC)
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="Invoice",
            entity_id=invoice.id,
            action="DISPUTE_OVERRIDE",
            performed_by=override_by_id,
            old_values={"status": old_status},
            new_values={"status": InvoiceStatus.APPROVED, "override_reason": reason},
        )

        return invoice

    async def mark_paid(self, invoice_id: UUID, paid_amount: Decimal, paid_by_id: UUID) -> Invoice:
        invoice = await self.uow.invoices.get_or_raise(invoice_id)
        if invoice.status not in (InvoiceStatus.MATCHED, InvoiceStatus.APPROVED):
            raise DomainException("Only MATCHED or APPROVED invoices can be marked paid")

        invoice.paid_amount += paid_amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID

        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="Invoice",
            entity_id=invoice.id,
            action="PAYMENT_RECORDED",
            performed_by=paid_by_id,
            new_values={"paid_amount": str(paid_amount)},
        )

        return invoice

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_invoice(self, invoice_id: UUID) -> Invoice:
        invoice = await self.uow.invoices.get_with_items(invoice_id)
        if invoice is None:
            raise NotFoundException("Invoice", str(invoice_id))
        return invoice

    async def list_invoices(
        self,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        vendor_id: UUID | None = None,
    ) -> tuple[list[Invoice], int]:
        filters = []
        if status:
            filters.append(Invoice.status == status)
        if vendor_id:
            filters.append(Invoice.vendor_id == vendor_id)

        items = await self.uow.invoices.list(
            *filters,
            order_by=Invoice.created_at.desc(),
            page=page,
            per_page=per_page,
        )
        total = await self.uow.invoices.count(*filters)
        return list(items), total
