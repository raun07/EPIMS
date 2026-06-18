"""Material schemas."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class MaterialGroupResponse(BaseSchema):
    id: UUID
    code: str
    name: str
    parent_id: UUID | None


class UOMResponse(BaseSchema):
    id: UUID
    code: str
    name: str
    conversion_factor: Decimal


class MaterialCreate(BaseSchema):
    description: str = Field(min_length=3)
    material_type: str
    material_group_id: UUID | None = None
    base_uom_id: UUID | None = None
    purchase_uom_id: UUID | None = None
    standard_price: Decimal | None = Field(None, ge=0)
    reorder_point: Decimal | None = Field(None, ge=0)
    min_order_qty: Decimal | None = Field(None, ge=0)
    max_order_qty: Decimal | None = Field(None, ge=0)
    lead_time_days: int | None = Field(None, ge=0)
    shelf_life_days: int | None = Field(None, ge=0)
    storage_conditions: str | None = None
    valuation_class: str | None = None
    currency: str = "INR"


class MaterialUpdate(BaseSchema):
    description: str | None = None
    material_type: str | None = None
    material_group_id: UUID | None = None
    standard_price: Decimal | None = None
    reorder_point: Decimal | None = None
    min_order_qty: Decimal | None = None
    max_order_qty: Decimal | None = None
    lead_time_days: int | None = None
    shelf_life_days: int | None = None
    is_active: bool | None = None


class MaterialResponse(BaseSchema):
    id: UUID
    material_number: str
    description: str
    material_type: str
    standard_price: Decimal | None
    moving_average_price: Decimal | None
    reorder_point: Decimal | None
    lead_time_days: int | None
    is_active: bool
    currency: str
    material_group: MaterialGroupResponse | None = None
    base_uom: UOMResponse | None = None
