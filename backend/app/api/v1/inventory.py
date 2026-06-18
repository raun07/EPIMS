"""Inventory API endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, require_permission
from app.core.unit_of_work import UnitOfWork
from app.database import get_db
from app.schemas.inventory import (
    InitialStockRequest,
    LowStockAlert,
    StockIssueRequest,
    StockMovementResponse,
    StockResponse,
    StockTransferRequest,
)
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("/materials/{material_id}/stock", response_model=list[StockResponse])
async def get_material_stock(
    material_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("inventory", "read"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        return await svc.get_stock_overview(material_id)


@router.get("/warehouses/{warehouse_id}/stock", response_model=list[StockResponse])
async def get_warehouse_stock(
    warehouse_id: UUID,
    current_user: CurrentUser,
    _: None = require_permission("inventory", "read"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        return await svc.get_warehouse_stock(warehouse_id)


@router.get("/alerts/low-stock", response_model=list[LowStockAlert])
async def get_low_stock_alerts(
    current_user: CurrentUser,
    _: None = require_permission("inventory", "read"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        return await svc.get_low_stock_alerts()


@router.get("/materials/{material_id}/movements", response_model=list[StockMovementResponse])
async def get_stock_movements(
    material_id: UUID,
    current_user: CurrentUser,
    page: int = 1,
    per_page: int = 50,
    _: None = require_permission("inventory", "read"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        return await svc.get_stock_movements(material_id, page=page, per_page=per_page)


@router.post("/transfer", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def transfer_stock(
    body: StockTransferRequest,
    current_user: CurrentUser,
    _: None = require_permission("inventory", "transfer"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        movement = await svc.transfer_stock(
            material_id=body.material_id,
            quantity=body.quantity,
            from_warehouse_id=body.from_warehouse_id,
            to_warehouse_id=body.to_warehouse_id,
            transferred_by_id=current_user.id,
            from_location_id=body.from_location_id,
            to_location_id=body.to_location_id,
            batch_number=body.batch_number,
            reason=body.reason,
        )
        await uow.commit()
    return movement


@router.post("/issue", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def issue_stock(
    body: StockIssueRequest,
    current_user: CurrentUser,
    _: None = require_permission("inventory", "issue"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        movement = await svc.issue_stock(
            material_id=body.material_id,
            quantity=body.quantity,
            warehouse_id=body.warehouse_id,
            issued_by_id=current_user.id,
            movement_type=body.movement_type,
            location_id=body.location_id,
            batch_number=body.batch_number,
            reference_doc_type=body.reference_doc_type,
            reference_doc_id=body.reference_doc_id,
            reason=body.reason,
        )
        await uow.commit()
    return movement


@router.post("/initial-stock", response_model=StockMovementResponse, status_code=status.HTTP_201_CREATED)
async def post_initial_stock(
    body: InitialStockRequest,
    current_user: CurrentUser,
    _: None = require_permission("inventory", "adjust"),
):
    async with UnitOfWork() as uow:
        svc = InventoryService(uow)
        movement = await svc.post_initial_stock(
            material_id=body.material_id,
            warehouse_id=body.warehouse_id,
            quantity=body.quantity,
            unit_price=body.unit_price,
            currency=body.currency,
            posted_by_id=current_user.id,
            location_id=body.location_id,
            batch_number=body.batch_number,
            uom_id=body.uom_id,
        )
        await uow.commit()
    return movement
