"""Common Pydantic schema primitives shared across modules."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class IDResponse(BaseSchema):
    id: UUID


class SuccessResponse(BaseSchema):
    success: bool = True
    message: str


class PaginationMeta(BaseSchema):
    page: int
    per_page: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseSchema, Generic[T]):
    success: bool = True
    data: list[T]
    meta: PaginationMeta


class ErrorResponse(BaseSchema):
    success: bool = False
    detail: str | dict[str, Any]
