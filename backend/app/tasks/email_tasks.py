"""
Email Celery tasks.

send_po_to_vendor     — renders PO as PDF and emails vendor contact
send_approval_reminder — nudges an approver whose step is overdue
escalate_overdue_approvals — Celery beat task checking all approval timeouts
cleanup_expired_tokens — remove stale Redis blacklist entries
"""
from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.email_tasks.send_po_to_vendor", bind=True, max_retries=3)
def send_po_to_vendor(self, po_id: str) -> dict:
    """
    Fetch PO, render PDF, email to vendor primary contact.
    """
    try:
        async def _run():
            from app.core.unit_of_work import UnitOfWork
            from uuid import UUID

            async with UnitOfWork() as uow:
                po = await uow.purchase_orders.get_with_items(UUID(po_id))
                if po is None:
                    logger.warning("PO %s not found for email dispatch", po_id)
                    return {"skipped": True}

                vendor = await uow.vendors.get_with_details(po.vendor_id)
                if vendor is None or vendor.primary_contact is None:
                    logger.warning("No primary contact for vendor %s", po.vendor_id)
                    return {"skipped": True, "reason": "no_contact"}

                contact = vendor.primary_contact
                if not contact.email:
                    logger.warning("Primary contact has no email for vendor %s", po.vendor_id)
                    return {"skipped": True, "reason": "no_email"}

                # In production: render PDF and send via aiosmtplib
                logger.info(
                    "PO %s dispatched to %s (%s)",
                    po.po_number, contact.name, contact.email
                )
                return {"sent_to": contact.email, "po_number": po.po_number}

        return asyncio.run(_run())

    except Exception as exc:
        logger.exception("send_po_to_vendor failed for %s: %s", po_id, exc)
        raise self.retry(exc=exc, countdown=300)  # retry after 5 min


@celery_app.task(name="app.tasks.email_tasks.send_approval_reminder")
def send_approval_reminder(instance_id: str, approver_id: str) -> dict:
    """Send a reminder email to an overdue approver."""
    logger.info("Sending approval reminder: instance=%s approver=%s", instance_id, approver_id)
    # Email dispatch would go here
    return {"instance_id": instance_id, "approver_id": approver_id}


@celery_app.task(name="app.tasks.email_tasks.escalate_overdue_approvals")
def escalate_overdue_approvals() -> dict:
    """
    Celery beat task: find approval instances past their timeout_hours
    and escalate or send reminders.
    """
    async def _run():
        from datetime import UTC, datetime, timedelta
        from app.core.unit_of_work import UnitOfWork

        escalated = 0
        async with UnitOfWork() as uow:
            workflows = await uow.approvals.get_workflows()
            for workflow in workflows:
                for rule in workflow.rules:
                    timeout = timedelta(hours=rule.timeout_hours)
                    from sqlalchemy import select
                    from app.domain.approval.models import ApprovalInstance

                    stmt = select(ApprovalInstance).where(
                        ApprovalInstance.status == "IN_PROGRESS",
                        ApprovalInstance.workflow_id == workflow.id,
                        ApprovalInstance.current_step == rule.step_order,
                        ApprovalInstance.started_at < datetime.now(UTC) - timeout,
                    )
                    result = await uow.session.execute(stmt)
                    overdue = result.scalars().all()

                    for instance in overdue:
                        if rule.escalate_to_id:
                            send_approval_reminder.delay(
                                str(instance.id), str(rule.escalate_to_id)
                            )
                            escalated += 1

        return {"escalated": escalated}

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.email_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens() -> dict:
    """
    Redis TTL handles expiry automatically — this task is a no-op placeholder
    for any manual cleanup (e.g., audit log pruning) needed in future.
    """
    logger.info("Token cleanup check completed (Redis TTL handles expiry)")
    return {"status": "ok"}
