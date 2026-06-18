"""
Material Master domain models.

Tables: material_groups, units_of_measure, materials, vendor_material_info
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MaterialType(str, Enum):
    RAW = "RAW"
    SEMI_FINISHED = "SEMI_FINISHED"
    FINISHED = "FINISHED"
    SERVICE = "SERVICE"
    CONSUMABLE = "CONSUMABLE"
    SPARE_PART = "SPARE_PART"
    TRADING_GOOD = "TRADING_GOOD"


class ValuationClass(str, Enum):
    RAW_MATERIAL = "3000"
    FINISHED_GOOD = "7920"
    SEMI_FINISHED = "7900"
    TRADING_GOOD = "3100"
    CONSUMABLE = "3030"
    SERVICE = "3050"


class MaterialGroup(Base):
    __tablename__ = "material_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_groups.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    parent: Mapped[MaterialGroup | None] = relationship(
        "MaterialGroup", remote_side="MaterialGroup.id", foreign_keys=[parent_id]
    )
    children: Mapped[list[MaterialGroup]] = relationship(
        "MaterialGroup", foreign_keys=[parent_id]
    )
    materials: Mapped[list[Material]] = relationship(
        "Material", back_populates="material_group"
    )

    def __repr__(self) -> str:
        return f"<MaterialGroup {self.code}: {self.name}>"


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    base_unit: Mapped[str | None] = mapped_column(String(10))
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), default=Decimal("1.0"), nullable=False
    )

    def __repr__(self) -> str:
        return f"<UOM {self.code}>"


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    material_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    material_type: Mapped[str] = mapped_column(String(30), nullable=False)
    material_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("material_groups.id", ondelete="SET NULL")
    )
    base_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="RESTRICT")
    )
    purchase_uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="RESTRICT")
    )
    valuation_class: Mapped[str | None] = mapped_column(String(20))
    standard_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    moving_average_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    price_unit: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), default=Decimal("1.0"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    weight_gross: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    weight_net: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    weight_unit: Mapped[str | None] = mapped_column(String(5))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    volume_unit: Mapped[str | None] = mapped_column(String(5))
    storage_conditions: Mapped[str | None] = mapped_column(String(100))
    shelf_life_days: Mapped[int | None] = mapped_column(Integer)
    reorder_point: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    min_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    max_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    material_group: Mapped[MaterialGroup | None] = relationship(
        "MaterialGroup", back_populates="materials"
    )
    base_uom: Mapped[UnitOfMeasure | None] = relationship(
        "UnitOfMeasure", foreign_keys=[base_uom_id]
    )
    purchase_uom: Mapped[UnitOfMeasure | None] = relationship(
        "UnitOfMeasure", foreign_keys=[purchase_uom_id]
    )
    created_by_user: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )

    def __repr__(self) -> str:
        return f"<Material {self.material_number}: {self.description}>"
