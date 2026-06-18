"""Invoice repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.domain.invoice.models import Invoice, InvoiceItem, ThreeWayMatchResult
from app.repositories.base import AbstractRepository


class InvoiceRepository(AbstractRepository[Invoice]):
    model = Invoice

    async def get_by_number(self, invoice_number: str) -> Invoice | None:
        return await self.get_by(invoice_number=invoice_number)

    async def list(self, *filters, order_by=None, page: int = 1, per_page: int = 20):
        """Override list to eager load relationships."""
        from sqlalchemy import select
        stmt = (
            select(Invoice)
            .options(
                selectinload(Invoice.vendor),
                selectinload(Invoice.items),
                selectinload(Invoice.three_way_matches),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(Invoice.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_items(self, invoice_id: UUID) -> Invoice | None:
        stmt = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.items).selectinload(InvoiceItem.po_item),
                selectinload(Invoice.items).selectinload(InvoiceItem.grn_item),
                selectinload(Invoice.vendor),
                selectinload(Invoice.po),
                selectinload(Invoice.three_way_matches),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_po(self, po_id: UUID) -> list[Invoice]:
        return list(
            await self.list_all(
                Invoice.po_id == po_id,
                order_by=Invoice.created_at.desc(),
            )
        )

    async def get_pending_verification(self) -> list[Invoice]:
        return list(
            await self.list_all(
                Invoice.status == "PENDING_VERIFICATION",
                order_by=Invoice.invoice_date,
            )
        )

    async def get_disputed(self) -> list[Invoice]:
        return list(
            await self.list_all(Invoice.status == "DISPUTED")
        )
