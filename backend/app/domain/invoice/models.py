"""Invoice Verification domain models — 3-way match engine."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class InvoiceStatus(str, Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    MATCHED = "MATCHED"
    PARTIALLY_MATCHED = "PARTIALLY_MATCHED"
    DISPUTED = "DISPUTED"
    APPROVED = "APPROVED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class MatchStatus(str, Enum):
    TWO_WAY = "TWO_WAY"
    THREE_WAY = "THREE_WAY"
    FAILED = "FAILED"
    PENDING = "PENDING"


class MatchResult(str, Enum):
    PASSED = "PASSED"
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    FAILED = "FAILED"


class LineMatchFlag(str, Enum):
    MATCHED = "MATCHED"
    PRICE_VARIANCE = "PRICE_VARIANCE"
    QTY_VARIANCE = "QTY_VARIANCE"
    UNMATCHED = "UNMATCHED"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vendor_invoice_number: Mapped[str | None] = mapped_column(String(100))
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(30), default=InvoiceStatus.PENDING_VERIFICATION, nullable=False
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    match_status: Mapped[str | None] = mapped_column(String(20))
    tolerance_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("2.0"), nullable=False)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items: Mapped[list[InvoiceItem]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    vendor: Mapped["Vendor"] = relationship("Vendor")  # noqa: F821
    po: Mapped["PurchaseOrder | None"] = relationship("PurchaseOrder", back_populates="invoices")  # noqa: F821
    created_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    verified_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[verified_by])  # noqa: F821
    three_way_matches: Mapped[list[ThreeWayMatchResult]] = relationship(
        "ThreeWayMatchResult", back_populates="invoice"
    )

    @property
    def balance_due(self) -> Decimal:
        return self.total_amount - self.paid_amount

    def __repr__(self) -> str:
        return f"<Invoice {self.invoice_number} [{self.status}]>"


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    po_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("po_items.id", ondelete="SET NULL")
    )
    grn_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("grn_items.id", ondelete="SET NULL")
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    net_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    match_flag: Mapped[str | None] = mapped_column(String(20))
    variance_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="items")
    po_item: Mapped["POItem | None"] = relationship("POItem")  # noqa: F821
    grn_item: Mapped["GRNItem | None"] = relationship("GRNItem", back_populates="invoice_items")  # noqa: F821
    material: Mapped["Material | None"] = relationship("Material")  # noqa: F821

    def __repr__(self) -> str:
        return f"<InvoiceItem {self.invoice_id} line {self.line_number}>"


class ThreeWayMatchResult(Base):
    __tablename__ = "three_way_match_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    po_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL")
    )
    grn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipts.id", ondelete="SET NULL")
    )
    match_result: Mapped[str] = mapped_column(String(20), nullable=False)
    price_variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    qty_variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 3))
    value_variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tolerance_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="three_way_matches")
    po: Mapped["PurchaseOrder | None"] = relationship("PurchaseOrder")  # noqa: F821
    grn: Mapped["GoodsReceipt | None"] = relationship("GoodsReceipt", back_populates="three_way_matches")  # noqa: F821
    checked_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[checked_by])  # noqa: F821

    def __repr__(self) -> str:
        return f"<ThreeWayMatch invoice={self.invoice_id} result={self.match_result}>"
