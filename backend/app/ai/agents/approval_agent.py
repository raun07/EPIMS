"""
Approval Summary Agent.

Generates a concise executive summary for each PR to help approvers
decide quickly. Runs as a Celery task after PR submission (async).
"""
from __future__ import annotations

import uuid
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import APPROVAL_SUMMARY_SYSTEM, approval_summary_user
from app.ai.schemas.outputs import ApprovalSummaryOutput
from app.config import settings
from app.domain.ai.models import AIApprovalSummary, AICapability, AIInteraction, AIStatus
import logging

logger = logging.getLogger(__name__)


class ApprovalSummaryAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def generate(
        self,
        pr_id: UUID,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Generate or retrieve existing approval summary for a PR.
        Cached in DB — returns existing if already generated for this PR.
        """
        sid = session_id or uuid.uuid4()

        # ── Check if summary already exists ───────────────────────────────────
        from sqlalchemy import select
        existing = await self.session.execute(
            select(AIApprovalSummary).where(AIApprovalSummary.pr_id == pr_id)
        )
        existing_summary = existing.scalar_one_or_none()
        if existing_summary:
            return {
                "summary_id": str(existing_summary.id),
                "headline": self._extract_field(existing_summary, "headline"),
                "purchase_rationale": self._extract_field(existing_summary, "purchase_rationale"),
                "cost_impact": existing_summary.cost_impact,
                "business_value": existing_summary.business_value,
                "risk_flags": existing_summary.risk_flags or [],
                "comparable_purchases": existing_summary.comparable_purchases or [],
                "recommendation": existing_summary.recommendation,
                "summary_text": existing_summary.summary_text,
                "from_cache": True,
                "generated_at": existing_summary.generated_at.isoformat(),
            }

        # ── Load PR data ──────────────────────────────────────────────────────
        pr_data = await self._load_pr_data(pr_id)
        if not pr_data:
            return {"error": f"PR {pr_id} not found"}

        enrichment = await self._load_enrichment(pr_data)

        # ── Call LLM ──────────────────────────────────────────────────────────
        user_prompt = approval_summary_user(pr_data, enrichment)
        parsed, llm_result = await ai_client.complete_structured(
            system=APPROVAL_SUMMARY_SYSTEM,
            user=user_prompt,
            schema=ApprovalSummaryOutput,
            model=settings.AI_MODEL_FAST,
        )

        # ── Persist interaction ───────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.APPROVAL_SUMMARY,
            user_id=user_id,
            input_text=pr_data.get("title", ""),
            input_metadata={"pr_id": str(pr_id)},
            output_json=parsed.model_dump() if parsed else None,
            model_used=llm_result.model if llm_result else settings.AI_MODEL_FAST,
            prompt_tokens=llm_result.input_tokens if llm_result else None,
            completion_tokens=llm_result.output_tokens if llm_result else None,
            latency_ms=llm_result.latency_ms if llm_result else None,
            status=AIStatus.SUCCESS if parsed else AIStatus.FAILED,
        )
        self.session.add(interaction)
        await self.session.flush()

        if parsed is None:
            return {"error": "Summary generation failed", "interaction_id": str(interaction.id)}

        # ── Persist summary ───────────────────────────────────────────────────
        summary = AIApprovalSummary(
            interaction_id=interaction.id,
            pr_id=pr_id,
            summary_text=f"{parsed.headline}\n\n{parsed.purchase_rationale}",
            cost_impact=parsed.cost_impact,
            business_value=parsed.business_value,
            risk_flags=[f.model_dump() for f in parsed.risk_flags],
            comparable_purchases=[c.model_dump() for c in parsed.comparable_purchases],
            recommendation=parsed.recommendation,
        )
        self.session.add(summary)
        await self.session.flush()

        return {
            "summary_id": str(summary.id),
            "interaction_id": str(interaction.id),
            "headline": parsed.headline,
            "purchase_rationale": parsed.purchase_rationale,
            "cost_impact": parsed.cost_impact,
            "business_value": parsed.business_value,
            "risk_flags": [f.model_dump() for f in parsed.risk_flags],
            "comparable_purchases": [c.model_dump() for c in parsed.comparable_purchases],
            "recommendation": parsed.recommendation,
            "recommendation_rationale": parsed.recommendation_rationale,
            "summary_text": summary.summary_text,
            "from_cache": False,
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

    def _extract_field(self, summary: AIApprovalSummary, field: str) -> str | None:
        """Helper to safely extract headline from summary_text."""
        if field == "headline" and summary.summary_text:
            return summary.summary_text.split("\n")[0]
        if field == "purchase_rationale" and summary.summary_text:
            parts = summary.summary_text.split("\n\n")
            return parts[1] if len(parts) > 1 else None
        return None

    async def _load_pr_data(self, pr_id: UUID) -> dict | None:
        from app.domain.procurement.models import PurchaseRequisition, PRItem
        from app.domain.auth.models import User
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        stmt = (
            select(PurchaseRequisition)
            .options(selectinload(PurchaseRequisition.items))
            .where(PurchaseRequisition.id == pr_id)
        )
        result = await self.session.execute(stmt)
        pr = result.scalar_one_or_none()
        if not pr:
            return None

        requester_name = "Unknown"
        if pr.requested_by:
            u = await self.session.get(User, pr.requested_by)
            if u:
                requester_name = u.full_name

        return {
            "pr_number": pr.pr_number,
            "title": pr.title,
            "department": pr.department,
            "total_value": float(pr.total_value or 0),
            "description": pr.description or pr.notes or "",
            "required_date": pr.required_date.isoformat() if pr.required_date else None,
            "priority": pr.priority,
            "requester_name": requester_name,
            "items": [
                {"description": i.description, "quantity": float(i.quantity),
                 "estimated_price": float(i.estimated_price or 0)}
                for i in pr.items
            ],
        }

    async def _load_enrichment(self, pr_data: dict) -> dict:
        from sqlalchemy import text
        enrichment: dict = {}

        # Budget utilization
        try:
            from datetime import date
            quarter_start = date.today().replace(
                month=((date.today().month - 1) // 3) * 3 + 1, day=1
            )
            row = await self.session.execute(text("""
                SELECT COALESCE(SUM(total_value),0) FROM purchase_requisitions
                WHERE department = :dept AND status NOT IN ('CANCELLED','DRAFT') AND created_at >= :qs
            """), {"dept": pr_data.get("department", ""), "qs": quarter_start})
            spent = float(row.scalar_one() or 0)
            budget_estimate = max(spent * 3, float(pr_data.get("total_value", 0)) * 5)
            enrichment["budget_utilization_pct"] = round(spent / budget_estimate * 100, 1) if budget_estimate else 0
        except Exception:
            enrichment["budget_utilization_pct"] = "N/A"

        # Similar approved PRs
        try:
            from sqlalchemy import text as sqltext
            similar = await self.session.execute(sqltext("""
                SELECT pr_number, title, total_value, approved_at
                FROM purchase_requisitions
                WHERE status = 'APPROVED'
                  AND LOWER(title) LIKE :kw
                ORDER BY approved_at DESC LIMIT 3
            """), {"kw": f"%{pr_data['title'][:20].lower()}%"})
            enrichment["similar_approved_count"] = 0
            enrichment["comparable_prs"] = []
            for row in similar:
                enrichment["similar_approved_count"] += 1
                enrichment["comparable_prs"].append(
                    f"{row.pr_number}: {row.title} (₹{float(row.total_value or 0):,.0f})"
                )
        except Exception:
            enrichment["comparable_prs"] = "None found"
            enrichment["similar_approved_count"] = 0

        enrichment["policy_status"] = "Not checked"
        enrichment["policy_violations"] = "None"
        enrichment["top_vendor_name"] = "Not selected"
        return enrichment
