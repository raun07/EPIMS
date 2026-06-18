"""AI Copilot tables.

Revision ID: 002_ai_tables
Revises: 001
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002_ai_tables"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("ai_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.String(30), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="SET NULL")),
        sa.Column("input_text", sa.Text),
        sa.Column("input_metadata", postgresql.JSON),
        sa.Column("output_json", postgresql.JSON),
        sa.Column("model_used", sa.String(80)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("status", sa.String(20), nullable=False, server_default="SUCCESS"),
        sa.Column("error_detail", sa.Text),
        sa.Column("feedback_score", sa.SmallInteger),
        sa.Column("feedback_text", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ai_session", "ai_interactions", ["session_id"])
    op.create_index("ix_ai_capability", "ai_interactions", ["capability"])
    op.create_index("ix_ai_user", "ai_interactions", ["user_id"])

    op.create_table("ai_pr_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_requisitions.id", ondelete="SET NULL")),
        sa.Column("raw_input", sa.Text, nullable=False),
        sa.Column("extracted_title", sa.String(255)),
        sa.Column("extracted_items", postgresql.JSON),
        sa.Column("extracted_department", sa.String(100)),
        sa.Column("extracted_budget", sa.Numeric(18, 2)),
        sa.Column("extracted_required_date", sa.Date),
        sa.Column("extracted_priority", sa.String(20)),
        sa.Column("business_justification", sa.Text),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("ambiguities", postgresql.JSON),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table("ai_vendor_recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_requisitions.id", ondelete="SET NULL")),
        sa.Column("material_category", sa.String(100)),
        sa.Column("recommendations", postgresql.JSON),
        sa.Column("data_snapshot", postgresql.JSON),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_table("ai_policy_checks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("overall_status", sa.String(10), nullable=False),
        sa.Column("violations", postgresql.JSON),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("overridden_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("auth_users.id", ondelete="SET NULL")),
        sa.Column("override_reason", sa.Text),
    )
    op.create_table("ai_approval_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pr_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_requisitions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("summary_text", sa.Text),
        sa.Column("cost_impact", sa.Text),
        sa.Column("business_value", sa.Text),
        sa.Column("risk_flags", postgresql.JSON),
        sa.Column("comparable_purchases", postgresql.JSON),
        sa.Column("recommendation", sa.String(20)),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_table("ai_analytics_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("user_question", sa.Text, nullable=False),
        sa.Column("classified_intent", sa.String(50)),
        sa.Column("generated_sql", sa.Text),
        sa.Column("sql_validated", sa.Boolean, server_default="false"),
        sa.Column("allowed_tables_used", postgresql.JSON),
        sa.Column("result_json", postgresql.JSON),
        sa.Column("row_count", sa.Integer),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
    )
    op.create_table("ai_document_extractions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("interaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_interactions.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("invoices.id", ondelete="SET NULL")),
        sa.Column("source_filename", sa.String(255)),
        sa.Column("source_s3_key", sa.String(500)),
        sa.Column("extracted_invoice_number", sa.String(100)),
        sa.Column("extracted_vendor_name", sa.String(255)),
        sa.Column("extracted_po_number", sa.String(100)),
        sa.Column("extracted_date", sa.Date),
        sa.Column("extracted_due_date", sa.Date),
        sa.Column("extracted_line_items", postgresql.JSON),
        sa.Column("extracted_total", sa.Numeric(18, 2)),
        sa.Column("extracted_tax_total", sa.Numeric(18, 2)),
        sa.Column("extracted_currency", sa.String(3)),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("raw_extraction", postgresql.JSON),
        sa.Column("status", sa.String(20), nullable=False, server_default="EXTRACTED"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    for t in ["ai_document_extractions","ai_analytics_queries","ai_approval_summaries",
              "ai_policy_checks","ai_vendor_recommendations","ai_pr_drafts","ai_interactions"]:
        op.drop_table(t)
