"""Approval Engine domain models."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ApproverType(str, Enum):
    USER = "USER"
    ROLE = "ROLE"
    MANAGER = "MANAGER"          # Requester's direct manager
    DEPARTMENT_HEAD = "DEPARTMENT_HEAD"
    COST_CENTER_OWNER = "COST_CENTER_OWNER"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalAction(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DELEGATED = "DELEGATED"
    RETURNED = "RETURNED"       # Returned for revision
    ESCALATED = "ESCALATED"


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)  # PR, PO, INVOICE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    rules: Mapped[list[ApprovalRule]] = relationship(
        "ApprovalRule", back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="ApprovalRule.step_order"
    )
    instances: Mapped[list[ApprovalInstance]] = relationship(
        "ApprovalInstance", back_populates="workflow"
    )

    def __repr__(self) -> str:
        return f"<ApprovalWorkflow {self.name} [{self.document_type}]>"


class ApprovalRule(Base):
    __tablename__ = "approval_rules"
    __table_args__ = (
        UniqueConstraint("workflow_id", "step_order", name="uq_approval_rules_workflow_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_type: Mapped[str] = mapped_column(String(30), nullable=False)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # specific user
    approver_role: Mapped[str | None] = mapped_column(String(50))
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    department: Mapped[str | None] = mapped_column(String(100))
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    escalate_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )

    workflow: Mapped[ApprovalWorkflow] = relationship("ApprovalWorkflow", back_populates="rules")
    escalate_to: Mapped["User | None"] = relationship("User", foreign_keys=[escalate_to_id])  # noqa: F821

    def applies_to_amount(self, amount: Decimal) -> bool:
        """Check if this rule applies given a document value."""
        if self.min_amount is not None and amount < self.min_amount:
            return False
        if self.max_amount is not None and amount > self.max_amount:
            return False
        return True

    def __repr__(self) -> str:
        return f"<ApprovalRule step={self.step_order} type={self.approver_type}>"


class ApprovalInstance(Base):
    __tablename__ = "approval_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_workflows.id", ondelete="RESTRICT"), nullable=False
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.PENDING, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workflow: Mapped[ApprovalWorkflow] = relationship("ApprovalWorkflow", back_populates="instances")
    actions: Mapped[list[ApprovalActionRecord]] = relationship(
        "ApprovalActionRecord",
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="ApprovalActionRecord.acted_at"
    )

    @property
    def is_complete(self) -> bool:
        return self.status in (ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CANCELLED)

    def __repr__(self) -> str:
        return f"<ApprovalInstance doc={self.document_id} step={self.current_step} [{self.status}]>"


class ApprovalActionRecord(Base):
    """Records each approval decision (renamed from ApprovalAction to avoid clash with Enum)."""
    __tablename__ = "approval_actions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_instances.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_rules.id", ondelete="SET NULL")
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    delegated_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    acted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    instance: Mapped[ApprovalInstance] = relationship("ApprovalInstance", back_populates="actions")
    approver: Mapped["User"] = relationship("User", foreign_keys=[approver_id])  # noqa: F821
    delegated_to: Mapped["User | None"] = relationship("User", foreign_keys=[delegated_to_id])  # noqa: F821
    rule: Mapped[ApprovalRule | None] = relationship("ApprovalRule")

    def __repr__(self) -> str:
        return f"<ApprovalActionRecord step={self.step_order} action={self.action}>"


class ApprovalDelegation(Base):
    __tablename__ = "approval_delegations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delegator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False
    )
    delegate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[str | None] = mapped_column(String(30))  # NULL = all types
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    delegator: Mapped["User"] = relationship("User", foreign_keys=[delegator_id])  # noqa: F821
    delegate: Mapped["User"] = relationship("User", foreign_keys=[delegate_id])  # noqa: F821

    @property
    def is_currently_valid(self) -> bool:
        today = date.today()
        return self.is_active and self.valid_from <= today <= self.valid_to

    def __repr__(self) -> str:
        return f"<Delegation from={self.delegator_id} to={self.delegate_id}>"
