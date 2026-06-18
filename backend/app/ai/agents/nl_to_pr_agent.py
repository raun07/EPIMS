"""
NL→PR Agent: Converts a natural language purchase request into a structured PR draft.

Flow:
  1. Load context (departments, categories, budget policy)
  2. Call LLM with structured output schema
  3. Validate and score the extraction
  4. Persist to ai_pr_drafts + ai_interactions
  5. Return draft ready for user to review and accept
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, UTC
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import NL_TO_PR_SYSTEM, nl_to_pr_user
from app.ai.schemas.outputs import NLToPROutput
from app.config import settings
from app.domain.ai.models import AICapability, AIInteraction, AIPRDraft, AIStatus, PRDraftStatus
import logging

logger = logging.getLogger(__name__)


class NLToPRAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def extract(
        self,
        request_text: str,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Parse a natural language request and return a structured PR draft.

        Returns a dict with:
          - draft_id: UUID of the AIPRDraft record
          - extracted: NLToPROutput fields
          - interaction_id: UUID for feedback tracking
          - ready_to_create: bool (True if confidence >= 0.7 and no blocking ambiguities)
        """
        sid = session_id or uuid.uuid4()

        # ── Build context ─────────────────────────────────────────────────────
        context = await self._load_context()

        # ── Call LLM ──────────────────────────────────────────────────────────
        user_prompt = nl_to_pr_user(request_text, context)
        parsed, llm_result = await ai_client.complete_structured(
            system=NL_TO_PR_SYSTEM,
            user=user_prompt,
            schema=NLToPROutput,
            model=settings.AI_MODEL_PRIMARY,
        )

        # ── Persist interaction ───────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.NL_TO_PR,
            user_id=user_id,
            input_text=request_text,
            input_metadata={"context_keys": list(context.keys())},
            output_json=parsed.model_dump() if parsed else None,
            model_used=llm_result.model if llm_result else settings.AI_MODEL_PRIMARY,
            prompt_tokens=llm_result.input_tokens if llm_result else None,
            completion_tokens=llm_result.output_tokens if llm_result else None,
            latency_ms=llm_result.latency_ms if llm_result else None,
            status=AIStatus.SUCCESS if parsed else AIStatus.FAILED,
            error_detail=None if parsed else "LLM returned invalid structured output",
        )
        self.session.add(interaction)
        await self.session.flush()

        if parsed is None:
            return {
                "draft_id": None,
                "interaction_id": str(interaction.id),
                "error": "AI extraction failed. Please try rephrasing your request.",
                "ready_to_create": False,
            }

        # ── Parse required_date ───────────────────────────────────────────────
        required_date = None
        if parsed.required_by_date:
            try:
                required_date = date.fromisoformat(parsed.required_by_date)
            except ValueError:
                pass

        # ── Persist draft ─────────────────────────────────────────────────────
        draft = AIPRDraft(
            interaction_id=interaction.id,
            raw_input=request_text,
            extracted_title=parsed.title,
            extracted_items=[i.model_dump() for i in parsed.items],
            extracted_department=parsed.department,
            extracted_budget=Decimal(str(parsed.estimated_total_budget)) if parsed.estimated_total_budget else None,
            extracted_required_date=required_date,
            extracted_priority=parsed.priority,
            business_justification=parsed.business_justification,
            confidence_score=Decimal(str(parsed.confidence_score)),
            ambiguities=parsed.ambiguities,
            status=PRDraftStatus.DRAFT,
        )
        self.session.add(draft)
        await self.session.flush()

        ready = parsed.confidence_score >= 0.65 and len(parsed.ambiguities) < 3

        return {
            "draft_id": str(draft.id),
            "interaction_id": str(interaction.id),
            "title": parsed.title,
            "items": [i.model_dump() for i in parsed.items],
            "department": parsed.department,
            "estimated_budget": parsed.estimated_total_budget,
            "required_by_date": parsed.required_by_date,
            "priority": parsed.priority,
            "business_justification": parsed.business_justification,
            "confidence_score": parsed.confidence_score,
            "ambiguities": parsed.ambiguities,
            "ready_to_create": ready,
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

    async def _load_context(self) -> dict:
        """Fetch departments and categories from DB to include in prompt."""
        from sqlalchemy import select, distinct
        from app.domain.procurement.models import PurchaseRequisition
        from app.domain.material.models import MaterialGroup

        try:
            dept_rows = await self.session.execute(
                select(distinct(PurchaseRequisition.department))
                .where(PurchaseRequisition.department.isnot(None))
                .limit(20)
            )
            departments = [r[0] for r in dept_rows if r[0]]

            cat_rows = await self.session.execute(select(MaterialGroup.name).limit(20))
            categories = [r[0] for r in cat_rows]
        except Exception:
            departments = ["Engineering", "Finance", "Operations", "IT", "HR", "Procurement"]
            categories = ["IT_EQUIPMENT", "FURNITURE", "CONSUMABLES", "SERVICES", "CHEMICALS", "SPARE_PARTS"]

        return {
            "departments": departments or ["Engineering", "Finance", "Operations", "IT", "HR"],
            "material_categories": categories or ["IT_EQUIPMENT", "FURNITURE", "CONSUMABLES", "SERVICES"],
            "budget_policy": "Purchases above ₹1,00,000 require manager approval. Above ₹5,00,000 require CFO approval.",
            "today": date.today().isoformat(),
        }
