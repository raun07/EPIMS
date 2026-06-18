"""Alembic environment configuration."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# ── Import all models so Alembic detects them ─────────────────────────────────
from app.domain.audit.models import AuditLog  # noqa: F401
from app.domain.auth.models import Permission, Role, User  # noqa: F401
from app.domain.approval.models import (  # noqa: F401
    ApprovalActionRecord,
    ApprovalDelegation,
    ApprovalInstance,
    ApprovalRule,
    ApprovalWorkflow,
)
from app.domain.inventory.models import InventoryStock, StockMovement  # noqa: F401
from app.domain.invoice.models import (  # noqa: F401
    Invoice,
    InvoiceItem,
    ThreeWayMatchResult,
)
from app.domain.material.models import Material, MaterialGroup, UnitOfMeasure  # noqa: F401
from app.domain.notification.models import Notification, NotificationTemplate  # noqa: F401
from app.domain.procurement.models import (  # noqa: F401
    GoodsReceipt,
    GRNItem,
    POItem,
    PRItem,
    PurchaseOrder,
    PurchaseRequisition,
)
from app.domain.vendor.models import Vendor, VendorAddress, VendorContact, VendorMaterialInfo  # noqa: F401
from app.domain.warehouse.models import StorageLocation, Warehouse  # noqa: F401

# Alembic config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations with an async engine (used for online mode)."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
