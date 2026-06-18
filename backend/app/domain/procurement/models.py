"""
Procurement domain models.

PR  → PRItem  (purchase requisition + line items)
PO  → POItem  (purchase order + line items)
GRN → GRNItem (goods receipt note + line items)
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class PRStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PARTIALLY_ORDERED = "PARTIALLY_ORDERED"
    PO_CREATED = "PO_CREATED"
    CANCELLED = "CANCELLED"

    # Valid transitions
    TRANSITIONS: dict = {}  # populated below

PR_STATUS_TRANSITIONS: dict[str, list[str]] = {
    PRStatus.DRAFT: [PRStatus.SUBMITTED, PRStatus.CANCELLED],
    PRStatus.SUBMITTED: [PRStatus.PENDING_APPROVAL, PRStatus.CANCELLED],
    PRStatus.PENDING_APPROVAL: [PRStatus.APPROVED, PRStatus.DRAFT, PRStatus.CANCELLED],
    PRStatus.APPROVED: [PRStatus.PARTIALLY_ORDERED, PRStatus.PO_CREATED, PRStatus.CANCELLED],
    PRStatus.PARTIALLY_ORDERED: [PRStatus.PO_CREATED],
    PRStatus.PO_CREATED: [],
    PRStatus.CANCELLED: [],
}


class PRPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class PRItemStatus(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_ORDERED = "PARTIALLY_ORDERED"
    PO_CREATED = "PO_CREATED"
    CANCELLED = "CANCELLED"


class POStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    RELEASED = "RELEASED"
    SENT = "SENT"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    RECEIVED = "RECEIVED"
    INVOICED = "INVOICED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


PO_STATUS_TRANSITIONS: dict[str, list[str]] = {
    POStatus.DRAFT: [POStatus.PENDING_APPROVAL, POStatus.RELEASED, POStatus.CANCELLED],
    POStatus.PENDING_APPROVAL: [POStatus.APPROVED, POStatus.DRAFT],
    POStatus.APPROVED: [POStatus.RELEASED, POStatus.CANCELLED],
    POStatus.RELEASED: [POStatus.SENT, POStatus.PARTIALLY_RECEIVED, POStatus.RECEIVED, POStatus.CANCELLED],
    POStatus.SENT: [POStatus.PARTIALLY_RECEIVED, POStatus.RECEIVED, POStatus.CANCELLED],
    POStatus.PARTIALLY_RECEIVED: [POStatus.RECEIVED, POStatus.INVOICED],
    POStatus.RECEIVED: [POStatus.INVOICED, POStatus.CLOSED],
    POStatus.INVOICED: [POStatus.CLOSED],
    POStatus.CLOSED: [],
    POStatus.CANCELLED: [],
}


class POType(str, Enum):
    STANDARD = "STANDARD"
    BLANKET = "BLANKET"
    FRAMEWORK = "FRAMEWORK"
    CONSIGNMENT = "CONSIGNMENT"


class GRNStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    REVERSED = "REVERSED"


# ── Purchase Requisition ──────────────────────────────────────────────────────

class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pr_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default=PRStatus.DRAFT, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default=PRPriority.NORMAL, nullable=False)
    required_date: Mapped[date | None] = mapped_column(Date)
    cost_center: Mapped[str | None] = mapped_column(String(20))
    plant: Mapped[str | None] = mapped_column(String(20))
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL")
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False
    )
    department: Mapped[str | None] = mapped_column(String(100))
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items: Mapped[list[PRItem]] = relationship(
        "PRItem", back_populates="pr", cascade="all, delete-orphan", order_by="PRItem.line_number"
    )
    requester: Mapped["User"] = relationship("User", foreign_keys=[requested_by])  # noqa: F821
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")  # noqa: F821
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship("PurchaseOrder", back_populates="pr")

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in PR_STATUS_TRANSITIONS.get(self.status, [])

    def recalculate_total(self) -> None:
        self.total_value = sum(
            (item.estimated_value or Decimal("0")) for item in self.items
        )

    def __repr__(self) -> str:
        return f"<PR {self.pr_number} [{self.status}]>"


class PRItem(Base):
    __tablename__ = "pr_items"
    __table_args__ = (
        UniqueConstraint("pr_id", "line_number", name="uq_pr_items_pr_line"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="SET NULL")
    )
    estimated_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    required_date: Mapped[date | None] = mapped_column(Date)
    preferred_vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL")
    )
    delivery_address: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=PRItemStatus.OPEN, nullable=False)

    pr: Mapped[PurchaseRequisition] = relationship("PurchaseRequisition", back_populates="items")
    material: Mapped["Material | None"] = relationship("Material")  # noqa: F821
    uom: Mapped["UnitOfMeasure | None"] = relationship("UnitOfMeasure")  # noqa: F821
    preferred_vendor: Mapped["Vendor | None"] = relationship("Vendor")  # noqa: F821
    po_items: Mapped[list["POItem"]] = relationship("POItem", back_populates="pr_item")

    def calculate_value(self) -> None:
        if self.estimated_price is not None:
            self.estimated_value = self.quantity * self.estimated_price

    def __repr__(self) -> str:
        return f"<PRItem {self.pr_id} line {self.line_number}>"


# ── Purchase Order ────────────────────────────────────────────────────────────

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    pr_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="SET NULL")
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default=POStatus.DRAFT, nullable=False)
    po_type: Mapped[str] = mapped_column(String(20), default=POType.STANDARD, nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    payment_terms: Mapped[str | None] = mapped_column(String(50))
    incoterms: Mapped[str | None] = mapped_column(String(20))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="SET NULL")
    )
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    amount_received: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    amount_invoiced: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    internal_notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items: Mapped[list[POItem]] = relationship(
        "POItem", back_populates="po", cascade="all, delete-orphan", order_by="POItem.line_number"
    )
    vendor: Mapped["Vendor"] = relationship("Vendor")  # noqa: F821
    pr: Mapped[PurchaseRequisition | None] = relationship("PurchaseRequisition", back_populates="purchase_orders")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")  # noqa: F821
    created_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    approved_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])  # noqa: F821
    goods_receipts: Mapped[list["GoodsReceipt"]] = relationship("GoodsReceipt", back_populates="po")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="po")  # noqa: F821

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in PO_STATUS_TRANSITIONS.get(self.status, [])

    def recalculate_totals(self) -> None:
        self.subtotal = sum(item.net_value for item in self.items)
        self.total_amount = self.subtotal + self.tax_amount - self.discount_amount

    def __repr__(self) -> str:
        return f"<PO {self.po_number} [{self.status}]>"


class POItem(Base):
    __tablename__ = "po_items"
    __table_args__ = (
        UniqueConstraint("po_id", "line_number", name="uq_po_items_po_line"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    pr_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pr_items.id", ondelete="SET NULL")
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="SET NULL")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    tax_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    net_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    delivery_date: Mapped[date | None] = mapped_column(Date)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    qty_invoiced: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)

    po: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="items")
    pr_item: Mapped[PRItem | None] = relationship("PRItem", back_populates="po_items")
    material: Mapped["Material | None"] = relationship("Material")  # noqa: F821
    uom: Mapped["UnitOfMeasure | None"] = relationship("UnitOfMeasure")  # noqa: F821
    grn_items: Mapped[list["GRNItem"]] = relationship("GRNItem", back_populates="po_item")

    def calculate_net_value(self) -> None:
        base = self.quantity * self.unit_price
        discount = base * (self.discount_pct / Decimal("100"))
        self.net_value = base - discount

    def __repr__(self) -> str:
        return f"<POItem {self.po_id} line {self.line_number}>"


# ── Goods Receipt ─────────────────────────────────────────────────────────────

class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    po_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="RESTRICT"), nullable=False
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="SET NULL")
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default=GRNStatus.DRAFT, nullable=False)
    receipt_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    delivery_note: Mapped[str | None] = mapped_column(String(100))
    vehicle_number: Mapped[str | None] = mapped_column(String(30))
    driver_name: Mapped[str | None] = mapped_column(String(100))
    total_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    posted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    items: Mapped[list[GRNItem]] = relationship(
        "GRNItem", back_populates="grn", cascade="all, delete-orphan", order_by="GRNItem.line_number"
    )
    po: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="goods_receipts")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")  # noqa: F821
    vendor: Mapped["Vendor | None"] = relationship("Vendor")  # noqa: F821
    posted_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[posted_by])  # noqa: F821
    three_way_matches: Mapped[list["ThreeWayMatchResult"]] = relationship(  # noqa: F821
        "ThreeWayMatchResult", back_populates="grn"
    )

    def __repr__(self) -> str:
        return f"<GRN {self.grn_number} [{self.status}]>"


class GRNItem(Base):
    __tablename__ = "grn_items"
    __table_args__ = (
        UniqueConstraint("grn_id", "line_number", name="uq_grn_items_grn_line"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("goods_receipts.id", ondelete="CASCADE"), nullable=False
    )
    po_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("po_items.id", ondelete="SET NULL")
    )
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    material_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("materials.id", ondelete="SET NULL")
    )
    quantity_delivered: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    quantity_accepted: Mapped[Decimal] = mapped_column(Numeric(18, 3), nullable=False)
    quantity_rejected: Mapped[Decimal] = mapped_column(Numeric(18, 3), default=Decimal("0"), nullable=False)
    uom_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units_of_measure.id", ondelete="SET NULL")
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    net_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    storage_location_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_locations.id", ondelete="SET NULL")
    )
    batch_number: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    inspection_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    grn: Mapped[GoodsReceipt] = relationship("GoodsReceipt", back_populates="items")
    po_item: Mapped[POItem | None] = relationship("POItem", back_populates="grn_items")
    material: Mapped["Material | None"] = relationship("Material")  # noqa: F821
    uom: Mapped["UnitOfMeasure | None"] = relationship("UnitOfMeasure")  # noqa: F821
    invoice_items: Mapped[list["InvoiceItem"]] = relationship("InvoiceItem", back_populates="grn_item")  # noqa: F821

    def __repr__(self) -> str:
        return f"<GRNItem {self.grn_id} line {self.line_number}>"
