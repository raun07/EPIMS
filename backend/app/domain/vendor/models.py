"""
Vendor Master domain models.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
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


class VendorType(str, Enum):
    SUPPLIER = "SUPPLIER"
    SERVICE_PROVIDER = "SERVICE_PROVIDER"
    CONTRACTOR = "CONTRACTOR"
    SUBCONTRACTOR = "SUBCONTRACTOR"


class VendorStatus(str, Enum):
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"
    INACTIVE = "INACTIVE"
    PENDING_APPROVAL = "PENDING_APPROVAL"


class PaymentTerms(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    NET_15 = "NET15"
    NET_30 = "NET30"
    NET_45 = "NET45"
    NET_60 = "NET60"
    NET_90 = "NET90"


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(50))
    vendor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(50))
    gst_number: Mapped[str | None] = mapped_column(String(20))
    pan_number: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    website: Mapped[str | None] = mapped_column(String(255))
    payment_terms: Mapped[str] = mapped_column(String(50), default="NET30", nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(30))
    bank_name: Mapped[str | None] = mapped_column(String(100))
    bank_account: Mapped[str | None] = mapped_column(String(50))
    bank_ifsc: Mapped[str | None] = mapped_column(String(20))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
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
    addresses: Mapped[list[VendorAddress]] = relationship(
        "VendorAddress", back_populates="vendor", cascade="all, delete-orphan"
    )
    contacts: Mapped[list[VendorContact]] = relationship(
        "VendorContact", back_populates="vendor", cascade="all, delete-orphan"
    )
    material_info: Mapped[list[VendorMaterialInfo]] = relationship(
        "VendorMaterialInfo", back_populates="vendor", cascade="all, delete-orphan"
    )
    created_by_user: Mapped["User | None"] = relationship(  # noqa: F821
        "User", foreign_keys=[created_by]
    )

    @property
    def is_blocked(self) -> bool:
        return self.status == VendorStatus.BLOCKED

    @property
    def primary_contact(self) -> VendorContact | None:
        return next((c for c in self.contacts if c.is_primary), None)

    @property
    def billing_address(self) -> VendorAddress | None:
        return next((a for a in self.addresses if a.address_type == "BILLING"), None)

    def __repr__(self) -> str:
        return f"<Vendor {self.vendor_number}: {self.name}>"


class VendorAddress(Base):
    __tablename__ = "vendor_addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False
    )
    address_type: Mapped[str] = mapped_column(String(20), nullable=False)  # BILLING, SHIPPING
    address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100))
    pincode: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str] = mapped_column(String(3), default="IND", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="addresses")

    def __repr__(self) -> str:
        return f"<VendorAddress {self.address_type} for vendor {self.vendor_id}>"


class VendorContact(Base):
    __tablename__ = "vendor_contacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="contacts")

    def __repr__(self) -> str:
        return f"<VendorContact {self.name}>"


class VendorMaterialInfo(Base):
    __tablename__ = "vendor_material_info"
    __table_args__ = (
        UniqueConstraint("vendor_id", "material_id", name="uq_vendor_material"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    vendor_mat_num: Mapped[str | None] = mapped_column(String(50))
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    last_currency: Mapped[str | None] = mapped_column(String(3))
    last_po_date: Mapped[date | None] = mapped_column(Date)
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    min_order_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))

    vendor: Mapped[Vendor] = relationship("Vendor", back_populates="material_info")
    material: Mapped["Material"] = relationship("Material")  # noqa: F821

    def __repr__(self) -> str:
        return f"<VendorMaterialInfo vendor={self.vendor_id} material={self.material_id}>"
