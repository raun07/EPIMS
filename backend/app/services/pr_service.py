"""
Purchase Requisition service.

State machine:
  DRAFT → SUBMITTED → PENDING_APPROVAL → APPROVED → PO_CREATED | CANCELLED

Business rules enforced here:
  - Only the requester (or superuser) can edit a DRAFT PR
  - Submitting triggers the approval workflow
  - Approval sets approved_at timestamp
  - Cancellation is allowed up to APPROVED status
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.events import (
    PRApprovedEvent,
    PRRejectedEvent,
    PRSubmittedEvent,
    event_dispatcher,
)
from app.core.exceptions import (
    DomainException,
    InvalidStatusTransition,
    NotFoundException,
    PermissionDenied,
)
from app.core.unit_of_work import UnitOfWork
from app.domain.procurement.models import PR_STATUS_TRANSITIONS, PRItem, PRStatus, PurchaseRequisition
from app.utils.number_gen import generate_pr_number


class PRService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_pr(
        self,
        title: str,
        description: str | None,
        requested_by_id: UUID,
        items: list[dict],
        priority: str = "NORMAL",
        required_date=None,
        cost_center: str | None = None,
        department: str | None = None,
        warehouse_id: UUID | None = None,
        notes: str | None = None,
    ) -> PurchaseRequisition:
        """Create a PR in DRAFT status with line items."""
        pr_number = await generate_pr_number(self.uow.session)

        pr = await self.uow.purchase_requisitions.create(
            {
                "pr_number": pr_number,
                "title": title,
                "description": description,
                "requested_by": requested_by_id,
                "status": PRStatus.DRAFT,
                "priority": priority,
                "required_date": required_date,
                "cost_center": cost_center,
                "department": department,
                "warehouse_id": warehouse_id,
                "notes": notes,
            }
        )

        # Create line items
        for idx, item_data in enumerate(items, start=1):
            item = PRItem(
                pr_id=pr.id,
                line_number=idx,
                material_id=item_data.get("material_id"),
                description=item_data["description"],
                quantity=Decimal(str(item_data["quantity"])),
                uom_id=item_data.get("uom_id"),
                estimated_price=Decimal(str(item_data["estimated_price"])) if item_data.get("estimated_price") else None,
                required_date=item_data.get("required_date"),
                preferred_vendor_id=item_data.get("preferred_vendor_id"),
                specifications=item_data.get("specifications"),
            )
            if item.estimated_price:
                item.estimated_value = item.quantity * item.estimated_price
            self.uow.session.add(item)

        await self.uow.session.flush()

        # Recalculate header total from the input data (avoids lazy-load on detached relationship)
        total = Decimal("0")
        for item_data in items:
            qty = Decimal(str(item_data.get("quantity", 0)))
            price = Decimal(str(item_data.get("estimated_price", 0) or 0))
            total += qty * price
        pr.total_value = total
        await self.uow.session.flush()

        # Audit
        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="CREATE",
            performed_by=requested_by_id,
            new_values={"pr_number": pr_number, "status": PRStatus.DRAFT},
        )

        return pr

    async def submit_pr(self, pr_id: UUID, submitted_by_id: UUID) -> PurchaseRequisition:
        """Submit PR for approval. Requester or superuser only."""
        pr = await self.uow.purchase_requisitions.get_with_items(pr_id)
        if pr is None:
            raise NotFoundException("PurchaseRequisition", str(pr_id))

        requester = await self.uow.users.get(submitted_by_id)
        if not requester:
            raise NotFoundException("User", str(submitted_by_id))

        if not requester.is_superuser and pr.requested_by != submitted_by_id:
            raise PermissionDenied("submit", "PurchaseRequisition")

        if not pr.can_transition_to(PRStatus.SUBMITTED):
            raise InvalidStatusTransition("PurchaseRequisition", pr.status, PRStatus.SUBMITTED)

        if not pr.items:
            raise DomainException("Cannot submit a PR with no line items")

        old_status = pr.status
        pr.status = PRStatus.SUBMITTED
        pr.submitted_at = datetime.now(UTC)
        await self.uow.session.flush()

        # Trigger approval workflow
        from app.services.approval_service import ApprovalService
        approval_svc = ApprovalService(self.uow)
        await approval_svc.start_workflow(
            document_type="PR",
            document_id=pr.id,
            document_value=pr.total_value,
            requester_id=submitted_by_id,
        )

        # Update PR status to PENDING_APPROVAL
        pr.status = PRStatus.PENDING_APPROVAL
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="STATUS_CHANGE",
            performed_by=submitted_by_id,
            old_values={"status": old_status},
            new_values={"status": pr.status},
        )

        await event_dispatcher.emit(
            PRSubmittedEvent(
                pr_id=str(pr.id),
                pr_number=pr.pr_number,
                requested_by_id=str(submitted_by_id),
                total_value=float(pr.total_value),
                currency=pr.currency,
            )
        )

        return pr

    async def approve_pr(self, pr_id: UUID, approved_by_id: UUID) -> PurchaseRequisition:
        """Mark PR as approved (called by approval engine after all steps pass)."""
        pr = await self.uow.purchase_requisitions.get_or_raise(pr_id)
        if not pr.can_transition_to(PRStatus.APPROVED):
            raise InvalidStatusTransition("PurchaseRequisition", pr.status, PRStatus.APPROVED)

        old_status = pr.status
        pr.status = PRStatus.APPROVED
        pr.approved_at = datetime.now(UTC)
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="STATUS_CHANGE",
            performed_by=approved_by_id,
            old_values={"status": old_status},
            new_values={"status": PRStatus.APPROVED},
        )

        await event_dispatcher.emit(
            PRApprovedEvent(
                pr_id=str(pr.id),
                pr_number=pr.pr_number,
                approved_by_id=str(approved_by_id),
            )
        )

        return pr

    async def reject_pr(
        self, pr_id: UUID, rejected_by_id: UUID, reason: str
    ) -> PurchaseRequisition:
        """Return PR to DRAFT with rejection reason (called by approval engine)."""
        pr = await self.uow.purchase_requisitions.get_or_raise(pr_id)

        old_status = pr.status
        pr.status = PRStatus.DRAFT
        pr.rejection_reason = reason
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="STATUS_CHANGE",
            performed_by=rejected_by_id,
            old_values={"status": old_status},
            new_values={"status": PRStatus.DRAFT, "rejection_reason": reason},
        )

        await event_dispatcher.emit(
            PRRejectedEvent(
                pr_id=str(pr.id),
                pr_number=pr.pr_number,
                rejected_by_id=str(rejected_by_id),
                reason=reason,
            )
        )

        return pr

    async def cancel_pr(self, pr_id: UUID, cancelled_by_id: UUID) -> PurchaseRequisition:
        pr = await self.uow.purchase_requisitions.get_or_raise(pr_id)
        if not pr.can_transition_to(PRStatus.CANCELLED):
            raise InvalidStatusTransition("PurchaseRequisition", pr.status, PRStatus.CANCELLED)

        old_status = pr.status
        pr.status = PRStatus.CANCELLED
        await self.uow.session.flush()

        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="STATUS_CHANGE",
            performed_by=cancelled_by_id,
            old_values={"status": old_status},
            new_values={"status": PRStatus.CANCELLED},
        )

        return pr

    async def get_pr(self, pr_id: UUID) -> PurchaseRequisition:
        pr = await self.uow.purchase_requisitions.get_with_items(pr_id)
        if pr is None:
            raise NotFoundException("PurchaseRequisition", str(pr_id))
        return pr

    async def list_prs(
        self,
        page: int = 1,
        per_page: int = 20,
        status: str | None = None,
        requester_id: UUID | None = None,
    ) -> tuple[list[PurchaseRequisition], int]:
        filters = []
        if status:
            filters.append(PurchaseRequisition.status == status)
        if requester_id:
            filters.append(PurchaseRequisition.requested_by == requester_id)

        from app.domain.procurement.models import PurchaseRequisition as PR
        items = await self.uow.purchase_requisitions.list(
            *filters,
            order_by=PR.created_at.desc(),
            page=page,
            per_page=per_page,
        )
        total = await self.uow.purchase_requisitions.count(*filters)
        return list(items), total

    async def update_pr(
        self, pr_id: UUID, user_id: UUID, update_data: dict
    ) -> PurchaseRequisition:
        """Update a DRAFT PR. Only requester or superuser."""
        pr = await self.uow.purchase_requisitions.get_with_items(pr_id)
        if pr is None:
            raise NotFoundException("PurchaseRequisition", str(pr_id))

        user = await self.uow.users.get(user_id)
        if not user or (not user.is_superuser and pr.requested_by != user_id):
            raise PermissionDenied("update", "PurchaseRequisition")

        if pr.status != PRStatus.DRAFT:
            raise DomainException("Only DRAFT PRs can be edited")

        allowed = {"title", "description", "priority", "required_date",
                   "cost_center", "department", "warehouse_id", "notes"}
        filtered = {k: v for k, v in update_data.items() if k in allowed}

        old_values = {k: str(getattr(pr, k)) for k in filtered}
        updated = await self.uow.purchase_requisitions.update(pr, filtered)

        await self.uow.audit.log(
            entity_type="PurchaseRequisition",
            entity_id=pr.id,
            action="UPDATE",
            performed_by=user_id,
            old_values=old_values,
            new_values=filtered,
            changed_fields=list(filtered.keys()),
        )

        return updated
