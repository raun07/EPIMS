"""Master Data API — Materials, Vendors, Warehouses."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core.dependencies import CurrentUser, require_permission
from app.core.unit_of_work import UnitOfWork
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.material import MaterialCreate, MaterialResponse, MaterialUpdate
from app.schemas.vendor import (
    VendorBlockRequest,
    VendorCreate,
    VendorResponse,
    VendorUpdate,
)
from app.services.material_service import MaterialService
from app.services.vendor_service import VendorService
from app.services.warehouse_service import WarehouseService

router = APIRouter(tags=["Master Data"])

# ── Materials ─────────────────────────────────────────────────────────────────

mat_router = APIRouter(prefix="/materials")


@mat_router.post("", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def create_material(
    body: MaterialCreate,
    current_user: CurrentUser,
    _: None = require_permission("materials", "create"),
):
    async with UnitOfWork() as uow:
        svc = MaterialService(uow)
        mat = await svc.create_material(body.model_dump(exclude_none=True), current_user.id)
        await uow.commit()
        await uow.refresh(mat)
    return mat


@mat_router.get("", response_model=PaginatedResponse[MaterialResponse])
async def list_materials(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: str | None = None,
    _: None = require_permission("materials", "read"),
):
    async with UnitOfWork() as uow:
        svc = MaterialService(uow)
        if q:
            items = await svc.search_materials(q, page=page, per_page=per_page)
            total = len(items)
        else:
            items, total = await svc.list_materials(page=page, per_page=per_page)
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page, per_page=per_page, total=total,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total, has_prev=page > 1,
        ),
    )


@mat_router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("materials", "read"),
):
    async with UnitOfWork() as uow:
        svc = MaterialService(uow)
        return await svc.get_material(material_id)


@mat_router.put("/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: UUID,
    body: MaterialUpdate,
    current_user: CurrentUser,
    _: None = require_permission("materials", "update"),
):
    async with UnitOfWork() as uow:
        svc = MaterialService(uow)
        mat = await svc.update_material(material_id, body.model_dump(exclude_none=True), current_user.id)
        await uow.commit()
    return mat


# ── Vendors ───────────────────────────────────────────────────────────────────

ven_router = APIRouter(prefix="/vendors")


@ven_router.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    body: VendorCreate,
    current_user: CurrentUser,
    _: None = require_permission("vendors", "create"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        vendor = await svc.create_vendor(
            body.model_dump(exclude_none=True, exclude={"addresses", "contacts"}),
            current_user.id,
        )
        await uow.commit()
        await uow.refresh(vendor)
    return vendor


@ven_router.get("", response_model=PaginatedResponse[VendorResponse])
async def list_vendors(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    _: None = require_permission("vendors", "read"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        if q:
            items = await svc.search_vendors(q, page=page, per_page=per_page)
            total = len(items)
        else:
            items, total = await svc.list_vendors(page=page, per_page=per_page, status=status)
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page, per_page=per_page, total=total,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total, has_prev=page > 1,
        ),
    )


@ven_router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("vendors", "read"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        return await svc.get_vendor(vendor_id)


@ven_router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: UUID,
    body: VendorUpdate,
    current_user: CurrentUser,
    _: None = require_permission("vendors", "update"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        vendor = await svc.update_vendor(vendor_id, body.model_dump(exclude_none=True), current_user.id)
        await uow.commit()
    return vendor


@ven_router.post("/{vendor_id}/block", response_model=VendorResponse)
async def block_vendor(
    vendor_id: UUID,
    body: VendorBlockRequest,
    current_user: CurrentUser,
    _: None = require_permission("vendors", "block"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        vendor = await svc.block_vendor(vendor_id, body.reason, current_user.id)
        await uow.commit()
    return vendor


@ven_router.post("/{vendor_id}/unblock", response_model=VendorResponse)
async def unblock_vendor(
    vendor_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("vendors", "block"),
):
    async with UnitOfWork() as uow:
        svc = VendorService(uow)
        vendor = await svc.unblock_vendor(vendor_id, current_user.id)
        await uow.commit()
    return vendor


# Wire sub-routers
router.include_router(mat_router)
router.include_router(ven_router)
