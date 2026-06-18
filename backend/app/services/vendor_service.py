"""Vendor Master service."""
from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ConflictException, DomainException, NotFoundException
from app.core.unit_of_work import UnitOfWork
from app.domain.vendor.models import Vendor, VendorStatus
from app.utils.number_gen import generate_vendor_number


class VendorService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_vendor(self, data: dict, created_by_id: UUID) -> Vendor:
        ven_number = await generate_vendor_number(self.uow.session)
        data["vendor_number"] = ven_number
        data["created_by"] = created_by_id
        data.setdefault("status", VendorStatus.ACTIVE)

        vendor = await self.uow.vendors.create(data)

        await self.uow.audit.log(
            entity_type="Vendor",
            entity_id=vendor.id,
            action="CREATE",
            performed_by=created_by_id,
            new_values={"vendor_number": ven_number, "name": data.get("name")},
        )

        return vendor

    async def update_vendor(self, vendor_id: UUID, data: dict, updated_by_id: UUID) -> Vendor:
        vendor = await self.uow.vendors.get_or_raise(vendor_id)
        allowed = {
            "name", "short_name", "email", "phone", "website",
            "payment_terms", "payment_method", "bank_name",
            "bank_account", "bank_ifsc", "credit_limit", "rating",
        }
        filtered = {k: v for k, v in data.items() if k in allowed}
        old_values = {k: str(getattr(vendor, k)) for k in filtered}

        updated = await self.uow.vendors.update(vendor, filtered)

        await self.uow.audit.log(
            entity_type="Vendor",
            entity_id=vendor.id,
            action="UPDATE",
            performed_by=updated_by_id,
            old_values=old_values,
            new_values=filtered,
            changed_fields=list(filtered.keys()),
        )

        return updated

    async def block_vendor(
        self, vendor_id: UUID, reason: str, blocked_by_id: UUID
    ) -> Vendor:
        vendor = await self.uow.vendors.get_or_raise(vendor_id)
        if vendor.status == VendorStatus.BLOCKED:
            raise DomainException(f"Vendor '{vendor.name}' is already blocked")

        vendor.status = VendorStatus.BLOCKED
        vendor.blocked_reason = reason
        await self.uow.vendors.save(vendor)

        await self.uow.audit.log(
            entity_type="Vendor",
            entity_id=vendor.id,
            action="STATUS_CHANGE",
            performed_by=blocked_by_id,
            old_values={"status": "ACTIVE"},
            new_values={"status": VendorStatus.BLOCKED, "blocked_reason": reason},
        )

        return vendor

    async def unblock_vendor(self, vendor_id: UUID, unblocked_by_id: UUID) -> Vendor:
        vendor = await self.uow.vendors.get_or_raise(vendor_id)
        if vendor.status != VendorStatus.BLOCKED:
            raise DomainException(f"Vendor '{vendor.name}' is not blocked")

        vendor.status = VendorStatus.ACTIVE
        vendor.blocked_reason = None
        await self.uow.vendors.save(vendor)

        await self.uow.audit.log(
            entity_type="Vendor",
            entity_id=vendor.id,
            action="STATUS_CHANGE",
            performed_by=unblocked_by_id,
            old_values={"status": VendorStatus.BLOCKED},
            new_values={"status": VendorStatus.ACTIVE},
        )

        return vendor

    async def get_vendor(self, vendor_id: UUID) -> Vendor:
        return await self.uow.vendors.get_or_raise(vendor_id)

    async def search_vendors(self, query: str, page: int = 1, per_page: int = 20):
        return await self.uow.vendors.search(query, page=page, per_page=per_page)

    async def list_vendors(self, page: int = 1, per_page: int = 20, status: str | None = None):
        if status:
            items = await self.uow.vendors.list(
                Vendor.status == status, page=page, per_page=per_page
            )
        else:
            items = await self.uow.vendors.get_active(page=page, per_page=per_page)
        total = await self.uow.vendors.count(
            Vendor.status == (status or VendorStatus.ACTIVE)
        )
        return list(items), total
