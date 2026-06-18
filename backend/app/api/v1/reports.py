"""Reporting and dashboard API."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import CurrentUser, DBSession, require_permission
from app.schemas.common import SuccessResponse
from app.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/dashboard")
async def dashboard_kpis(
    current_user: CurrentUser,
    db: DBSession,
):
    svc = ReportingService(db)
    return await svc.dashboard_kpis()


@router.get("/pr-summary")
async def pr_summary(
    current_user: CurrentUser,
    db: DBSession,
    from_date: date | None = None,
    to_date: date | None = None,
    department: str | None = None,
    _: None = require_permission("reports", "read"),
):
    svc = ReportingService(db)
    return await svc.pr_summary(from_date, to_date, department)


@router.get("/po-summary")
async def po_summary(
    current_user: CurrentUser,
    db: DBSession,
    from_date: date | None = None,
    to_date: date | None = None,
    _: None = require_permission("reports", "read"),
):
    svc = ReportingService(db)
    return await svc.po_summary(from_date, to_date)


@router.get("/vendor-performance")
async def vendor_performance(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(10, ge=1, le=50),
    _: None = require_permission("reports", "read"),
):
    svc = ReportingService(db)
    return await svc.vendor_performance(limit)


@router.get("/inventory-valuation")
async def inventory_valuation(
    current_user: CurrentUser,
    db: DBSession,
    _: None = require_permission("reports", "read"),
):
    svc = ReportingService(db)
    return await svc.inventory_valuation()


@router.get("/invoice-aging")
async def invoice_aging(
    current_user: CurrentUser,
    db: DBSession,
    _: None = require_permission("reports", "read"),
):
    svc = ReportingService(db)
    return await svc.invoice_aging()


@router.post("/exports")
async def trigger_export(
    current_user: CurrentUser,
    db: DBSession,
    report_type: str = "PR_SUMMARY",
    format: str = "xlsx",
):
    """Dispatch an async export job. Returns task_id to poll."""
    svc = ReportingService(db)
    task_id = await svc.trigger_export(
        report_type=report_type,
        format=format,
        filters={},
        requested_by_id=str(current_user.id),
    )
    return {"task_id": task_id, "message": "Export queued — poll /reports/exports/{task_id}"}
