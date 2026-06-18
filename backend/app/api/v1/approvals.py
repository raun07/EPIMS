"""Approval queue and action API."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.dependencies import CurrentUser
from app.core.unit_of_work import UnitOfWork
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class ApprovalActionRequest(BaseModel):
    action: str  # APPROVED | REJECTED | DELEGATED | RETURNED
    comments: str | None = None
    delegate_to_id: UUID | None = None


@router.get("/queue")
async def get_approval_queue(current_user: CurrentUser):
    """Return all approval instances pending action by the current user."""
    async with UnitOfWork() as uow:
        svc = ApprovalService(uow)
        return await svc.get_approval_queue(current_user.id)


@router.post("/{instance_id}/action")
async def process_action(
    instance_id: UUID,
    body: ApprovalActionRequest,
    current_user: CurrentUser,
):
    async with UnitOfWork() as uow:
        svc = ApprovalService(uow)
        result = await svc.process_action(
            instance_id=instance_id,
            approver_id=current_user.id,
            action=body.action,
            comments=body.comments,
            delegate_to_id=body.delegate_to_id,
        )
        await uow.commit()
    return result
