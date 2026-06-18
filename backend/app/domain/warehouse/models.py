"""Warehouse & Storage Location domain models."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WarehouseType(str, Enum):
    MAIN = "MAIN"
    TRANSIT = "TRANSIT"
    COLD_STORAGE = "COLD_STORAGE"
    QUARANTINE = "QUARANTINE"
    CONSIGNMENT = "CONSIGNMENT"
    RETURNS = "RETURNS"


class LocationType(str, Enum):
    RACK = "RACK"
    SHELF = "SHELF"
    BIN = "BIN"
    FLOOR = "FLOOR"
    BULK = "BULK"


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    warehouse_type: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    storage_locations: Mapped[list[StorageLocation]] = relationship(
        "StorageLocation", back_populates="warehouse", cascade="all, delete-orphan"
    )
    manager: Mapped["User | None"] = relationship("User", foreign_keys=[manager_id])  # noqa: F821

    def __repr__(self) -> str:
        return f"<Warehouse {self.code}: {self.name}>"


class StorageLocation(Base):
    __tablename__ = "storage_locations"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "code", name="uq_storage_location_warehouse_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    location_type: Mapped[str | None] = mapped_column(String(30))
    aisle: Mapped[str | None] = mapped_column(String(10))
    rack: Mapped[str | None] = mapped_column(String(10))
    level: Mapped[str | None] = mapped_column(String(10))
    bin: Mapped[str | None] = mapped_column(String(10))
    capacity_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    capacity_volume: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    warehouse: Mapped[Warehouse] = relationship("Warehouse", back_populates="storage_locations")

    @property
    def full_address(self) -> str:
        parts = [self.warehouse.code if self.warehouse else "", self.code]
        if self.aisle:
            parts.append(f"A{self.aisle}")
        if self.rack:
            parts.append(f"R{self.rack}")
        if self.level:
            parts.append(f"L{self.level}")
        if self.bin:
            parts.append(f"B{self.bin}")
        return "-".join(filter(None, parts))

    def __repr__(self) -> str:
        return f"<StorageLocation {self.code} in {self.warehouse_id}>"
