"""
Pydantic output schemas for AI structured outputs.
Every LLM response is validated against one of these before touching the DB.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ── ① NL→PR Extraction ───────────────────────────────────────────────────────

class ExtractedLineItem(BaseModel):
    description: str = Field(description="Clear description of the item")
    quantity: float = Field(gt=0, description="Numeric quantity")
    unit: str = Field(default="EA", description="Unit of measure code")
    estimated_unit_price: float | None = Field(None, ge=0, description="Price per unit in INR")
    material_category: str | None = Field(None, description="Material category: IT_EQUIPMENT, FURNITURE, CONSUMABLES, etc.")


class NLToPROutput(BaseModel):
    """Structured PR extracted from natural language."""
    title: str = Field(description="Concise PR title, max 80 chars")
    items: list[ExtractedLineItem] = Field(min_length=1)
    department: str | None = Field(None, description="Department name if mentioned")
    estimated_total_budget: float | None = Field(None, ge=0, description="Total budget in INR")
    required_by_date: str | None = Field(None, description="ISO date YYYY-MM-DD or null")
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = Field(default="NORMAL")
    business_justification: str = Field(description="Why this purchase is needed")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall extraction confidence 0-1")
    ambiguities: list[str] = Field(
        default_factory=list,
        description="List of unclear aspects that need clarification from requester"
    )

    @field_validator("required_by_date", mode="before")
    @classmethod
    def validate_date(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            return None


# ── ② Vendor Recommendation ───────────────────────────────────────────────────

class VendorScore(BaseModel):
    vendor_id: str = Field(description="UUID of the vendor")
    vendor_name: str
    overall_score: float = Field(ge=0.0, le=1.0, description="Weighted composite score")
    price_score: float = Field(ge=0.0, le=1.0, description="Price competitiveness vs market")
    delivery_score: float = Field(ge=0.0, le=1.0, description="On-time delivery rate")
    quality_score: float = Field(ge=0.0, le=1.0, description="Quality/rejection rate")
    relationship_score: float = Field(ge=0.0, le=1.0, description="Payment terms, responsiveness")
    explanation: str = Field(description="2-3 sentence narrative for why this vendor ranks here")
    past_po_count: int = Field(ge=0, description="Number of POs in last 12 months")
    avg_delivery_days: float | None = Field(None, description="Average actual delivery time")
    avg_unit_price: float | None = Field(None, description="Average price paid historically")
    recommendation_strength: Literal["STRONG", "MODERATE", "WEAK"] = "MODERATE"


class VendorRecommendationOutput(BaseModel):
    """Ranked vendor recommendations with explanations."""
    material_category: str
    recommendations: list[VendorScore] = Field(min_length=1, max_length=5)
    analysis_summary: str = Field(description="Overall market context and recommendation rationale")
    data_period: str = Field(description="Period of historical data used e.g. 'Last 12 months'")


# ── ③ Policy Check ────────────────────────────────────────────────────────────

class PolicyViolation(BaseModel):
    rule_id: str = Field(description="Machine-readable rule identifier e.g. BUDGET_001")
    rule_name: str = Field(description="Human-readable rule name")
    severity: Literal["INFO", "WARN", "BLOCK"]
    explanation: str = Field(description="Why this rule was triggered")
    suggested_fix: str = Field(description="What the requester should do to resolve")
    field_affected: str | None = Field(None, description="Which PR field triggered this")
    reference: str | None = Field(None, description="Policy document reference if applicable")


class PolicyCheckOutput(BaseModel):
    """Compliance analysis result for a PR."""
    overall_status: Literal["PASS", "WARN", "BLOCK"]
    violations: list[PolicyViolation] = Field(default_factory=list)
    summary: str = Field(description="One-sentence overall compliance assessment")
    auto_approvable: bool = Field(
        description="True if no violations or only INFO-level — can bypass manual approval"
    )


# ── ④ Approval Summary ────────────────────────────────────────────────────────

class RiskFlag(BaseModel):
    flag: str = Field(description="Short risk label")
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    detail: str = Field(description="1-2 sentence explanation")


class ComparablePurchase(BaseModel):
    pr_number: str
    title: str
    total_value: float
    approved_date: str | None
    outcome: str  # APPROVED | REJECTED | CANCELLED


class ApprovalSummaryOutput(BaseModel):
    """Executive summary for approvers — concise, decision-ready."""
    headline: str = Field(description="One sentence: what, how much, why")
    purchase_rationale: str = Field(description="Why this purchase is needed (2-3 sentences)")
    cost_impact: str = Field(description="Budget impact analysis (monthly/annual amortisation if relevant)")
    business_value: str = Field(description="Expected ROI or operational benefit")
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    comparable_purchases: list[ComparablePurchase] = Field(
        default_factory=list,
        description="Similar past PRs for context (max 3)"
    )
    recommendation: Literal["APPROVE", "REVIEW", "ESCALATE"] = Field(
        description="AI recommendation based on policy, history, and risk"
    )
    recommendation_rationale: str = Field(description="Why the AI recommends this action")


# ── ⑤ Analytics ──────────────────────────────────────────────────────────────

class AnalyticsQueryOutput(BaseModel):
    """SQL generation result with full safety metadata."""
    intent: Literal[
        "VENDOR_PERFORMANCE", "SPEND_ANALYSIS", "INVENTORY_STATUS",
        "DEPARTMENT_SPEND", "DELIVERY_PERFORMANCE", "INVOICE_STATUS"
    ]
    sql: str = Field(description="Read-only SELECT query — no DML, no DDL")
    tables_used: list[str] = Field(description="Exact table names referenced in the query")
    explanation: str = Field(description="Plain English: what the query computes")
    result_columns: list[str] = Field(description="Expected column names in result set")
    chart_type: Literal["table", "bar", "line", "pie", "number"] = Field(
        description="Best visualization type for the expected result"
    )

    @field_validator("sql")
    @classmethod
    def no_dml(cls, v: str) -> str:
        forbidden = ["DELETE", "UPDATE", "INSERT", "DROP", "TRUNCATE", "ALTER", "CREATE", "EXEC", "EXECUTE"]
        upper = v.upper()
        for kw in forbidden:
            if kw in upper:
                raise ValueError(f"Forbidden keyword '{kw}' in generated SQL")
        if not upper.strip().startswith("SELECT"):
            raise ValueError("Query must start with SELECT")
        return v


# ── ⑥ Document Intelligence ───────────────────────────────────────────────────

class ExtractedInvoiceLineItem(BaseModel):
    line_number: int | None = None
    description: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    amount: float | None = None
    tax_rate: float | None = None
    tax_amount: float | None = None
    hsn_sac_code: str | None = None


class DocumentExtractionOutput(BaseModel):
    """Structured data extracted from a PDF invoice."""
    invoice_number: str | None = None
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    po_number: str | None = None
    invoice_date: str | None = None   # ISO date
    due_date: str | None = None       # ISO date
    currency: str = "INR"
    subtotal: float | None = None
    tax_total: float | None = None
    total_amount: float | None = None
    line_items: list[ExtractedInvoiceLineItem] = Field(default_factory=list)
    payment_terms: str | None = None
    bank_details: dict | None = None  # {"account": ..., "ifsc": ..., "bank": ...}
    confidence_score: float = Field(ge=0.0, le=1.0, description="Overall extraction confidence")
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Fields that were unclear or required inference"
    )

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def validate_dates(cls, v: str | None) -> str | None:
        if not v:
            return None
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%B %d, %Y"):
            try:
                from datetime import datetime
                return datetime.strptime(str(v), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return v  # Return as-is if no format matches
