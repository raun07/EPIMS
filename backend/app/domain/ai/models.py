"""
AI Copilot domain models.

Six tables — one per capability — plus a master interaction log.
Every LLM call is stored: input, output JSON, tokens, latency, feedback.
This enables evaluation, auditing, cost tracking, and prompt improvement.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey,
    Integer, Numeric, SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class AICapability(str, Enum):
    NL_TO_PR = "NL_TO_PR"
    VENDOR_REC = "VENDOR_REC"
    POLICY_CHECK = "POLICY_CHECK"
    APPROVAL_SUMMARY = "APPROVAL_SUMMARY"
    ANALYTICS = "ANALYTICS"
    DOCUMENT_INTEL = "DOCUMENT_INTEL"


class AIStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class PolicySeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    BLOCK = "BLOCK"


class PolicyOverallStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


class AnalyticsIntent(str, Enum):
    VENDOR_PERFORMANCE = "VENDOR_PERFORMANCE"
    SPEND_ANALYSIS = "SPEND_ANALYSIS"
    INVENTORY_STATUS = "INVENTORY_STATUS"
    DEPARTMENT_SPEND = "DEPARTMENT_SPEND"
    DELIVERY_PERFORMANCE = "DELIVERY_PERFORMANCE"
    INVOICE_STATUS = "INVOICE_STATUS"


class DocExtractionStatus(str, Enum):
    EXTRACTED = "EXTRACTED"
    LINKED = "LINKED"
    REJECTED = "REJECTED"


class PRDraftStatus(str, Enum):
    DRAFT = "DRAFT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


# ── Master interaction log ────────────────────────────────────────────────────

class AIInteraction(Base):
    """Every LLM call gets one row here — the audit spine of the AI module."""
    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    input_text: Mapped[str | None] = mapped_column(Text)
    input_metadata: Mapped[dict | None] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    model_used: Mapped[str | None] = mapped_column(String(80))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=AIStatus.SUCCESS, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text)
    # User feedback
    feedback_score: Mapped[int | None] = mapped_column(SmallInteger)   # 1–5
    feedback_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships to capability-specific rows
    pr_draft: Mapped["AIPRDraft | None"] = relationship(back_populates="interaction", uselist=False)
    vendor_rec: Mapped["AIVendorRecommendation | None"] = relationship(back_populates="interaction", uselist=False)
    policy_check: Mapped["AIPolicyCheck | None"] = relationship(back_populates="interaction", uselist=False)
    approval_summary: Mapped["AIApprovalSummary | None"] = relationship(back_populates="interaction", uselist=False)
    analytics_query: Mapped["AIAnalyticsQuery | None"] = relationship(back_populates="interaction", uselist=False)
    doc_extraction: Mapped["AIDocumentExtraction | None"] = relationship(back_populates="interaction", uselist=False)


# ── ① NL→PR Draft ─────────────────────────────────────────────────────────────

class AIPRDraft(Base):
    """Stores the structured PR extracted from a natural language request."""
    __tablename__ = "ai_pr_drafts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pr_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="SET NULL")
    )
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_title: Mapped[str | None] = mapped_column(String(255))
    extracted_items: Mapped[list | None] = mapped_column(JSON)  # [{description, quantity, estimated_price, category}]
    extracted_department: Mapped[str | None] = mapped_column(String(100))
    extracted_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    extracted_required_date: Mapped[date | None] = mapped_column(Date)
    extracted_priority: Mapped[str | None] = mapped_column(String(20))
    business_justification: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    ambiguities: Mapped[list | None] = mapped_column(JSON)   # fields where AI was uncertain
    status: Mapped[str] = mapped_column(String(20), default=PRDraftStatus.DRAFT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    interaction: Mapped["AIInteraction"] = relationship(back_populates="pr_draft")


# ── ② Vendor Recommendations ──────────────────────────────────────────────────

class AIVendorRecommendation(Base):
    """Scored and ranked vendor list for a PR, with per-vendor explanations."""
    __tablename__ = "ai_vendor_recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pr_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="SET NULL")
    )
    material_category: Mapped[str | None] = mapped_column(String(100))
    # [{vendor_id, vendor_name, overall_score, price_score, delivery_score,
    #   quality_score, relationship_score, explanation, past_po_count, avg_delivery_days}]
    recommendations: Mapped[list | None] = mapped_column(JSON)
    data_snapshot: Mapped[dict | None] = mapped_column(JSON)  # context used (reproducibility)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    interaction: Mapped["AIInteraction"] = relationship(back_populates="vendor_rec")


# ── ③ Policy Check ────────────────────────────────────────────────────────────

class AIPolicyCheck(Base):
    """Pre-submission compliance analysis result for a PR."""
    __tablename__ = "ai_policy_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_status: Mapped[str] = mapped_column(String(10), nullable=False)  # PASS | WARN | BLOCK
    # [{rule_id, rule_name, severity, explanation, suggested_fix, reference}]
    violations: Mapped[list | None] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    overridden_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth_users.id", ondelete="SET NULL")
    )
    override_reason: Mapped[str | None] = mapped_column(Text)

    interaction: Mapped["AIInteraction"] = relationship(back_populates="policy_check")


# ── ④ Approval Summary ────────────────────────────────────────────────────────

class AIApprovalSummary(Base):
    """Executive summary generated for each PR to help approvers decide quickly."""
    __tablename__ = "ai_approval_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    pr_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_requisitions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    summary_text: Mapped[str | None] = mapped_column(Text)
    cost_impact: Mapped[str | None] = mapped_column(Text)
    business_value: Mapped[str | None] = mapped_column(Text)
    risk_flags: Mapped[list | None] = mapped_column(JSON)          # [{flag, severity, detail}]
    comparable_purchases: Mapped[list | None] = mapped_column(JSON) # similar past PRs
    recommendation: Mapped[str | None] = mapped_column(String(20))  # APPROVE | REVIEW | ESCALATE
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interaction: Mapped["AIInteraction"] = relationship(back_populates="approval_summary")


# ── ⑤ Analytics Query ─────────────────────────────────────────────────────────

class AIAnalyticsQuery(Base):
    """Audit log of every NL→SQL analytics request with full validation chain."""
    __tablename__ = "ai_analytics_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    user_question: Mapped[str] = mapped_column(Text, nullable=False)
    classified_intent: Mapped[str | None] = mapped_column(String(50))
    generated_sql: Mapped[str | None] = mapped_column(Text)
    sql_validated: Mapped[bool] = mapped_column(Boolean, default=False)
    allowed_tables_used: Mapped[list | None] = mapped_column(JSON)
    result_json: Mapped[list | None] = mapped_column(JSON)
    row_count: Mapped[int | None] = mapped_column(Integer)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    interaction: Mapped["AIInteraction"] = relationship(back_populates="analytics_query")


# ── ⑥ Document Intelligence ───────────────────────────────────────────────────

class AIDocumentExtraction(Base):
    """Stores PDF invoice extraction results before linking to invoice records."""
    __tablename__ = "ai_document_extractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="SET NULL")
    )
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_s3_key: Mapped[str | None] = mapped_column(String(500))
    extracted_invoice_number: Mapped[str | None] = mapped_column(String(100))
    extracted_vendor_name: Mapped[str | None] = mapped_column(String(255))
    extracted_po_number: Mapped[str | None] = mapped_column(String(100))
    extracted_date: Mapped[date | None] = mapped_column(Date)
    extracted_due_date: Mapped[date | None] = mapped_column(Date)
    # [{description, quantity, unit_price, amount, tax}]
    extracted_line_items: Mapped[list | None] = mapped_column(JSON)
    extracted_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    extracted_tax_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    extracted_currency: Mapped[str | None] = mapped_column(String(3))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    raw_extraction: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default=DocExtractionStatus.EXTRACTED, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    interaction: Mapped["AIInteraction"] = relationship(back_populates="doc_extraction")
