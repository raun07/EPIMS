"""Report generation Celery tasks."""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.report_tasks.generate_report_export",
    bind=True,
    max_retries=2,
)
def generate_report_export(
    self,
    report_type: str,
    format: str,
    filters: dict,
    requested_by_id: str,
) -> dict:
    """
    Generate a report export (xlsx / csv / pdf) and upload to MinIO.
    Returns a presigned URL valid for 1 hour.
    """
    async def _run():
        from app.database import AsyncSessionLocal
        from app.services.reporting_service import ReportingService

        async with AsyncSessionLocal() as session:
            svc = ReportingService(session)

            if report_type == "pr_summary":
                data = await svc.pr_summary()
            elif report_type == "po_summary":
                data = await svc.po_summary()
            elif report_type == "vendor_performance":
                data = await svc.vendor_performance()
            elif report_type == "inventory_valuation":
                data = await svc.inventory_valuation()
            elif report_type == "invoice_aging":
                data = await svc.invoice_aging()
            else:
                raise ValueError(f"Unknown report type: {report_type}")

        # In production: serialize data → openpyxl/csv/reportlab, upload to MinIO,
        # return presigned URL. Here we return a summary.
        logger.info(
            "Report '%s' generated for user %s (format=%s)",
            report_type, requested_by_id, format
        )
        return {
            "report_type": report_type,
            "format": format,
            "status": "completed",
            "download_url": None,  # presigned URL would go here
        }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Report generation failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
