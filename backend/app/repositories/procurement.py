"""Procurement repositories: PR, PO, GRN."""
from __future__ import annotations
from uuid import UUID
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from app.domain.procurement.models import (
    GoodsReceipt,
    GRNItem,
    POItem,
    PRItem,
    PurchaseOrder,
    PurchaseRequisition,
)
from app.repositories.base import AbstractRepository


class PRRepository(AbstractRepository[PurchaseRequisition]):
    model = PurchaseRequisition

    async def list(self, *filters, order_by=None, page: int = 1, per_page: int = 20):
        stmt = (
            select(PurchaseRequisition)
            .options(
                selectinload(PurchaseRequisition.requester),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.material),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.uom),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(PurchaseRequisition.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_items(self, pr_id: UUID) -> PurchaseRequisition | None:
        stmt = (
            select(PurchaseRequisition)
            .options(
                selectinload(PurchaseRequisition.requester),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.material),
                selectinload(PurchaseRequisition.items).selectinload(PRItem.uom),
            )
            .where(PurchaseRequisition.id == pr_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def get_by_number(self, pr_number: str) -> PurchaseRequisition | None:
        return await self.get_by(pr_number=pr_number)

    async def count_by_status(self, status: str) -> int:
        return await self.count(PurchaseRequisition.status == status)


class PORepository(AbstractRepository[PurchaseOrder]):
    model = PurchaseOrder

    async def list(self, *filters, order_by=None, page: int = 1, per_page: int = 20):
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.vendor),
                selectinload(PurchaseOrder.items).selectinload(POItem.material),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            stmt = stmt.order_by(PurchaseOrder.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_items(self, po_id: UUID) -> PurchaseOrder | None:
        stmt = (
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.vendor),
                selectinload(PurchaseOrder.items).selectinload(POItem.material),
                selectinload(PurchaseOrder.items).selectinload(POItem.uom),
            )
            .where(PurchaseOrder.id == po_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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

    async def get_by_number(self, po_number: str) -> PurchaseOrder | None:
        return await self.get_by(po_number=po_number)

    async def get_open_value(self) -> float:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.sum(PurchaseOrder.total_amount)).where(
                PurchaseOrder.status.in_(["RELEASED", "SENT", "PARTIALLY_RECEIVED"])
            )
        )
        return float(result.scalar_one() or 0)


class GRNRepository(AbstractRepository[GoodsReceipt]):
    model = GoodsReceipt

    async def get_with_items(self, grn_id: UUID) -> GoodsReceipt | None:
        stmt = (
            select(GoodsReceipt)
            .options(
                selectinload(GoodsReceipt.items).selectinload(GRNItem.material),
                selectinload(GoodsReceipt.po),
                selectinload(GoodsReceipt.vendor),
            )
            .where(GoodsReceipt.id == grn_id)
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

    async def get_by_number(self, grn_number: str) -> GoodsReceipt | None:
        return await self.get_by(grn_number=grn_number)
