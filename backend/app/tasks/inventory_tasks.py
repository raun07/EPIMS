"""Inventory Celery tasks."""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.inventory_tasks.check_low_stock")
def check_low_stock() -> dict:
    """
    Celery beat task: query all materials below reorder point and emit events.
    """
    async def _run():
        from app.core.unit_of_work import UnitOfWork
        from app.services.inventory_service import InventoryService

        async with UnitOfWork() as uow:
            svc = InventoryService(uow)
            alerts = await svc.get_low_stock_alerts()
            await uow.commit()
        return {"low_stock_count": len(alerts)}

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.inventory_tasks.auto_create_reorder_pr")
def auto_create_reorder_pr(material_id: str, warehouse_id: str) -> dict:
    """
    Optionally auto-create a PR for low-stock items (configured per material).
    Currently a placeholder — production systems would check material's
    preferred vendor and auto-PR settings.
    """
    logger.info(
        "Reorder PR requested for material=%s warehouse=%s",
        material_id, warehouse_id
    )
    return {"queued": True, "material_id": material_id}
