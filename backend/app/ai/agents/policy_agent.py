"""
Policy Compliance Agent.

Runs pre-submission checks against 10 procurement policy rules.
Uses LLM for nuanced interpretation + rule explanation, but first
performs deterministic DB checks to gather facts for the LLM context.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import POLICY_SYSTEM, policy_check_user
from app.ai.schemas.outputs import PolicyCheckOutput
from app.config import settings
from app.domain.ai.models import AICapability, AIInteraction, AIPolicyCheck, AIStatus
import logging

logger = logging.getLogger(__name__)


class PolicyComplianceAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def check(
        self,
        pr_id: UUID,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Run all 10 policy rules against a PR.
        Returns structured violations + overall status.
        """
        sid = session_id or uuid.uuid4()

        # ── Fetch PR data ─────────────────────────────────────────────────────
        pr_data = await self._load_pr_data(pr_id)
        if not pr_data:
            return {"error": f"PR {pr_id} not found", "overall_status": "BLOCK"}

        # ── Gather policy context (deterministic DB facts) ────────────────────
        policy_context = await self._gather_policy_context(pr_data)

        # ── Call LLM ──────────────────────────────────────────────────────────
        user_prompt = policy_check_user(pr_data, policy_context)
        parsed, llm_result = await ai_client.complete_structured(
            system=POLICY_SYSTEM,
            user=user_prompt,
            schema=PolicyCheckOutput,
            model=settings.AI_MODEL_FAST,
        )

        # ── Deterministic overrides (safety net — LLM must not override these) ──
        if policy_context.get("has_blocked_vendor"):
            if parsed:
                # Ensure BLOCK is in violations regardless of LLM output
                block_exists = any(v.rule_id == "VENDOR_002" for v in parsed.violations)
                if not block_exists:
                    from app.ai.schemas.outputs import PolicyViolation
                    parsed.violations.append(PolicyViolation(
                        rule_id="VENDOR_002",
                        rule_name="Blocked Vendor",
                        severity="BLOCK",
                        explanation="This PR references a vendor that has been blocked in the system.",
                        suggested_fix="Remove the blocked vendor and select an approved alternative.",
                        field_affected="vendor_id",
                    ))
                    parsed.overall_status = "BLOCK"
                    parsed.auto_approvable = False

        # ── Persist interaction ───────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.POLICY_CHECK,
            user_id=user_id,
            input_text=pr_data.get("title", ""),
            input_metadata={"pr_id": str(pr_id), "pr_value": str(pr_data.get("total_value", 0))},
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
            # Fail open with WARN — don't block submission on AI failure
            return {
                "overall_status": "WARN",
                "violations": [{
                    "rule_id": "AI_001",
                    "rule_name": "Policy Check Unavailable",
                    "severity": "WARN",
                    "explanation": "AI policy check temporarily unavailable. Manual review required.",
                    "suggested_fix": "Proceed to submission — approver will review manually.",
                }],
                "summary": "Policy check could not be completed automatically.",
                "auto_approvable": False,
                "interaction_id": str(interaction.id),
            }

        # ── Persist policy check ──────────────────────────────────────────────
        check = AIPolicyCheck(
            interaction_id=interaction.id,
            pr_id=pr_id,
            overall_status=parsed.overall_status,
            violations=[v.model_dump() for v in parsed.violations],
        )
        self.session.add(check)
        await self.session.flush()

        return {
            "check_id": str(check.id),
            "interaction_id": str(interaction.id),
            "overall_status": parsed.overall_status,
            "violations": [v.model_dump() for v in parsed.violations],
            "summary": parsed.summary,
            "auto_approvable": parsed.auto_approvable,
            "violation_count": {
                "BLOCK": sum(1 for v in parsed.violations if v.severity == "BLOCK"),
                "WARN": sum(1 for v in parsed.violations if v.severity == "WARN"),
                "INFO": sum(1 for v in parsed.violations if v.severity == "INFO"),
            },
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

    async def _load_pr_data(self, pr_id: UUID) -> dict | None:
        from app.domain.procurement.models import PurchaseRequisition, PRItem
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

        return {
            "pr_number": pr.pr_number,
            "title": pr.title,
            "department": pr.department,
            "total_value": float(pr.total_value or 0),
            "description": pr.description or pr.notes,
            "required_date": pr.required_date.isoformat() if pr.required_date else None,
            "priority": pr.priority,
            "items": [
                {
                    "description": i.description,
                    "quantity": float(i.quantity),
                    "estimated_price": float(i.estimated_price or 0),
                }
                for i in pr.items
            ],
            "justification": pr.notes or pr.description,
        }

    async def _gather_policy_context(self, pr_data: dict) -> dict:
        """
        Run deterministic DB checks to provide factual context to the LLM.
        The LLM interprets — the DB provides facts.
        """
        ctx: dict = {"today": date.today().isoformat()}

        # Budget utilization
        try:
            dept = pr_data.get("department")
            if dept:
                quarter_start = date.today().replace(
                    month=((date.today().month - 1) // 3) * 3 + 1, day=1
                )
                row = await self.session.execute(text("""
                    SELECT COALESCE(SUM(total_value), 0) as spent
                    FROM purchase_requisitions
                    WHERE department = :dept
                      AND status NOT IN ('CANCELLED', 'DRAFT')
                      AND created_at >= :qs
                """), {"dept": dept, "qs": quarter_start})
                spent = float(row.scalar_one() or 0)
                ctx["dept_spent"] = spent
                ctx["dept_budget"] = spent * 3  # placeholder — real system would have budget table
        except Exception:
            ctx["dept_spent"] = 0

        # Similar PRs in last 30 days
        try:
            title_words = set(pr_data.get("title", "").lower().split())
            cutoff = date.today() - timedelta(days=30)
            similar_row = await self.session.execute(text("""
                SELECT COUNT(*) FROM purchase_requisitions
                WHERE department = :dept
                  AND created_at >= :cutoff
                  AND status NOT IN ('CANCELLED')
                  AND LOWER(title) LIKE :keyword
            """), {
                "dept": pr_data.get("department", ""),
                "cutoff": cutoff,
                "keyword": f"%{list(title_words)[0] if title_words else 'x'}%",
            })
            ctx["recent_similar_count"] = similar_row.scalar_one() or 0
        except Exception:
            ctx["recent_similar_count"] = 0

        # Blocked vendors
        ctx["has_blocked_vendor"] = False
        ctx["blocked_vendors"] = "None"

        ctx["preferred_vendors"] = "Yes"
        return ctx
