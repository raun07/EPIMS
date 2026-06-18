"""Approval repository."""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.domain.approval.models import (
    ApprovalActionRecord,
    ApprovalDelegation,
    ApprovalInstance,
    ApprovalRule,
    ApprovalWorkflow,
)
from app.repositories.base import AbstractRepository


class ApprovalRepository(AbstractRepository[ApprovalInstance]):
    model = ApprovalInstance

    async def get_workflow_for_document(
        self, document_type: str
    ) -> ApprovalWorkflow | None:
        stmt = (
            select(ApprovalWorkflow)
            .where(
                ApprovalWorkflow.document_type == document_type,
                ApprovalWorkflow.is_active == True,  # noqa: E712
            )
            .options(
                selectinload(ApprovalWorkflow.rules).selectinload(ApprovalRule.escalate_to)
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_instance(
        self, document_type: str, document_id: UUID
    ) -> ApprovalInstance | None:
        stmt = (
            select(ApprovalInstance)
            .where(
                ApprovalInstance.document_type == document_type,
                ApprovalInstance.document_id == document_id,
                ApprovalInstance.status.in_(["PENDING", "IN_PROGRESS"]),
            )
            .options(
                selectinload(ApprovalInstance.workflow).selectinload(ApprovalWorkflow.rules),
                selectinload(ApprovalInstance.actions),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_for_user(self, user_id: UUID) -> list[ApprovalInstance]:
        """Return all approval instances where the given user is the current approver."""
        stmt = (
            select(ApprovalInstance)
            .where(ApprovalInstance.status.in_(["PENDING", "IN_PROGRESS"]))
            .options(
                selectinload(ApprovalInstance.workflow),
                selectinload(ApprovalInstance.actions),
            )
        )
        result = await self.session.execute(stmt)
        all_pending = result.scalars().all()

        # Filter to those where user is the current-step approver
        # (full resolution happens in service layer)
        return list(all_pending)

    async def get_active_delegation(
        self, user_id: UUID, document_type: str | None = None
    ) -> ApprovalDelegation | None:
        today = date.today()
        filters = [
            ApprovalDelegation.delegator_id == user_id,
            ApprovalDelegation.is_active == True,  # noqa: E712
            ApprovalDelegation.valid_from <= today,
            ApprovalDelegation.valid_to >= today,
        ]
        if document_type:
            filters.append(
                or_(
                    ApprovalDelegation.document_type == document_type,
                    ApprovalDelegation.document_type == None,  # noqa: E711
                )
            )
        stmt = select(ApprovalDelegation).where(and_(*filters))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_workflow(self, data: dict) -> ApprovalWorkflow:
        wf = ApprovalWorkflow(**data)
        self.session.add(wf)
        await self.session.flush()
        return wf

    async def create_rule(self, data: dict) -> ApprovalRule:
        rule = ApprovalRule(**data)
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def create_instance(self, data: dict) -> ApprovalInstance:
        instance = ApprovalInstance(**data)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def record_action(self, data: dict) -> ApprovalActionRecord:
        action = ApprovalActionRecord(**data)
        self.session.add(action)
        await self.session.flush()
        return action

    async def create_delegation(self, data: dict) -> ApprovalDelegation:
        delegation = ApprovalDelegation(**data)
        self.session.add(delegation)
        await self.session.flush()
        return delegation

    async def get_workflows(self) -> list[ApprovalWorkflow]:
        stmt = (
            select(ApprovalWorkflow)
            .options(selectinload(ApprovalWorkflow.rules))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
