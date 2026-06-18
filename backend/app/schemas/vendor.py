"""Vendor schemas."""
from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import BaseSchema


class VendorAddressCreate(BaseSchema):
    address_type: str = "BILLING"
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str | None = None
    pincode: str | None = None
    country: str = "IND"
    is_default: bool = False


class VendorContactCreate(BaseSchema):
    name: str
    designation: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    is_primary: bool = False


class VendorCreate(BaseSchema):
    name: str = Field(min_length=2)
    short_name: str | None = None
    vendor_type: str = "SUPPLIER"
    tax_id: str | None = None
    gst_number: str | None = None
    pan_number: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    website: str | None = None
    payment_terms: str = "NET30"
    bank_name: str | None = None
    bank_account: str | None = None
    bank_ifsc: str | None = None
    credit_limit: Decimal | None = None
    currency: str = "INR"
    addresses: list[VendorAddressCreate] = []
    contacts: list[VendorContactCreate] = []


class VendorUpdate(BaseSchema):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    payment_terms: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_ifsc: str | None = None
    credit_limit: Decimal | None = None
    rating: Decimal | None = None


class VendorAddressResponse(BaseSchema):
    id: UUID
    address_type: str
    address_line1: str
    city: str
    state: str | None
    pincode: str | None
    country: str
    is_default: bool


class VendorContactResponse(BaseSchema):
    id: UUID
    name: str
    designation: str | None
    email: str | None
    phone: str | None
    is_primary: bool


class VendorResponse(BaseSchema):
    id: UUID
    vendor_number: str
    name: str
    short_name: str | None
    vendor_type: str
    gst_number: str | None
    email: str | None
    phone: str | None
    payment_terms: str
    credit_limit: Decimal | None
    currency: str
    status: str
    rating: Decimal | None
    addresses: list[VendorAddressResponse] = []
    contacts: list[VendorContactResponse] = []


class VendorBlockRequest(BaseSchema):
    reason: str = Field(min_length=10)
