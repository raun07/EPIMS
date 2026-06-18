"""
Inventory domain models.

InventoryStock — current on-hand quantities per material/warehouse/location/batch
StockMovement  — immutable ledger of every stock change (mirrors SAP material document)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Date, DateTime, ForeignKey, Numeric, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StockType(str, Enum):
    UNRESTRICTED = "UNRESTRICTED"
    QUALITY_INSPECTION = "QUALITY_INSPECTION"
    BLOCKED = "BLOCKED"
    RESERVED = "RESERVED"
    IN_TRANSIT = "IN_TRANSIT"


class MovementType(str, Enum):
    """
    SAP-inspired movement type codes.
    101 = Goods receipt vs PO
    122 = Return delivery to vendor
    201 = Goods issue to cost center
    261 = Goods issue for production order
    301 = Transfer posting (plant to plant)
    311 = Transfer posting (storage location to storage location)
    321 = Transfer from QI to unrestricted
    344 = Transfer from blocked to unrestricted
    """
    GR_VS_PO = "101"
    GR_RETURN = "122"
    GI_COST_CENTER = "201"
    GI_PRODUCTION = "261"
    TRANSFER_PLANT = "301"
    TRANSFER_SLOC = "311"
    QI_TO_UNRESTRICTED = "321"
    BLOCKED_TO_UNRESTRICTED = "344"
    MANUAL_ADJUSTMENT = "551"
    INITIAL_STOCK = "561"


class InventoryStock(Base):
    __tablename__ = "inventory_stock"
    __table_args__ = (
        UniqueConstraint(
            "material_id", "warehouse_id", "storage_location_id", "batch_number", "stock_type",
            name="uq_inventory_stock_material_location_batch_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    storage_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_locations.id", ondelete="SET NULL")
    )
    batch_number: Mapped[str | None] = mapped_column(String(50))
    stock_type: Mapped[str] = mapped_column(String(30), default="UNRESTRICTED", nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="RESTRICT")
    )
    valuation_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    last_movement_date: Mapped[date | None] = mapped_column(Date)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    material: Mapped["Material"] = relationship("Material")  # noqa: F821
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    storage_location: Mapped["StorageLocation | None"] = relationship("StorageLocation")  # noqa: F821
    uom: Mapped["UnitOfMeasure | None"] = relationship("UnitOfMeasure")  # noqa: F821

    @property
    def total_value(self) -> Decimal:
        if self.valuation_price is None:
            return Decimal("0")
        return self.quantity * self.valuation_price

    def __repr__(self) -> str:
        return f"<InventoryStock {self.material_id} @ {self.warehouse_id}: {self.quantity}>"


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    movement_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id"), nullable=False
    )
    from_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id")
    )
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_locations.id")
    )
    to_warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id")
    )
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_locations.id")
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id")
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    reference_doc_type: Mapped[str | None] = mapped_column(String(30))
    reference_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    batch_number: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(Text)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    material: Mapped["Material"] = relationship("Material")  # noqa: F821
    from_warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[from_warehouse_id])  # noqa: F821
    to_warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[to_warehouse_id])  # noqa: F821
    posted_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[posted_by])  # noqa: F821

    def __repr__(self) -> str:
        return f"<StockMovement {self.movement_number} type={self.movement_type}>"
