"""Procurement API — PRs, POs, GRNs."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import CurrentUser, require_permission
from app.core.unit_of_work import UnitOfWork
from app.schemas.common import PaginatedResponse, PaginationMeta, SuccessResponse
from app.schemas.procurement import (
    GRNCreate,
    GRNResponse,
    GRNReverseRequest,
    POCreate,
    POResponse,
    POUpdate,
    PRCreate,
    PRRejectRequest,
    PRResponse,
    PRUpdate,
)
from app.services.grn_service import GRNService
from app.services.po_service import POService
from app.services.pr_service import PRService

router = APIRouter(tags=["Procurement"])

# ── Purchase Requisitions ─────────────────────────────────────────────────────

pr_router = APIRouter(prefix="/purchase-requisitions")


@pr_router.post("", response_model=PRResponse, status_code=status.HTTP_201_CREATED)
async def create_pr(
    body: PRCreate,
    current_user: CurrentUser,
    _: None = require_permission("purchase_requisitions", "create"),
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        pr = await svc.create_pr(
            title=body.title,
            description=body.description,
            requested_by_id=current_user.id,
            items=[i.model_dump() for i in body.items],
            priority=body.priority,
            required_date=body.required_date,
            cost_center=body.cost_center,
            department=body.department,
            warehouse_id=body.warehouse_id,
            notes=body.notes,
        )
        await uow.commit()
        pr_id = pr.id
    async with UnitOfWork() as uow2:
        pr = await uow2.purchase_requisitions.get_with_items(pr_id)
    return pr


@pr_router.get("", response_model=PaginatedResponse[PRResponse])
async def list_prs(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    my_prs: bool = False,
    _: None = require_permission("purchase_requisitions", "read"),
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        requester_id = current_user.id if my_prs else None
        items, total = await svc.list_prs(
            page=page, per_page=per_page, status=status, requester_id=requester_id
        )
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total,
            has_prev=page > 1,
        ),
    )


@pr_router.get("/{pr_id}", response_model=PRResponse)
async def get_pr(
    pr_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("purchase_requisitions", "read"),
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        return await svc.get_pr(pr_id)


@pr_router.put("/{pr_id}", response_model=PRResponse)
async def update_pr(
    pr_id: UUID,
    body: PRUpdate,
    current_user: CurrentUser,
    _: None = require_permission("purchase_requisitions", "update"),
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        pr = await svc.update_pr(pr_id, current_user.id, body.model_dump(exclude_none=True))
        await uow.commit()
    return pr


@pr_router.post("/{pr_id}/submit", response_model=PRResponse)
async def submit_pr(
    pr_id: UUID,
    current_user: CurrentUser,
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        pr = await svc.submit_pr(pr_id, current_user.id)
        await uow.commit()
    return pr


@pr_router.post("/{pr_id}/cancel", response_model=PRResponse)
async def cancel_pr(
    pr_id: UUID,
    current_user: CurrentUser,
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        pr = await svc.cancel_pr(pr_id, current_user.id)
        await uow.commit()
    return pr


@pr_router.post("/{pr_id}/reject", response_model=PRResponse)
async def reject_pr(
    pr_id: UUID,
    body: PRRejectRequest,
    current_user: CurrentUser,
    _: None = require_permission("purchase_requisitions", "approve"),
):
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        pr = await svc.reject_pr(pr_id, current_user.id, body.reason)
        await uow.commit()
    return pr


# ── Purchase Orders ───────────────────────────────────────────────────────────

po_router = APIRouter(prefix="/purchase-orders")


@po_router.post("", response_model=POResponse, status_code=status.HTTP_201_CREATED)
async def create_po(
    body: POCreate,
    current_user: CurrentUser,
    _: None = require_permission("purchase_orders", "create"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        po = await svc.create_po(
            vendor_id=body.vendor_id,
            items=[i.model_dump() for i in body.items],
            created_by_id=current_user.id,
            pr_id=body.pr_id,
            po_type=body.po_type,
            delivery_date=body.delivery_date,
            warehouse_id=body.warehouse_id,
            payment_terms=body.payment_terms,
            notes=body.notes,
        )
        await uow.commit()
        await uow.refresh(po)
    return po


@po_router.get("", response_model=PaginatedResponse[POResponse])
async def list_pos(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    vendor_id: UUID | None = None,
    _: None = require_permission("purchase_orders", "read"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        items, total = await svc.list_pos(
            page=page, per_page=per_page, status=status, vendor_id=vendor_id
        )
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page, per_page=per_page, total=total,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total, has_prev=page > 1,
        ),
    )


@po_router.get("/{po_id}", response_model=POResponse)
async def get_po(
    po_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("purchase_orders", "read"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        return await svc.get_po(po_id)


@po_router.put("/{po_id}", response_model=POResponse)
async def amend_po(
    po_id: UUID,
    body: POUpdate,
    current_user: CurrentUser,
    _: None = require_permission("purchase_orders", "update"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        po = await svc.amend_po(po_id, current_user.id, body.model_dump(exclude_none=True))
        await uow.commit()
    return po


@po_router.post("/{po_id}/submit", response_model=POResponse)
async def submit_po_for_approval(
    po_id: UUID,
    current_user: CurrentUser,
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        po = await svc.submit_for_approval(po_id, current_user.id)
        await uow.commit()
    return po


@po_router.post("/{po_id}/release", response_model=POResponse)
async def release_po(
    po_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("purchase_orders", "release"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        po = await svc.release_po(po_id, current_user.id)
        await uow.commit()
    return po


@po_router.post("/{po_id}/cancel", response_model=POResponse)
async def cancel_po(
    po_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("purchase_orders", "cancel"),
):
    async with UnitOfWork() as uow:
        svc = POService(uow)
        po = await svc.cancel_po(po_id, current_user.id)
        await uow.commit()
    return po


# ── Goods Receipts ────────────────────────────────────────────────────────────

grn_router = APIRouter(prefix="/goods-receipts")


@grn_router.post("", response_model=GRNResponse, status_code=status.HTTP_201_CREATED)
async def create_grn(
    body: GRNCreate,
    current_user: CurrentUser,
    _: None = require_permission("goods_receipts", "create"),
):
    async with UnitOfWork() as uow:
        svc = GRNService(uow)
        grn = await svc.create_grn(
            po_id=body.po_id,
            warehouse_id=body.warehouse_id,
            items=[i.model_dump() for i in body.items],
            created_by_id=current_user.id,
            receipt_date=body.receipt_date,
            delivery_note=body.delivery_note,
            vehicle_number=body.vehicle_number,
            driver_name=body.driver_name,
            notes=body.notes,
        )
        await uow.commit()
        await uow.refresh(grn)
    return grn


@grn_router.post("/{grn_id}/post", response_model=GRNResponse)
async def post_grn(
    grn_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("goods_receipts", "post"),
):
    async with UnitOfWork() as uow:
        svc = GRNService(uow)
        grn = await svc.post_grn(grn_id, current_user.id)
        await uow.commit()
    return grn


@grn_router.get("/{grn_id}", response_model=GRNResponse)
async def get_grn(
    grn_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("goods_receipts", "read"),
):
    async with UnitOfWork() as uow:
        svc = GRNService(uow)
        return await svc.get_grn(grn_id)


@grn_router.post("/{grn_id}/reverse", response_model=GRNResponse)
async def reverse_grn(
    grn_id: UUID,
    body: GRNReverseRequest,
    current_user: CurrentUser,
    _: None = require_permission("goods_receipts", "reverse"),
):
    async with UnitOfWork() as uow:
        svc = GRNService(uow)
        grn = await svc.reverse_grn(grn_id, current_user.id, body.reason)
        await uow.commit()
    return grn


@grn_router.get("", response_model=PaginatedResponse[GRNResponse])
async def list_grns(
    current_user: CurrentUser,
    po_id: UUID | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: None = require_permission("goods_receipts", "read"),
):
    async with UnitOfWork() as uow:
        svc = GRNService(uow)
        items, total = await svc.list_grns(po_id=po_id, page=page, per_page=per_page)
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(
            page=page, per_page=per_page, total=total,
            total_pages=(total + per_page - 1) // per_page,
            has_next=page * per_page < total, has_prev=page > 1,
        ),
    )


# Wire sub-routers into main router
router.include_router(pr_router)
router.include_router(po_router)
router.include_router(grn_router)
