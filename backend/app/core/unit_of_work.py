"""
Unit of Work pattern.

UnitOfWork wraps an AsyncSession and exposes all repository instances.
Services import UnitOfWork, never the session or repositories directly.

Usage:
    async with UnitOfWork() as uow:
        user = await uow.users.get_by_email("admin@epims.local")
        await uow.commit()

The UoW guarantees that all operations inside one `async with` block
share a single database transaction.
"""
from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.repositories.approval import ApprovalRepository
from app.repositories.audit import AuditRepository
from app.repositories.auth import RoleRepository, UserRepository
from app.repositories.inventory import InventoryRepository, StockMovementRepository
from app.repositories.invoice import InvoiceRepository
from app.repositories.material import MaterialGroupRepository, MaterialRepository
from app.repositories.notification import NotificationRepository
from app.repositories.procurement import GRNRepository, PORepository, PRRepository
from app.repositories.vendor import VendorRepository
from app.repositories.warehouse import StorageLocationRepository, WarehouseRepository


class UnitOfWork:
    """
    Context manager that:
    1. Opens a single AsyncSession for the duration of the block.
    2. Lazily instantiates repositories bound to that session.
    3. Commits on clean exit; rolls back on any exception.
    """

    def __init__(self) -> None:
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        self._session = AsyncSessionLocal()
        self._bind_repositories()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        await self._session.close()  # type: ignore[union-attr]

    def _bind_repositories(self) -> None:
        """Wire all repositories to the current session."""
        s = self.session
        # Auth
        self.users = UserRepository(s)
        self.roles = RoleRepository(s)
        # Master data
        self.materials = MaterialRepository(s)
        self.material_groups = MaterialGroupRepository(s)
        self.vendors = VendorRepository(s)
        self.warehouses = WarehouseRepository(s)
        self.storage_locations = StorageLocationRepository(s)
        # Inventory
        self.inventory = InventoryRepository(s)
        self.stock_movements = StockMovementRepository(s)
        # Procurement
        self.purchase_requisitions = PRRepository(s)
        self.purchase_orders = PORepository(s)
        self.goods_receipts = GRNRepository(s)
        # Finance
        self.invoices = InvoiceRepository(s)
        # Workflow
        self.approvals = ApprovalRepository(s)
        # Cross-cutting
        self.notifications = NotificationRepository(s)
        self.audit = AuditRepository(s)

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork not entered — use 'async with UnitOfWork()'")
        return self._session

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        """Flush pending changes to DB without committing (useful for generated IDs)."""
        await self.session.flush()

    async def refresh(self, instance: object) -> None:
        """Reload an instance's attributes from the database."""
        await self.session.refresh(instance)
