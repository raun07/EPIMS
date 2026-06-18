"""Procurement schemas — PR, PO, GRN."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


# ── PR schemas ────────────────────────────────────────────────────────────────

class PRItemCreate(BaseSchema):
    description: str = Field(min_length=3)
    quantity: Decimal = Field(gt=0)
    material_id: UUID | None = None
    uom_id: UUID | None = None
    estimated_price: Decimal | None = Field(None, ge=0)
    required_date: date | None = None
    preferred_vendor_id: UUID | None = None
    specifications: str | None = None


class PRCreate(BaseSchema):
    title: str = Field(min_length=5)
    description: str | None = None
    priority: str = "NORMAL"
    required_date: date | None = None
    cost_center: str | None = None
    department: str | None = None
    warehouse_id: UUID | None = None
    notes: str | None = None
    items: list[PRItemCreate] = Field(min_length=1)


class PRUpdate(BaseSchema):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    required_date: date | None = None
    notes: str | None = None


class PRRejectRequest(BaseSchema):
    reason: str = Field(min_length=10)


class PRItemResponse(BaseSchema):
    id: UUID
    line_number: int
    description: str
    quantity: Decimal
    estimated_price: Decimal | None
    estimated_value: Decimal | None
    currency: str
    status: str
    material_id: UUID | None
    uom_id: UUID | None


class PRResponse(BaseSchema):
    id: UUID
    pr_number: str
    title: str
    description: str | None
    status: str
    priority: str
    required_date: date | None
    cost_center: str | None
    department: str | None
    total_value: Decimal
    currency: str
    notes: str | None
    rejection_reason: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    created_at: datetime
    requested_by: UUID
    items: list[PRItemResponse] = []


# ── PO schemas ────────────────────────────────────────────────────────────────

class POItemCreate(BaseSchema):
    description: str = Field(min_length=3)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    material_id: UUID | None = None
    uom_id: UUID | None = None
    pr_item_id: UUID | None = None
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    tax_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    delivery_date: date | None = None


class POCreate(BaseSchema):
    vendor_id: UUID
    pr_id: UUID | None = None
    po_type: str = "STANDARD"
    delivery_date: date | None = None
    warehouse_id: UUID | None = None
    payment_terms: str | None = None
    notes: str | None = None
    items: list[POItemCreate] = Field(min_length=1)


class POUpdate(BaseSchema):
    delivery_date: date | None = None
    payment_terms: str | None = None
    notes: str | None = None
    internal_notes: str | None = None


class POItemResponse(BaseSchema):
    id: UUID
    line_number: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    tax_pct: Decimal
    net_value: Decimal
    qty_received: Decimal
    qty_invoiced: Decimal
    status: str
    material_id: UUID | None
    delivery_date: date | None


class POResponse(BaseSchema):
    id: UUID
    po_number: str
    vendor_id: UUID
    pr_id: UUID | None
    status: str
    po_type: str
    order_date: date
    delivery_date: date | None
    payment_terms: str | None
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    items: list[POItemResponse] = []


# ── GRN schemas ───────────────────────────────────────────────────────────────

class GRNItemCreate(BaseSchema):
    po_item_id: UUID | None = None
    material_id: UUID | None = None
    quantity_delivered: Decimal = Field(gt=0)
    quantity_accepted: Decimal | None = None
    uom_id: UUID | None = None
    unit_price: Decimal | None = None
    storage_location_id: UUID | None = None
    batch_number: str | None = None
    expiry_date: date | None = None
    inspection_note: str | None = None
    rejection_reason: str | None = None

    @field_validator("quantity_accepted", mode="before")
    @classmethod
    def default_accepted(cls, v, info):
        if v is None and "quantity_delivered" in info.data:
            return info.data["quantity_delivered"]
        return v


class GRNCreate(BaseSchema):
    po_id: UUID
    warehouse_id: UUID
    receipt_date: date | None = None
    delivery_note: str | None = None
    vehicle_number: str | None = None
    driver_name: str | None = None
    notes: str | None = None
    items: list[GRNItemCreate] = Field(min_length=1)


class GRNItemResponse(BaseSchema):
    id: UUID
    line_number: int
    material_id: UUID | None
    quantity_delivered: Decimal
    quantity_accepted: Decimal
    quantity_rejected: Decimal
    unit_price: Decimal | None
    net_value: Decimal | None
    batch_number: str | None
    storage_location_id: UUID | None
    inspection_note: str | None
    rejection_reason: str | None


class GRNResponse(BaseSchema):
    id: UUID
    grn_number: str
    po_id: UUID
    vendor_id: UUID | None
    warehouse_id: UUID
    status: str
    receipt_date: date
    delivery_note: str | None
    total_value: Decimal
    currency: str
    posted_by: UUID | None
    posted_at: datetime | None
    created_at: datetime
    items: list[GRNItemResponse] = []


class GRNReverseRequest(BaseSchema):
    reason: str = Field(min_length=10)
