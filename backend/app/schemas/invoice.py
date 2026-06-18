"""Invoice schemas."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class InvoiceItemCreate(BaseSchema):
    description: str | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    material_id: UUID | None = None
    po_item_id: UUID | None = None
    grn_item_id: UUID | None = None
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)


class InvoiceCreate(BaseSchema):
    vendor_id: UUID
    po_id: UUID | None = None
    vendor_invoice_number: str | None = None
    invoice_date: date
    due_date: date | None = None
    notes: str | None = None
    tolerance_pct: float = 2.0
    items: list[InvoiceItemCreate] = Field(min_length=1)


class InvoiceItemResponse(BaseSchema):
    id: UUID
    line_number: int
    description: str | None
    quantity: Decimal
    unit_price: Decimal
    net_value: Decimal
    match_flag: str | None
    variance_pct: Decimal | None


class InvoiceResponse(BaseSchema):
    id: UUID
    invoice_number: str
    vendor_invoice_number: str | None
    vendor_id: UUID
    po_id: UUID | None
    status: str
    invoice_date: date
    due_date: date | None
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    match_status: str | None
    dispute_reason: str | None
    notes: str | None
    verified_at: datetime | None
    created_at: datetime
    items: list[InvoiceItemResponse] = []


class ThreeWayMatchResponse(BaseSchema):
    invoice_id: UUID
    po_id: UUID | None
    grn_id: UUID | None
    match_result: str
    price_variance: Decimal | None
    qty_variance: Decimal | None
    value_variance: Decimal | None
    tolerance_pct: Decimal | None
    notes: str | None
    checked_at: datetime


class InvoiceOverrideRequest(BaseSchema):
    reason: str = Field(min_length=10)


class MarkPaidRequest(BaseSchema):
    paid_amount: Decimal = Field(gt=0)
