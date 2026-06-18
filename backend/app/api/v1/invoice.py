"""Invoice API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import CurrentUser, require_permission
from app.core.unit_of_work import UnitOfWork
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceOverrideRequest,
    InvoiceResponse,
    MarkPaidRequest,
    ThreeWayMatchResponse,
)
from app.services.invoice_service import InvoiceService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    body: InvoiceCreate,
    current_user: CurrentUser,
    _: None = require_permission("invoices", "create"),
):
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        invoice = await svc.create_invoice(
            vendor_id=body.vendor_id,
            invoice_date=body.invoice_date,
            items=[i.model_dump() for i in body.items],
            created_by_id=current_user.id,
            po_id=body.po_id,
            vendor_invoice_number=body.vendor_invoice_number,
            due_date=body.due_date,
            notes=body.notes,
            tolerance_pct=body.tolerance_pct,
        )
        await uow.commit()
        await uow.refresh(invoice)
    return invoice


@router.get("", response_model=PaginatedResponse[InvoiceResponse])
async def list_invoices(
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    vendor_id: UUID | None = None,
    _: None = require_permission("invoices", "read"),
):
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        items, total = await svc.list_invoices(
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


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("invoices", "read"),
):
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        return await svc.get_invoice(invoice_id)


@router.post("/{invoice_id}/verify", response_model=ThreeWayMatchResponse)
async def run_three_way_match(
    invoice_id: UUID,
    current_user: CurrentUser,
    force: bool = False,
    _: None = require_permission("invoices", "verify"),
):
    """Run the 3-way match. Returns match result; raises 400 if match fails."""
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        match_result = await svc.run_three_way_match(
            invoice_id, current_user.id, force=force
        )
        await uow.commit()
    return match_result


@router.post("/{invoice_id}/override", response_model=InvoiceResponse)
async def override_dispute(
    invoice_id: UUID,
    body: InvoiceOverrideRequest,
    current_user: CurrentUser,
    _: None = require_permission("invoices", "override"),
):
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        invoice = await svc.override_dispute(invoice_id, current_user.id, body.reason)
        await uow.commit()
    return invoice


@router.post("/{invoice_id}/payment", response_model=InvoiceResponse)
async def mark_paid(
    invoice_id: UUID,
    body: MarkPaidRequest,
    current_user: CurrentUser,
    _: None = require_permission("invoices", "payment"),
):
    async with UnitOfWork() as uow:
        svc = InvoiceService(uow)
        invoice = await svc.mark_paid(invoice_id, body.paid_amount, current_user.id)
        await uow.commit()
    return invoice
