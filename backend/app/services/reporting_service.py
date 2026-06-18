"""
Reporting service — KPI dashboard + export.

All queries use raw SQLAlchemy for performance (no N+1).
Exports are dispatched as Celery tasks; the endpoint returns a task_id
which the client polls via GET /reports/exports/{task_id}.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession


class ReportingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Procurement KPIs ──────────────────────────────────────────────────────

    async def pr_summary(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        department: str | None = None,
    ) -> dict:
        """Total PRs by status, total value, average approval time."""
        from app.domain.procurement.models import PurchaseRequisition

        stmt = select(
            PurchaseRequisition.status,
            func.count(PurchaseRequisition.id).label("count"),
            func.sum(PurchaseRequisition.total_value).label("total_value"),
            func.avg(
                func.extract(
                    "epoch",
                    PurchaseRequisition.approved_at - PurchaseRequisition.submitted_at,
                )
            ).label("avg_approval_seconds"),
        ).group_by(PurchaseRequisition.status)

        if from_date:
            stmt = stmt.where(PurchaseRequisition.created_at >= from_date)
        if to_date:
            stmt = stmt.where(PurchaseRequisition.created_at <= to_date)
        if department:
            stmt = stmt.where(PurchaseRequisition.department == department)

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            "by_status": [
                {
                    "status": row.status,
                    "count": row.count,
                    "total_value": float(row.total_value or 0),
                    "avg_approval_hours": (
                        round(row.avg_approval_seconds / 3600, 1)
                        if row.avg_approval_seconds
                        else None
                    ),
                }
                for row in rows
            ]
        }

    async def po_summary(
        self,
        from_date: date | None = None,
        to_date: date | None = None,
        vendor_id: UUID | None = None,
    ) -> dict:
        """PO volume, value, on-time delivery rate."""
        from app.domain.procurement.models import PurchaseOrder

        stmt = select(
            PurchaseOrder.status,
            func.count(PurchaseOrder.id).label("count"),
            func.sum(PurchaseOrder.total_amount).label("total_value"),
        ).group_by(PurchaseOrder.status)

        if from_date:
            stmt = stmt.where(PurchaseOrder.order_date >= from_date)
        if to_date:
            stmt = stmt.where(PurchaseOrder.order_date <= to_date)
        if vendor_id:
            stmt = stmt.where(PurchaseOrder.vendor_id == vendor_id)

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            "by_status": [
                {
                    "status": row.status,
                    "count": row.count,
                    "total_value": float(row.total_value or 0),
                }
                for row in rows
            ]
        }

    async def vendor_performance(self, limit: int = 10) -> list[dict]:
        """Top vendors by PO volume and on-time delivery."""
        from app.domain.procurement.models import GoodsReceipt, PurchaseOrder
        from app.domain.vendor.models import Vendor

        stmt = (
            select(
                Vendor.id,
                Vendor.name,
                Vendor.vendor_number,
                func.count(PurchaseOrder.id).label("po_count"),
                func.sum(PurchaseOrder.total_amount).label("total_spend"),
                func.avg(Vendor.rating).label("avg_rating"),
            )
            .join(PurchaseOrder, PurchaseOrder.vendor_id == Vendor.id)
            .group_by(Vendor.id, Vendor.name, Vendor.vendor_number)
            .order_by(func.sum(PurchaseOrder.total_amount).desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return [
            {
                "vendor_id": str(row.id),
                "vendor_number": row.vendor_number,
                "name": row.name,
                "po_count": row.po_count,
                "total_spend": float(row.total_spend or 0),
                "avg_rating": float(row.avg_rating or 0),
            }
            for row in result.all()
        ]

    async def inventory_valuation(self, warehouse_id: UUID | None = None) -> dict:
        """Total inventory value by warehouse."""
        from app.domain.inventory.models import InventoryStock
        from app.domain.material.models import Material
        from app.domain.warehouse.models import Warehouse

        stmt = select(
            Warehouse.code.label("warehouse_code"),
            Warehouse.name.label("warehouse_name"),
            func.count(InventoryStock.id).label("line_count"),
            func.sum(InventoryStock.quantity * InventoryStock.valuation_price).label(
                "total_value"
            ),
        ).join(Warehouse, InventoryStock.warehouse_id == Warehouse.id).group_by(
            Warehouse.code, Warehouse.name
        )

        if warehouse_id:
            stmt = stmt.where(InventoryStock.warehouse_id == warehouse_id)

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            "warehouses": [
                {
                    "code": row.warehouse_code,
                    "name": row.warehouse_name,
                    "line_count": row.line_count,
                    "total_value": float(row.total_value or 0),
                }
                for row in rows
            ],
            "grand_total": sum(float(r.total_value or 0) for r in rows),
        }

    async def invoice_aging(self) -> list[dict]:
        """Outstanding invoices grouped by aging bucket."""
        from app.domain.invoice.models import Invoice, InvoiceStatus

        today = date.today()

        stmt = select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.invoice_date,
            Invoice.due_date,
            Invoice.total_amount,
            Invoice.paid_amount,
            Invoice.status,
            (Invoice.total_amount - Invoice.paid_amount).label("balance"),
            (func.current_date() - Invoice.due_date).label("days_overdue"),
        ).where(
            Invoice.status.in_([InvoiceStatus.MATCHED, InvoiceStatus.APPROVED]),
            Invoice.paid_amount < Invoice.total_amount,
        )

        result = await self.session.execute(stmt)
        rows = result.all()

        buckets = {"0-30": [], "31-60": [], "61-90": [], "90+": []}
        for row in rows:
            days = (today - row.due_date).days if row.due_date else 0
            entry = {
                "invoice_number": row.invoice_number,
                "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
                "due_date": row.due_date.isoformat() if row.due_date else None,
                "balance": float(row.balance or 0),
                "days_overdue": max(days, 0),
            }
            if days <= 30:
                buckets["0-30"].append(entry)
            elif days <= 60:
                buckets["31-60"].append(entry)
            elif days <= 90:
                buckets["61-90"].append(entry)
            else:
                buckets["90+"].append(entry)

        return [
            {
                "bucket": k,
                "count": len(v),
                "total_balance": sum(e["balance"] for e in v),
                "invoices": v,
            }
            for k, v in buckets.items()
        ]

    async def dashboard_kpis(self) -> dict:
        """Single call for the main dashboard widget data."""
        from app.domain.invoice.models import Invoice, InvoiceStatus
        from app.domain.inventory.models import InventoryStock
        from app.domain.material.models import Material
        from app.domain.procurement.models import PurchaseOrder, PurchaseRequisition

        # Active PRs pending approval
        pr_stmt = select(func.count(PurchaseRequisition.id)).where(
            PurchaseRequisition.status == "PENDING_APPROVAL"
        )

        # Open POs value
        po_stmt = select(func.sum(PurchaseOrder.total_amount)).where(
            PurchaseOrder.status.in_(["RELEASED", "SENT", "PARTIALLY_RECEIVED"])
        )

        # Overdue invoices
        inv_stmt = select(func.count(Invoice.id)).where(
            Invoice.status.in_([InvoiceStatus.MATCHED, InvoiceStatus.APPROVED]),
            Invoice.due_date < date.today(),
            Invoice.paid_amount < Invoice.total_amount,
        )

        # Low stock alerts count
        ls_stmt = (
            select(func.count(InventoryStock.id))
            .join(Material, InventoryStock.material_id == Material.id)
            .where(
                InventoryStock.stock_type == "UNRESTRICTED",
                Material.reorder_point != None,  # noqa: E711
                InventoryStock.quantity <= Material.reorder_point,
            )
        )

        pr_result = await self.session.execute(pr_stmt)
        po_result = await self.session.execute(po_stmt)
        inv_result = await self.session.execute(inv_stmt)
        ls_result = await self.session.execute(ls_stmt)

        return {
            "pending_pr_approvals": pr_result.scalar_one() or 0,
            "open_po_value": float(po_result.scalar_one() or 0),
            "overdue_invoices": inv_result.scalar_one() or 0,
            "low_stock_alerts": ls_result.scalar_one() or 0,
        }

    # ── Async export dispatcher ───────────────────────────────────────────────

    async def trigger_export(
        self,
        report_type: str,
        format: str,
        filters: dict,
        requested_by_id: str,
    ) -> str:
        """
        Dispatch an export job to Celery. Returns task_id for polling.
        """
        try:
            from app.tasks.report_tasks import generate_report_export
            task = generate_report_export.delay(
                report_type=report_type,
                format=format,
                filters=filters,
                requested_by_id=requested_by_id,
            )
            return task.id
        except Exception as exc:
            raise RuntimeError(f"Export task dispatch failed: {exc}") from exc
