"""Procurement repositories: PR, PO, GRN."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.domain.procurement.models import (
    GRNItem,
    GoodsReceipt,
    POItem,
    PRItem,
    PurchaseOrder,
    PurchaseRequisition,
)
from app.repositories.base import AbstractRepository


class PRRepository(AbstractRepository[PurchaseRequisition]):
    model = PurchaseRequisition

    async def get_by_number(self, pr_number: str) -> PurchaseRequisition | None:
        return await self.get_by(pr_number=pr_number)

    async def get_with_items(self, pr_id: UUID) -> PurchaseRequisition | None:
        stmt = (
            select(PurchaseRequisition)
            .where(PurchaseRequisition.id == pr_id)
            .options(
                selectinload(PurchaseRequisition.items).selectinload(PRItem.material),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.uom),
                selectinload(PurchaseRequisition.requester),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_requester(
        self, user_id: UUID, page: int = 1, per_page: int = 20
    ) -> list[PurchaseRequisition]:
        return list(
            await self.list(
                PurchaseRequisition.requested_by == user_id,
                order_by=PurchaseRequisition.created_at.desc(),
                page=page,
                per_page=per_page,
            )
        )

    async def get_pending_approval(self) -> list[PurchaseRequisition]:
        return list(
            await self.list_all(
                PurchaseRequisition.status == "PENDING_APPROVAL",
                order_by=PurchaseRequisition.created_at,
            )
        )

    async def search(self, query: str, status: str | None = None,
                     page: int = 1, per_page: int = 20) -> list[PurchaseRequisition]:
        filters = [
            or_(
                PurchaseRequisition.pr_number.ilike(f"%{query}%"),
                PurchaseRequisition.title.ilike(f"%{query}%"),
            )
        ]
        if status:
            filters.append(PurchaseRequisition.status == status)
        stmt = (
            select(PurchaseRequisition)
            .where(*filters)
            .options(
                selectinload(PurchaseRequisition.requester),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.material),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.uom),
            )
            .order_by(PurchaseRequisition.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class PORepository(AbstractRepository[PurchaseOrder]):
    model = PurchaseOrder

    async def get_by_number(self, po_number: str) -> PurchaseOrder | None:
        return await self.get_by(po_number=po_number)

    async def get_with_items(self, po_id: UUID) -> PurchaseOrder | None:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id)
            .options(
                selectinload(PurchaseOrder.items).selectinload(POItem.material),
                selectinload(PurchaseOrder.items).selectinload(POItem.uom),
                selectinload(PurchaseOrder.vendor),
                selectinload(PurchaseOrder.pr),
                selectinload(PurchaseOrder.created_by_user),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_vendor(
        self, vendor_id: UUID, page: int = 1, per_page: int = 20
    ) -> list[PurchaseOrder]:
        return list(
            await self.list(
                PurchaseOrder.vendor_id == vendor_id,
                order_by=PurchaseOrder.created_at.desc(),
                page=page,
                per_page=per_page,
            )
        )

    async def get_open_orders(self) -> list[PurchaseOrder]:
        return list(
            await self.list_all(
                PurchaseOrder.status.in_(["RELEASED", "SENT", "PARTIALLY_RECEIVED"]),
                order_by=PurchaseOrder.delivery_date,
            )
        )

    async def get_overdue(self) -> list[PurchaseOrder]:
        from datetime import date
        from sqlalchemy import func

        return list(
            await self.list_all(
                PurchaseOrder.status.in_(["RELEASED", "SENT"]),
                PurchaseOrder.delivery_date < date.today(),
                order_by=PurchaseOrder.delivery_date,
            )
        )

    async def search(self, query: str, status: str | None = None,
                     vendor_id: UUID | None = None,
                     page: int = 1, per_page: int = 20) -> list[PurchaseOrder]:
        filters = [PurchaseOrder.po_number.ilike(f"%{query}%")]
        if status:
            filters.append(PurchaseOrder.status == status)
        if vendor_id:
            filters.append(PurchaseOrder.vendor_id == vendor_id)
        stmt = (
            select(PurchaseOrder)
            .where(*filters)
            .options(
                selectinload(PurchaseOrder.vendor),
                selectinload(PurchaseOrder.items).selectinload(POItem.material),
            )
            .order_by(PurchaseOrder.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class GRNRepository(AbstractRepository[GoodsReceipt]):
    model = GoodsReceipt

    async def get_by_number(self, grn_number: str) -> GoodsReceipt | None:
        return await self.get_by(grn_number=grn_number)

    async def get_with_items(self, grn_id: UUID) -> GoodsReceipt | None:
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.id == grn_id)
            .options(
                selectinload(GoodsReceipt.items).selectinload(GRNItem.material),
                selectinload(GoodsReceipt.items).selectinload(GRNItem.uom),
                selectinload(GoodsReceipt.po),
                selectinload(GoodsReceipt.vendor),
                selectinload(GoodsReceipt.warehouse),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_po(self, po_id: UUID) -> list[GoodsReceipt]:
        return list(
            await self.list_all(
                GoodsReceipt.po_id == po_id,
                order_by=GoodsReceipt.created_at.desc(),
            )
        )

    async def get_posted_by_po(self, po_id: UUID) -> list[GoodsReceipt]:
        return list(
            await self.list_all(
                GoodsReceipt.po_id == po_id,
                GoodsReceipt.status == "POSTED",
            )
        )
