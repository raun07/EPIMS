"""
AI Evaluation Framework.

Computes accuracy metrics per capability using stored interactions.
Run weekly via Celery beat or manually: python -m app.ai.evaluators.eval_runner

Metrics:
  NL→PR:      confidence calibration, field extraction rate
  Vendor Rec: top-3 vendor hit rate (compared to actual PO selections)
  Policy:     precision/recall on known violations
  Analytics:  SQL validity rate, execution success rate
  Document:   field extraction accuracy vs manually verified invoices
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AIEvaluator:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_all(self, days_back: int = 7) -> dict:
        """Run all evaluations for the past N days. Returns aggregate metrics."""
        since = datetime.now(UTC) - timedelta(days=days_back)
        return {
            "period_days": days_back,
            "evaluated_from": since.isoformat(),
            "nl_to_pr": await self.eval_nl_to_pr(since),
            "analytics": await self.eval_analytics(since),
            "policy": await self.eval_policy(since),
            "document_intel": await self.eval_document_intel(since),
            "overall_cost_usd": await self.total_cost_estimate(since),
        }

    async def eval_nl_to_pr(self, since: datetime) -> dict:
        """
        Evaluate NL→PR extraction quality.
        Metrics:
          - acceptance_rate: % of drafts accepted by users
          - avg_confidence: mean confidence score
          - field_completeness: % of drafts with all 4 key fields
        """
        from app.domain.ai.models import AIPRDraft, AIInteraction, PRDraftStatus

        stmt = (
            select(AIPRDraft)
            .join(AIInteraction, AIPRDraft.interaction_id == AIInteraction.id)
            .where(AIInteraction.created_at >= since)
        )
        result = await self.session.execute(stmt)
        drafts = result.scalars().all()

        if not drafts:
            return {"sample_size": 0, "message": "No NL→PR calls in this period"}

        total = len(drafts)
        accepted = sum(1 for d in drafts if d.status == PRDraftStatus.ACCEPTED)
        confidences = [float(d.confidence_score) for d in drafts if d.confidence_score]
        complete = sum(
            1 for d in drafts
            if d.extracted_title and d.extracted_items and d.extracted_budget is not None
        )

        return {
            "sample_size": total,
            "acceptance_rate": round(accepted / total * 100, 1),
            "rejected_rate": round((total - accepted) / total * 100, 1),
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "field_completeness_rate": round(complete / total * 100, 1),
        }

    async def eval_analytics(self, since: datetime) -> dict:
        """
        Evaluate analytics SQL generation.
        Metrics:
          - sql_validity_rate: % of queries that passed validation
          - execution_success_rate: % that executed without error
          - avg_row_count: typical result size
        """
        from app.domain.ai.models import AIAnalyticsQuery, AIInteraction

        stmt = (
            select(AIAnalyticsQuery)
            .join(AIInteraction, AIAnalyticsQuery.interaction_id == AIInteraction.id)
            .where(AIInteraction.created_at >= since)
        )
        result = await self.session.execute(stmt)
        queries = result.scalars().all()

        if not queries:
            return {"sample_size": 0, "message": "No analytics queries in this period"}

        total = len(queries)
        valid = sum(1 for q in queries if q.sql_validated)
        executed = sum(1 for q in queries if q.result_json is not None)
        row_counts = [q.row_count for q in queries if q.row_count is not None]

        return {
            "sample_size": total,
            "sql_validity_rate": round(valid / total * 100, 1),
            "execution_success_rate": round(executed / total * 100, 1),
            "avg_row_count": round(sum(row_counts) / len(row_counts), 1) if row_counts else 0,
        }

    async def eval_policy(self, since: datetime) -> dict:
        """
        Evaluate policy check results.
        Metrics:
          - block_rate: % of PRs that got BLOCK status
          - warn_rate: % that got WARN
          - pass_rate: % that passed
          - override_rate: % of BLOCK decisions that were overridden
        """
        from app.domain.ai.models import AIPolicyCheck, AIInteraction

        stmt = (
            select(AIPolicyCheck)
            .join(AIInteraction, AIPolicyCheck.interaction_id == AIInteraction.id)
            .where(AIInteraction.created_at >= since)
        )
        result = await self.session.execute(stmt)
        checks = result.scalars().all()

        if not checks:
            return {"sample_size": 0, "message": "No policy checks in this period"}

        total = len(checks)
        blocks = sum(1 for c in checks if c.overall_status == "BLOCK")
        warns = sum(1 for c in checks if c.overall_status == "WARN")
        passes = sum(1 for c in checks if c.overall_status == "PASS")
        overrides = sum(1 for c in checks if c.overridden_by is not None)

        return {
            "sample_size": total,
            "pass_rate": round(passes / total * 100, 1),
            "warn_rate": round(warns / total * 100, 1),
            "block_rate": round(blocks / total * 100, 1),
            "override_rate": round(overrides / max(blocks, 1) * 100, 1),
        }

    async def eval_document_intel(self, since: datetime) -> dict:
        """
        Evaluate document extraction quality.
        Metrics:
          - avg_confidence: mean extraction confidence
          - link_rate: % of extractions successfully linked to invoices
          - high_confidence_rate: % with confidence >= 0.8
        """
        from app.domain.ai.models import AIDocumentExtraction, AIInteraction, DocExtractionStatus

        stmt = (
            select(AIDocumentExtraction)
            .join(AIInteraction, AIDocumentExtraction.interaction_id == AIInteraction.id)
            .where(AIInteraction.created_at >= since)
        )
        result = await self.session.execute(stmt)
        extractions = result.scalars().all()

        if not extractions:
            return {"sample_size": 0, "message": "No document extractions in this period"}

        total = len(extractions)
        confidences = [float(e.confidence_score) for e in extractions if e.confidence_score]
        linked = sum(1 for e in extractions if e.status == DocExtractionStatus.LINKED)
        high_conf = sum(1 for e in extractions if e.confidence_score and float(e.confidence_score) >= 0.8)

        return {
            "sample_size": total,
            "avg_confidence": round(sum(confidences) / len(confidences), 3) if confidences else 0,
            "link_rate": round(linked / total * 100, 1),
            "high_confidence_rate": round(high_conf / total * 100, 1),
        }

    async def total_cost_estimate(self, since: datetime) -> dict:
        """Estimate total AI spend based on token counts."""
        from app.domain.ai.models import AIInteraction

        stmt = select(
            AIInteraction.model_used,
            func.sum(AIInteraction.prompt_tokens).label("total_input"),
            func.sum(AIInteraction.completion_tokens).label("total_output"),
            func.count(AIInteraction.id).label("call_count"),
        ).where(
            AIInteraction.created_at >= since
        ).group_by(AIInteraction.model_used)

        result = await self.session.execute(stmt)
        rows = result.all()

        _RATES = {
            "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
            "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00},
        }

        total_usd = 0.0
        breakdown = []
        for row in rows:
            model = row.model_used or "unknown"
            rates = _RATES.get(model, {"input": 3.00, "output": 15.00})
            cost = (
                ((row.total_input or 0) * rates["input"]) +
                ((row.total_output or 0) * rates["output"])
            ) / 1_000_000
            total_usd += cost
            breakdown.append({
                "model": model,
                "call_count": row.call_count,
                "input_tokens": row.total_input or 0,
                "output_tokens": row.total_output or 0,
                "estimated_cost_usd": round(cost, 4),
            })

        return {
            "total_estimated_usd": round(total_usd, 4),
            "by_model": breakdown,
        }

    async def feedback_summary(self, since: datetime) -> dict:
        """Aggregate user feedback scores by capability."""
        from app.domain.ai.models import AIInteraction

        stmt = select(
            AIInteraction.capability,
            func.avg(AIInteraction.feedback_score).label("avg_score"),
            func.count(AIInteraction.feedback_score).label("feedback_count"),
        ).where(
            AIInteraction.created_at >= since,
            AIInteraction.feedback_score.isnot(None),
        ).group_by(AIInteraction.capability)

        result = await self.session.execute(stmt)
        rows = result.all()

        return {
            row.capability: {
                "avg_score": round(float(row.avg_score), 2) if row.avg_score else None,
                "feedback_count": row.feedback_count,
            }
            for row in rows
        }
