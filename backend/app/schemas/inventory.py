"""Inventory schemas."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class StockResponse(BaseSchema):
    id: UUID
    material_id: UUID
    warehouse_id: UUID
    storage_location_id: UUID | None
    batch_number: str | None
    stock_type: str
    quantity: Decimal
    valuation_price: Decimal | None
    currency: str
    total_value: Decimal
    last_movement_date: date | None


class StockTransferRequest(BaseSchema):
    material_id: UUID
    quantity: Decimal = Field(gt=0)
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    from_location_id: UUID | None = None
    to_location_id: UUID | None = None
    batch_number: str | None = None
    reason: str | None = None


class StockIssueRequest(BaseSchema):
    material_id: UUID
    quantity: Decimal = Field(gt=0)
    warehouse_id: UUID
    location_id: UUID | None = None
    movement_type: str = "201"
    batch_number: str | None = None
    reference_doc_type: str | None = None
    reference_doc_id: UUID | None = None
    reason: str | None = None


class InitialStockRequest(BaseSchema):
    material_id: UUID
    warehouse_id: UUID
    location_id: UUID | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    currency: str = "INR"
    batch_number: str | None = None
    uom_id: UUID | None = None


class StockMovementResponse(BaseSchema):
    id: UUID
    movement_number: str
    movement_type: str
    movement_date: date
    material_id: UUID
    quantity: Decimal
    unit_price: Decimal | None
    total_value: Decimal | None
    currency: str
    reference_doc_type: str | None
    reference_doc_id: UUID | None
    batch_number: str | None
    created_at: date


class LowStockAlert(BaseSchema):
    material_id: str
    material_number: str | None
    warehouse_id: str
    warehouse_code: str | None
    current_qty: float
    reorder_point: float
    deficit: float
