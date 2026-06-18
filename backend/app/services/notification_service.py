"""
Notification service — subscribes to domain events and dispatches in-app notifications.
Email is always delegated to Celery tasks to avoid blocking the request.

Event → Notification mapping:
  PRSubmittedEvent     → notify approver(s)
  PRApprovedEvent      → notify requester
  PRRejectedEvent      → notify requester
  POCreatedEvent       → notify procurement manager
  POReleasedEvent      → send PO email to vendor (via task)
  GRNPostedEvent       → notify AP team
  InvoiceMatchedEvent  → notify AP team + requester
  LowStockEvent        → notify warehouse manager
  ApprovalRequiredEvent → notify the assigned approver
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.core.events import (
    ApprovalRequiredEvent,
    GRNPostedEvent,
    InvoiceMatchedEvent,
    LowStockEvent,
    PRApprovedEvent,
    PRRejectedEvent,
    PRSubmittedEvent,
    POReleasedEvent,
    event_dispatcher,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.notification.models import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Handles in-app notification creation.
    Call NotificationService(uow).register() once on startup to wire event handlers.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def notify(
        self,
        recipient_id: UUID,
        event_type: str,
        title: str,
        message: str | None = None,
        reference_type: str | None = None,
        reference_id: UUID | None = None,
        channel: str = "IN_APP",
    ) -> Notification:
        notification = Notification(
            recipient_id=recipient_id,
            event_type=event_type,
            title=title,
            message=message,
            channel=channel,
            reference_type=reference_type,
            reference_id=reference_id,
        )
        self.uow.session.add(notification)
        await self.uow.session.flush()
        return notification

    async def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Notification], int]:
        items = await self.uow.notifications.get_for_user(
            user_id, unread_only=unread_only, page=page, per_page=per_page
        )
        total = await self.uow.notifications.count_unread(user_id)
        return list(items), total

    async def mark_read(self, notification_id: UUID, user_id: UUID) -> Notification:
        from datetime import UTC, datetime
        n = await self.uow.notifications.get_or_raise(notification_id)
        if not n.is_read:
            n.is_read = True
            n.read_at = datetime.now(UTC)
            await self.uow.notifications.save(n)
        return n

    async def mark_all_read(self, user_id: UUID) -> None:
        await self.uow.notifications.mark_all_read(user_id)

    async def unread_count(self, user_id: UUID) -> int:
        return await self.uow.notifications.count_unread(user_id)


# ── Standalone event handlers (registered at startup) ─────────────────────────
# These are module-level functions that receive events and create notifications
# using a fresh UoW per handler invocation.

async def _on_pr_submitted(event: PRSubmittedEvent) -> None:
    """Notify all users with 'approver' role when a PR is submitted."""
    try:
        async with UnitOfWork() as uow:
            from sqlalchemy import select
            from app.domain.auth.models import Role, User, user_roles
            stmt = (
                select(User.id)
                .join(user_roles, User.id == user_roles.c.user_id)
                .join(Role, user_roles.c.role_id == Role.id)
                .where(Role.name.in_(["approver", "procurement_manager"]), User.is_active == True)  # noqa: E712
            )
            result = await uow.session.execute(stmt)
            approver_ids = [row[0] for row in result.all()]

            svc = NotificationService(uow)
            for approver_id in approver_ids:
                await svc.notify(
                    recipient_id=approver_id,
                    event_type="PR_SUBMITTED",
                    title=f"PR {event.pr_number} awaiting your approval",
                    message=(
                        f"A purchase requisition for "
                        f"{event.currency} {event.total_value:,.2f} "
                        f"requires your approval."
                    ),
                    reference_type="PR",
                    reference_id=UUID(event.pr_id),
                )
            await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create PR_SUBMITTED notifications: %s", exc)


async def _on_pr_approved(event: PRApprovedEvent) -> None:
    try:
        async with UnitOfWork() as uow:
            pr = await uow.purchase_requisitions.get(UUID(event.pr_id))
            if pr is None:
                return
            svc = NotificationService(uow)
            await svc.notify(
                recipient_id=pr.requested_by,
                event_type="PR_APPROVED",
                title=f"PR {event.pr_number} has been approved",
                message="Your purchase requisition has been approved and is ready for PO creation.",
                reference_type="PR",
                reference_id=UUID(event.pr_id),
            )
            await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create PR_APPROVED notification: %s", exc)


async def _on_pr_rejected(event: PRRejectedEvent) -> None:
    try:
        async with UnitOfWork() as uow:
            pr = await uow.purchase_requisitions.get(UUID(event.pr_id))
            if pr is None:
                return
            svc = NotificationService(uow)
            await svc.notify(
                recipient_id=pr.requested_by,
                event_type="PR_REJECTED",
                title=f"PR {event.pr_number} was returned for revision",
                message=f"Reason: {event.reason}",
                reference_type="PR",
                reference_id=UUID(event.pr_id),
            )
            await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create PR_REJECTED notification: %s", exc)


async def _on_approval_required(event: ApprovalRequiredEvent) -> None:
    try:
        async with UnitOfWork() as uow:
            svc = NotificationService(uow)
            await svc.notify(
                recipient_id=UUID(event.approver_id),
                event_type="APPROVAL_REQUIRED",
                title=f"Action required: {event.document_type} approval",
                message=f"{event.document_type} {event.document_number} is awaiting your decision.",
                reference_type=event.document_type,
                reference_id=UUID(event.document_id),
            )
            await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create APPROVAL_REQUIRED notification: %s", exc)


async def _on_grn_posted(event: GRNPostedEvent) -> None:
    """Notify AP team that a GRN was posted — invoicing can begin."""
    try:
        async with UnitOfWork() as uow:
            from sqlalchemy import select
            from app.domain.auth.models import Role, User, user_roles
            stmt = (
                select(User.id)
                .join(user_roles, User.id == user_roles.c.user_id)
                .join(Role, user_roles.c.role_id == Role.id)
                .where(Role.name == "accounts_payable", User.is_active == True)  # noqa: E712
            )
            result = await uow.session.execute(stmt)
            ap_ids = [row[0] for row in result.all()]

            svc = NotificationService(uow)
            for ap_id in ap_ids:
                await svc.notify(
                    recipient_id=ap_id,
                    event_type="GRN_POSTED",
                    title=f"GRN {event.grn_number} posted — invoice can be matched",
                    message=f"Goods worth {event.total_value:,.2f} have been received and posted.",
                    reference_type="GRN",
                    reference_id=UUID(event.grn_id),
                )
            await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create GRN_POSTED notifications: %s", exc)


async def _on_low_stock(event: LowStockEvent) -> None:
    try:
        async with UnitOfWork() as uow:
            wh = await uow.warehouses.get(UUID(event.warehouse_id))
            if wh and wh.manager_id:
                svc = NotificationService(uow)
                await svc.notify(
                    recipient_id=wh.manager_id,
                    event_type="LOW_STOCK",
                    title=f"Low stock: {event.material_number}",
                    message=(
                        f"Stock for {event.material_number} in warehouse "
                        f"{event.warehouse_id} is below reorder point "
                        f"({event.current_qty:.3f} < {event.reorder_point:.3f})."
                    ),
                    reference_type="MATERIAL",
                    reference_id=UUID(event.material_id),
                )
                await uow.commit()
    except Exception as exc:
        logger.exception("Failed to create LOW_STOCK notification: %s", exc)


def register_notification_handlers() -> None:
    """Call this once at FastAPI startup to wire all handlers."""
    event_dispatcher.subscribe(PRSubmittedEvent, _on_pr_submitted)
    event_dispatcher.subscribe(PRApprovedEvent, _on_pr_approved)
    event_dispatcher.subscribe(PRRejectedEvent, _on_pr_rejected)
    event_dispatcher.subscribe(ApprovalRequiredEvent, _on_approval_required)
    event_dispatcher.subscribe(GRNPostedEvent, _on_grn_posted)
    event_dispatcher.subscribe(LowStockEvent, _on_low_stock)
    logger.info("Notification event handlers registered")
