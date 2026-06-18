"""
Vendor Recommendation Agent.

Fetches historical PO + GRN data for each vendor in a category,
scores them on price/delivery/quality/relationship, then asks the LLM
to generate a ranked list with explanations.

Results are cached in Redis for AI_VENDOR_REC_CACHE_TTL_HOURS.
"""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import VENDOR_REC_SYSTEM, vendor_rec_user
from app.ai.schemas.outputs import VendorRecommendationOutput
from app.config import settings
from app.domain.ai.models import AICapability, AIInteraction, AIStatus, AIVendorRecommendation
import logging

logger = logging.getLogger(__name__)


class VendorRecommendationAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recommend(
        self,
        pr_id: UUID | None,
        material_category: str,
        pr_context: dict,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Return vendor recommendations for a given material category.
        Checks Redis cache first; generates fresh if stale/missing.
        """
        sid = session_id or uuid.uuid4()

        # ── Check cache ───────────────────────────────────────────────────────
        cache_key = f"ai:vendor_rec:{material_category.upper()}"
        cached = await self._get_cache(cache_key)
        if cached:
            logger.info("Vendor rec cache hit: %s", cache_key)
            return {**cached, "from_cache": True}

        # ── Load vendor history from DB ────────────────────────────────────────
        vendor_history = await self._load_vendor_history(material_category)

        if not vendor_history:
            return {
                "error": f"No vendor history found for category '{material_category}'. "
                         "Add vendors and purchase orders to get recommendations.",
                "recommendations": [],
                "from_cache": False,
            }

        # ── Call LLM ──────────────────────────────────────────────────────────
        user_prompt = vendor_rec_user(pr_context, vendor_history)
        parsed, llm_result = await ai_client.complete_structured(
            system=VENDOR_REC_SYSTEM,
            user=user_prompt,
            schema=VendorRecommendationOutput,
            model=settings.AI_MODEL_FAST,
        )

        # ── Persist interaction ───────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.VENDOR_REC,
            user_id=user_id,
            input_text=pr_context.get("title", ""),
            input_metadata={"material_category": material_category, "pr_id": str(pr_id) if pr_id else None},
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
            return {"error": "Vendor recommendation failed", "recommendations": [], "from_cache": False}

        # ── Persist recommendation record ─────────────────────────────────────
        expires_at = datetime.now(UTC) + timedelta(hours=settings.AI_VENDOR_REC_CACHE_TTL_HOURS)
        rec_record = AIVendorRecommendation(
            interaction_id=interaction.id,
            pr_id=pr_id,
            material_category=material_category,
            recommendations=[r.model_dump() for r in parsed.recommendations],
            data_snapshot={"vendor_count": len(vendor_history), "data_date": date.today().isoformat()},
            expires_at=expires_at,
        )
        self.session.add(rec_record)
        await self.session.flush()

        result = {
            "interaction_id": str(interaction.id),
            "material_category": parsed.material_category,
            "recommendations": [r.model_dump() for r in parsed.recommendations],
            "analysis_summary": parsed.analysis_summary,
            "data_period": parsed.data_period,
            "from_cache": False,
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

        # ── Cache result ──────────────────────────────────────────────────────
        await self._set_cache(cache_key, result, ttl_hours=settings.AI_VENDOR_REC_CACHE_TTL_HOURS)
        return result

    async def _load_vendor_history(self, category: str) -> list[dict]:
        """
        Aggregate vendor performance from PO + GRN data for the given category.
        Returns a list of vendor dicts with scoring metrics.
        """
        from app.domain.vendor.models import Vendor
        from app.domain.procurement.models import PurchaseOrder, GoodsReceipt, GRNItem, POItem
        from app.domain.material.models import Material, MaterialGroup

        cutoff = date.today() - timedelta(days=365)

        try:
            # Raw performance query
            rows = await self.session.execute(text("""
                SELECT
                    v.id::text           AS vendor_id,
                    v.name               AS vendor_name,
                    v.status             AS status,
                    v.rating             AS rating,
                    v.payment_terms      AS payment_terms,
                    COUNT(DISTINCT po.id) AS po_count,
                    AVG(
                        EXTRACT(EPOCH FROM (gr.receipt_date::timestamp - po.order_date::timestamp))
                        / 86400.0
                    )                    AS avg_delivery_days,
                    po.delivery_date     AS target_days,
                    AVG(poi.unit_price)  AS avg_unit_price,
                    SUM(gi.quantity_rejected) / NULLIF(SUM(gi.quantity_delivered), 0) * 100
                                         AS rejection_rate_pct
                FROM vendors v
                JOIN purchase_orders po ON po.vendor_id = v.id
                JOIN po_items poi       ON poi.po_id = po.id
                LEFT JOIN goods_receipts gr ON gr.po_id = po.id AND gr.status = 'POSTED'
                LEFT JOIN grn_items gi  ON gi.po_item_id = poi.id
                WHERE po.order_date >= :cutoff
                  AND po.status NOT IN ('CANCELLED', 'DRAFT')
                GROUP BY v.id, v.name, v.status, v.rating, v.payment_terms, po.delivery_date
                HAVING COUNT(DISTINCT po.id) >= 1
                ORDER BY COUNT(DISTINCT po.id) DESC
                LIMIT 12
            """), {"cutoff": cutoff})

            history = []
            for row in rows:
                history.append({
                    "id": row.vendor_id,
                    "name": row.vendor_name,
                    "status": row.status,
                    "rating": float(row.rating) if row.rating else None,
                    "payment_terms": row.payment_terms,
                    "po_count": row.po_count or 0,
                    "avg_delivery_days": round(float(row.avg_delivery_days), 1) if row.avg_delivery_days else None,
                    "target_days": 30,  # default
                    "avg_unit_price": float(row.avg_unit_price) if row.avg_unit_price else None,
                    "rejection_rate_pct": float(row.rejection_rate_pct) if row.rejection_rate_pct else 0.0,
                    "price_index": 1.0,  # will be computed cross-vendor
                })

            # Compute relative price index
            prices = [v["avg_unit_price"] for v in history if v["avg_unit_price"]]
            if prices:
                avg_market = sum(prices) / len(prices)
                for v in history:
                    if v["avg_unit_price"] and avg_market > 0:
                        v["price_index"] = round(v["avg_unit_price"] / avg_market, 3)

            return history

        except Exception as e:
            logger.warning("Could not load vendor history from DB: %s", e)
            return []

    async def _get_cache(self, key: str) -> dict | None:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)
            raw = await r.get(key)
            await r.aclose()
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _set_cache(self, key: str, value: dict, ttl_hours: int = 24) -> None:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL)
            await r.setex(key, ttl_hours * 3600, json.dumps(value, default=str))
            await r.aclose()
        except Exception as e:
            logger.warning("Could not set Redis cache: %s", e)
