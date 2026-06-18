"""
Document Intelligence Agent.

Extracts structured data from uploaded PDF invoices using Claude's
vision capability. Supports S3/MinIO-stored files and direct base64 uploads.

Flow:
  1. Fetch PDF bytes (from S3 key or direct upload)
  2. Convert to base64
  3. Call Claude with vision + structured output schema
  4. Validate extracted data
  5. Persist to ai_document_extractions
  6. Optionally auto-link to an existing invoice record
"""
from __future__ import annotations

import base64
import uuid
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import DOCUMENT_INTEL_SYSTEM, document_intel_user
from app.ai.schemas.outputs import DocumentExtractionOutput
from app.config import settings
from app.domain.ai.models import (
    AICapability, AIDocumentExtraction, AIInteraction, AIStatus, DocExtractionStatus,
)
import logging

logger = logging.getLogger(__name__)


class DocumentIntelligenceAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def extract_from_bytes(
        self,
        pdf_bytes: bytes,
        filename: str,
        user_id: UUID,
        s3_key: str | None = None,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Extract invoice data from PDF bytes.
        Returns structured extraction result ready for user review.
        """
        sid = session_id or uuid.uuid4()

        # ── Encode PDF as base64 ──────────────────────────────────────────────
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

        # ── Load known vendor names for fuzzy matching hint ───────────────────
        known_vendors = await self._load_known_vendors()

        # ── Call LLM with vision ──────────────────────────────────────────────
        user_prompt = document_intel_user(filename, known_vendors)
        parsed, llm_result = await ai_client.complete_structured(
            system=DOCUMENT_INTEL_SYSTEM,
            user=user_prompt,
            schema=DocumentExtractionOutput,
            model=settings.AI_MODEL_VISION,
            image_base64=pdf_b64,
            image_media_type="application/pdf",
        )

        # ── Persist interaction ───────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.DOCUMENT_INTEL,
            user_id=user_id,
            input_text=filename,
            input_metadata={"filename": filename, "s3_key": s3_key, "file_size_kb": len(pdf_bytes) // 1024},
            output_json=parsed.model_dump() if parsed else None,
            model_used=llm_result.model if llm_result else settings.AI_MODEL_VISION,
            prompt_tokens=llm_result.input_tokens if llm_result else None,
            completion_tokens=llm_result.output_tokens if llm_result else None,
            latency_ms=llm_result.latency_ms if llm_result else None,
            status=AIStatus.SUCCESS if parsed else AIStatus.FAILED,
        )
        self.session.add(interaction)
        await self.session.flush()

        if parsed is None:
            return {
                "error": "Document extraction failed. Please ensure the file is a clear, readable PDF.",
                "interaction_id": str(interaction.id),
            }

        # ── Parse dates safely ────────────────────────────────────────────────
        invoice_date = self._parse_date(parsed.invoice_date)
        due_date = self._parse_date(parsed.due_date)

        # ── Persist extraction ────────────────────────────────────────────────
        extraction = AIDocumentExtraction(
            interaction_id=interaction.id,
            source_filename=filename,
            source_s3_key=s3_key,
            extracted_invoice_number=parsed.invoice_number,
            extracted_vendor_name=parsed.vendor_name,
            extracted_po_number=parsed.po_number,
            extracted_date=invoice_date,
            extracted_due_date=due_date,
            extracted_line_items=[i.model_dump() for i in parsed.line_items],
            extracted_total=Decimal(str(parsed.total_amount)) if parsed.total_amount else None,
            extracted_tax_total=Decimal(str(parsed.tax_total)) if parsed.tax_total else None,
            extracted_currency=parsed.currency,
            confidence_score=Decimal(str(parsed.confidence_score)),
            raw_extraction=parsed.model_dump(),
            status=DocExtractionStatus.EXTRACTED,
        )
        self.session.add(extraction)
        await self.session.flush()

        # ── Try to match to existing PO ───────────────────────────────────────
        po_match = None
        if parsed.po_number:
            po_match = await self._find_po(parsed.po_number)

        # ── Try to match vendor ───────────────────────────────────────────────
        vendor_match = None
        if parsed.vendor_name:
            vendor_match = await self._find_vendor(parsed.vendor_name, parsed.vendor_name[:6] if parsed.vendor_name else "")

        return {
            "extraction_id": str(extraction.id),
            "interaction_id": str(interaction.id),
            "invoice_number": parsed.invoice_number,
            "vendor_name": parsed.vendor_name,
            "vendor_gstin": parsed.vendor_gstin,
            "vendor_match": vendor_match,
            "po_number": parsed.po_number,
            "po_match": po_match,
            "invoice_date": parsed.invoice_date,
            "due_date": parsed.due_date,
            "currency": parsed.currency,
            "subtotal": parsed.subtotal,
            "tax_total": parsed.tax_total,
            "total_amount": parsed.total_amount,
            "line_items": [i.model_dump() for i in parsed.line_items],
            "payment_terms": parsed.payment_terms,
            "confidence_score": parsed.confidence_score,
            "extraction_notes": parsed.extraction_notes,
            "ready_to_create": parsed.confidence_score >= 0.7 and parsed.invoice_number is not None,
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

    async def link_to_invoice(self, extraction_id: UUID, invoice_id: UUID) -> dict:
        """Link an extraction result to an invoice record after user review."""
        from sqlalchemy import select
        result = await self.session.execute(
            select(AIDocumentExtraction).where(AIDocumentExtraction.id == extraction_id)
        )
        extraction = result.scalar_one_or_none()
        if not extraction:
            return {"error": "Extraction not found"}

        extraction.invoice_id = invoice_id
        extraction.status = DocExtractionStatus.LINKED
        await self.session.flush()
        return {"status": "linked", "extraction_id": str(extraction_id), "invoice_id": str(invoice_id)}

    async def _load_known_vendors(self) -> list[str]:
        from sqlalchemy import select
        from app.domain.vendor.models import Vendor
        try:
            rows = await self.session.execute(select(Vendor.name).limit(50))
            return [r[0] for r in rows]
        except Exception:
            return []

    async def _find_po(self, po_number: str) -> dict | None:
        from sqlalchemy import select
        from app.domain.procurement.models import PurchaseOrder
        try:
            result = await self.session.execute(
                select(PurchaseOrder.id, PurchaseOrder.po_number, PurchaseOrder.total_amount)
                .where(PurchaseOrder.po_number.ilike(f"%{po_number}%"))
                .limit(1)
            )
            row = result.first()
            if row:
                return {"id": str(row.id), "po_number": row.po_number, "total_amount": float(row.total_amount or 0)}
        except Exception:
            pass
        return None

    async def _find_vendor(self, vendor_name: str, gstin_prefix: str) -> dict | None:
        from sqlalchemy import select
        from app.domain.vendor.models import Vendor
        try:
            result = await self.session.execute(
                select(Vendor.id, Vendor.name, Vendor.vendor_number)
                .where(Vendor.name.ilike(f"%{vendor_name[:15]}%"))
                .limit(1)
            )
            row = result.first()
            if row:
                return {"id": str(row.id), "name": row.name, "vendor_number": row.vendor_number}
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None
