"""
AI Procurement Copilot API — six deeply integrated endpoints.

All endpoints:
  - Require authentication
  - Store interaction in DB (audit trail)
  - Return structured JSON (never raw LLM text)
  - Accept feedback via PATCH /ai/feedback/{interaction_id}
"""
from __future__ import annotations

import uuid
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.config import settings
from app.core.dependencies import CurrentUser, DBSession
from app.database import AsyncSessionLocal

router = APIRouter(prefix="/ai", tags=["AI Copilot"])


def _require_ai():
    if not settings.AI_ENABLED:
        raise HTTPException(status_code=503, detail="AI Copilot is disabled (AI_ENABLED=False)")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured. Set it in your .env file to enable AI features."
        )


# ── ① NL→PR Extraction ───────────────────────────────────────────────────────

class NLToPRRequest(BaseModel):
    request_text: str
    session_id: str | None = None


class AcceptDraftRequest(BaseModel):
    draft_id: str


@router.post("/nl-to-pr")
async def nl_to_pr(
    body: NLToPRRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Convert a natural language purchase request into a structured PR draft.

    Example input:
    "Need 25 Dell laptops for new engineering team joining next month. Budget 15 lakh."
    """
    _require_ai()
    from app.ai.agents.nl_to_pr_agent import NLToPRAgent
    agent = NLToPRAgent(db)
    sid = UUID(body.session_id) if body.session_id else uuid.uuid4()
    result = await agent.extract(
        request_text=body.request_text,
        user_id=current_user.id,
        session_id=sid,
    )
    await db.commit()
    return result


@router.post("/nl-to-pr/{draft_id}/accept")
async def accept_pr_draft(
    draft_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Accept an AI-generated PR draft and create a real PR in DRAFT status.
    Returns the created PR.
    """
    _require_ai()
    from sqlalchemy import select
    from app.domain.ai.models import AIPRDraft, PRDraftStatus
    from app.services.pr_service import PRService
    from app.core.unit_of_work import UnitOfWork
    from decimal import Decimal

    # Fetch draft
    result = await db.execute(select(AIPRDraft).where(AIPRDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != PRDraftStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Draft is already {draft.status}")

    # Create real PR
    async with UnitOfWork() as uow:
        svc = PRService(uow)
        items = [
            {
                "description": i.get("description", ""),
                "quantity": i.get("quantity", 1),
                "estimated_price": i.get("estimated_unit_price"),
            }
            for i in (draft.extracted_items or [])
        ]
        pr = await svc.create_pr(
            title=draft.extracted_title or "AI-Generated PR",
            description=draft.business_justification,
            requested_by_id=current_user.id,
            items=items,
            priority=draft.extracted_priority or "NORMAL",
            required_date=draft.extracted_required_date,
            department=draft.extracted_department,
            notes=f"Created by AI Copilot from: {draft.raw_input[:200]}",
        )
        await uow.commit()

    # Mark draft as accepted
    draft.status = PRDraftStatus.ACCEPTED
    draft.pr_id = pr.id
    await db.commit()

    return {"pr_id": str(pr.id), "pr_number": pr.pr_number, "status": pr.status}


# ── ② Vendor Recommendations ──────────────────────────────────────────────────

class VendorRecRequest(BaseModel):
    material_category: str
    pr_id: str | None = None
    pr_title: str | None = None
    estimated_budget: float | None = None
    items_summary: str | None = None
    required_date: str | None = None


@router.post("/vendor-recommendations")
async def vendor_recommendations(
    body: VendorRecRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get AI-powered vendor recommendations for a purchase category.
    Considers historical PO data, delivery performance, and pricing.
    Results are cached for 24 hours.
    """
    _require_ai()
    from app.ai.agents.vendor_rec_agent import VendorRecommendationAgent
    agent = VendorRecommendationAgent(db)
    pr_context = {
        "title": body.pr_title or body.material_category,
        "category": body.material_category,
        "budget": body.estimated_budget,
        "items_summary": body.items_summary or "Not specified",
        "required_date": body.required_date or "Not specified",
    }
    pr_id = UUID(body.pr_id) if body.pr_id else None
    result = await agent.recommend(
        pr_id=pr_id,
        material_category=body.material_category,
        pr_context=pr_context,
        user_id=current_user.id,
    )
    await db.commit()
    return result


# ── ③ Policy Check ────────────────────────────────────────────────────────────

@router.post("/policy-check/{pr_id}")
async def policy_check(
    pr_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Run AI-powered policy compliance check on a PR before submission.
    Returns violations grouped by severity: BLOCK | WARN | INFO.
    """
    _require_ai()
    from app.ai.agents.policy_agent import PolicyComplianceAgent
    agent = PolicyComplianceAgent(db)
    result = await agent.check(pr_id=pr_id, user_id=current_user.id)
    await db.commit()
    return result


@router.post("/policy-check/{check_id}/override")
async def override_policy(
    check_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    reason: str = Form(...),
):
    """Finance manager override for a blocked policy check."""
    from sqlalchemy import select
    from app.domain.ai.models import AIPolicyCheck
    result = await db.execute(select(AIPolicyCheck).where(AIPolicyCheck.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(404, "Policy check not found")
    check.overridden_by = current_user.id
    check.override_reason = reason
    check.overall_status = "WARN"  # downgrade from BLOCK to WARN after override
    await db.commit()
    return {"status": "overridden", "check_id": str(check_id)}


# ── ④ Approval Summary ────────────────────────────────────────────────────────

@router.get("/approval-summary/{pr_id}")
async def get_approval_summary(
    pr_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Get or generate an AI executive summary for a PR approval decision.
    Generated once and cached — subsequent calls return the stored summary.
    """
    _require_ai()
    from app.ai.agents.approval_agent import ApprovalSummaryAgent
    agent = ApprovalSummaryAgent(db)
    result = await agent.generate(pr_id=pr_id, user_id=current_user.id)
    await db.commit()
    return result


@router.post("/approval-summary/{pr_id}/regenerate")
async def regenerate_approval_summary(
    pr_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Force regeneration of the approval summary (clears cached version)."""
    _require_ai()
    from sqlalchemy import select, delete
    from app.domain.ai.models import AIApprovalSummary
    await db.execute(delete(AIApprovalSummary).where(AIApprovalSummary.pr_id == pr_id))
    await db.flush()

    from app.ai.agents.approval_agent import ApprovalSummaryAgent
    agent = ApprovalSummaryAgent(db)
    result = await agent.generate(pr_id=pr_id, user_id=current_user.id)
    await db.commit()
    return result


# ── ⑤ Analytics Assistant ────────────────────────────────────────────────────

class AnalyticsRequest(BaseModel):
    question: str
    session_id: str | None = None


@router.post("/analytics")
async def analytics_query(
    body: AnalyticsRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Ask procurement analytics questions in plain English.

    Examples:
    - "Which vendors caused the most delays this quarter?"
    - "What categories had highest spend last month?"
    - "Show slow-moving inventory below reorder point"
    - "Which departments spend the most on IT equipment?"

    Returns validated query results + recommended chart type.
    """
    _require_ai()
    from app.ai.agents.analytics_agent import AnalyticsAgent
    agent = AnalyticsAgent(db)
    sid = UUID(body.session_id) if body.session_id else uuid.uuid4()
    result = await agent.query(
        question=body.question,
        user_id=current_user.id,
        session_id=sid,
    )
    await db.commit()
    return result


@router.get("/analytics/history")
async def analytics_history(
    current_user: CurrentUser,
    db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    """Return recent analytics queries by the current user."""
    from sqlalchemy import select, desc
    from app.domain.ai.models import AIAnalyticsQuery, AIInteraction
    stmt = (
        select(AIAnalyticsQuery, AIInteraction.created_at)
        .join(AIInteraction, AIAnalyticsQuery.interaction_id == AIInteraction.id)
        .where(AIInteraction.user_id == current_user.id)
        .order_by(desc(AIInteraction.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "id": str(row.AIAnalyticsQuery.id),
            "question": row.AIAnalyticsQuery.user_question,
            "intent": row.AIAnalyticsQuery.classified_intent,
            "row_count": row.AIAnalyticsQuery.row_count,
            "chart_type": None,  # stored in output_json
            "asked_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


# ── ⑥ Document Intelligence ───────────────────────────────────────────────────

@router.post("/document-extract")
async def document_extract(
    current_user: CurrentUser,
    db: DBSession,
    file: UploadFile = File(...),
):
    """
    Upload a PDF invoice and extract structured data using AI vision.

    Returns:
    - Invoice number, vendor, PO reference, line items
    - Matched vendor and PO from EPIMS database
    - Confidence score and extraction notes
    - Ready-to-create flag when confidence >= 0.7
    """
    _require_ai()

    # Validate file type
    if not file.content_type in ("application/pdf", "image/jpeg", "image/png"):
        raise HTTPException(
            status_code=422,
            detail="Only PDF, JPEG, and PNG files are supported"
        )
    if file.size and file.size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=422, detail="File too large (max 10MB)")

    pdf_bytes = await file.read()
    from app.ai.agents.document_agent import DocumentIntelligenceAgent
    agent = DocumentIntelligenceAgent(db)
    result = await agent.extract_from_bytes(
        pdf_bytes=pdf_bytes,
        filename=file.filename or "upload.pdf",
        user_id=current_user.id,
    )
    await db.commit()
    return result


@router.post("/document-extract/{extraction_id}/link")
async def link_extraction_to_invoice(
    extraction_id: UUID,
    invoice_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
):
    """Link an AI extraction to an existing invoice record after user confirms."""
    from app.ai.agents.document_agent import DocumentIntelligenceAgent
    agent = DocumentIntelligenceAgent(db)
    result = await agent.link_to_invoice(extraction_id, invoice_id)
    await db.commit()
    return result


# ── Feedback endpoint (shared across all capabilities) ───────────────────────

class FeedbackRequest(BaseModel):
    score: int  # 1-5
    text: str | None = None


@router.patch("/feedback/{interaction_id}")
async def submit_feedback(
    interaction_id: UUID,
    body: FeedbackRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Submit a 1-5 star rating + optional comment for any AI interaction."""
    if not 1 <= body.score <= 5:
        raise HTTPException(422, "Score must be between 1 and 5")

    from sqlalchemy import select
    from app.domain.ai.models import AIInteraction
    result = await db.execute(select(AIInteraction).where(AIInteraction.id == interaction_id))
    interaction = result.scalar_one_or_none()
    if not interaction:
        raise HTTPException(404, "Interaction not found")
    if interaction.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(403, "Cannot rate another user's interaction")

    interaction.feedback_score = body.score
    interaction.feedback_text = body.text
    await db.commit()
    return {"status": "recorded", "score": body.score}


# ── AI Interaction history ─────────────────────────────────────────────────────

@router.get("/interactions")
async def list_interactions(
    current_user: CurrentUser,
    db: DBSession,
    capability: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    """List recent AI interactions for the current user."""
    from sqlalchemy import select, desc
    from app.domain.ai.models import AIInteraction
    stmt = (
        select(AIInteraction)
        .where(AIInteraction.user_id == current_user.id)
        .order_by(desc(AIInteraction.created_at))
        .limit(limit)
    )
    if capability:
        stmt = stmt.where(AIInteraction.capability == capability.upper())

    result = await db.execute(stmt)
    interactions = result.scalars().all()

    return [
        {
            "id": str(i.id),
            "capability": i.capability,
            "status": i.status,
            "input_preview": (i.input_text or "")[:100],
            "model_used": i.model_used,
            "latency_ms": i.latency_ms,
            "feedback_score": i.feedback_score,
            "created_at": i.created_at.isoformat(),
        }
        for i in interactions
    ]


# ── AI Status / Health ────────────────────────────────────────────────────────

@router.get("/status")
async def ai_status():
    """Check AI module configuration and availability."""
    return {
        "enabled": settings.AI_ENABLED,
        "api_key_configured": bool(settings.ANTHROPIC_API_KEY),
        "primary_model": settings.AI_MODEL_PRIMARY,
        "fast_model": settings.AI_MODEL_FAST,
        "capabilities": [
            "nl_to_pr", "vendor_recommendations", "policy_check",
            "approval_summary", "analytics", "document_intelligence",
        ],
        "rate_limit_per_min": settings.AI_RATE_LIMIT_PER_MIN,
    }
