"""Vendor repositories."""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.domain.vendor.models import Vendor, VendorContact, VendorMaterialInfo
from app.repositories.base import AbstractRepository


class VendorRepository(AbstractRepository[Vendor]):
    model = Vendor

    async def list(self, *filters, order_by=None, page: int = 1, per_page: int = 20):
        """Override to eager-load addresses and contacts relationships."""
        stmt = (
            select(Vendor)
            .options(
                selectinload(Vendor.addresses),
                selectinload(Vendor.contacts),
            )
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        for f in filters:
            stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_number(self, vendor_number: str) -> Vendor | None:
        return await self.get_by(vendor_number=vendor_number)

    async def search(self, query: str, page: int = 1, per_page: int = 20) -> list[Vendor]:
        stmt = (
            select(Vendor)
            .where(
                or_(
                    Vendor.vendor_number.ilike(f"%{query}%"),
                    Vendor.name.ilike(f"%{query}%"),
                    Vendor.gst_number.ilike(f"%{query}%"),
                )
            )
            .options(selectinload(Vendor.addresses), selectinload(Vendor.contacts))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active(self, page: int = 1, per_page: int = 20) -> list[Vendor]:
        return list(
            await self.list(Vendor.status == "ACTIVE", page=page, per_page=per_page)
        )

    async def get_with_details(self, vendor_id) -> Vendor | None:
        stmt = (
            select(Vendor)
            .where(Vendor.id == vendor_id)
            .options(
                selectinload(Vendor.addresses),
                selectinload(Vendor.contacts),
                selectinload(Vendor.material_info),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def number_exists(self, number: str) -> bool:
        return await self.exists(vendor_number=number)

    async def get_material_info(
        self, vendor_id, material_id
    ) -> VendorMaterialInfo | None:
        stmt = select(VendorMaterialInfo).where(
            VendorMaterialInfo.vendor_id == vendor_id,
            VendorMaterialInfo.material_id == material_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
