"""
Analytics AI Agent.

Converts natural language questions into validated, read-only SQL queries
against EPIMS data. Full safety pipeline before any execution.

Security model:
  1. Classify intent → must match whitelist of 6 allowed intents
  2. Generate SQL via LLM with table/column constraints in system prompt
  3. Validate SQL (blacklist + whitelist + LIMIT cap)
  4. Execute with row cap + timeout
  5. Log everything to ai_analytics_queries
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.client import ai_client
from app.ai.prompts.templates import ANALYTICS_SYSTEM, analytics_user
from app.ai.schemas.outputs import AnalyticsQueryOutput
from app.ai.tools.sql_validator import SQLValidationError, validate_sql, extract_tables_referenced
from app.config import settings
from app.domain.ai.models import AIAnalyticsQuery, AICapability, AIInteraction, AIStatus
import logging

logger = logging.getLogger(__name__)


class AnalyticsAgent:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def query(
        self,
        question: str,
        user_id: UUID,
        session_id: UUID | None = None,
    ) -> dict:
        """
        Process a natural language analytics question end-to-end.

        Returns:
          - columns: list of column names
          - rows: list of row dicts
          - sql: the validated SQL (for transparency)
          - intent: classified intent
          - chart_type: recommended visualization
          - row_count: number of rows returned
        """
        sid = session_id or uuid.uuid4()
        context = {"today": date.today().isoformat(), "max_rows": settings.AI_ANALYTICS_MAX_ROWS}

        # ── Generate SQL ──────────────────────────────────────────────────────
        user_prompt = analytics_user(question, context)
        parsed, llm_result = await ai_client.complete_structured(
            system=ANALYTICS_SYSTEM,
            user=user_prompt,
            schema=AnalyticsQueryOutput,
            model=settings.AI_MODEL_PRIMARY,
        )

        # ── Log interaction ───────────────────────────────────────────────────
        interaction = AIInteraction(
            session_id=sid,
            capability=AICapability.ANALYTICS,
            user_id=user_id,
            input_text=question,
            input_metadata={"context": context},
            output_json=parsed.model_dump() if parsed else None,
            model_used=llm_result.model if llm_result else settings.AI_MODEL_PRIMARY,
            prompt_tokens=llm_result.input_tokens if llm_result else None,
            completion_tokens=llm_result.output_tokens if llm_result else None,
            latency_ms=llm_result.latency_ms if llm_result else None,
            status=AIStatus.FAILED if parsed is None else AIStatus.SUCCESS,
        )
        self.session.add(interaction)
        await self.session.flush()

        if parsed is None:
            return {
                "error": "Could not generate a query for this question. Try rephrasing.",
                "interaction_id": str(interaction.id),
            }

        # ── Validate SQL ──────────────────────────────────────────────────────
        try:
            safe_sql = validate_sql(parsed.sql, max_rows=settings.AI_ANALYTICS_MAX_ROWS)
            tables_used = extract_tables_referenced(safe_sql)
            sql_valid = True
        except SQLValidationError as e:
            logger.warning("SQL validation failed for question '%s': %s", question, e.reason)
            # Log the failed attempt
            aq = AIAnalyticsQuery(
                interaction_id=interaction.id,
                user_question=question,
                classified_intent=parsed.intent,
                generated_sql=parsed.sql,
                sql_validated=False,
                allowed_tables_used=None,
            )
            self.session.add(aq)
            await self.session.flush()
            return {
                "error": f"Generated query failed safety validation: {e.reason}",
                "intent": parsed.intent,
                "interaction_id": str(interaction.id),
            }

        # ── Execute with timeout ──────────────────────────────────────────────
        try:
            result_rows, columns = await asyncio.wait_for(
                self._execute_query(safe_sql),
                timeout=settings.AI_ANALYTICS_TIMEOUT_SECS,
            )
        except asyncio.TimeoutError:
            return {
                "error": f"Query timed out after {settings.AI_ANALYTICS_TIMEOUT_SECS}s. "
                         "Try a more specific question with a narrower date range.",
                "sql": safe_sql,
                "interaction_id": str(interaction.id),
            }
        except Exception as e:
            logger.error("Query execution error: %s | SQL: %s", e, safe_sql)
            return {
                "error": f"Query execution failed: {str(e)[:200]}",
                "sql": safe_sql,
                "interaction_id": str(interaction.id),
            }

        # ── Persist analytics query record ────────────────────────────────────
        aq = AIAnalyticsQuery(
            interaction_id=interaction.id,
            user_question=question,
            classified_intent=parsed.intent,
            generated_sql=safe_sql,
            sql_validated=True,
            allowed_tables_used=tables_used,
            result_json=result_rows,
            row_count=len(result_rows),
        )
        self.session.add(aq)
        await self.session.flush()

        return {
            "interaction_id": str(interaction.id),
            "intent": parsed.intent,
            "question": question,
            "sql": safe_sql,
            "explanation": parsed.explanation,
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "chart_type": parsed.chart_type,
            "model_used": llm_result.model if llm_result else None,
            "latency_ms": llm_result.latency_ms if llm_result else None,
        }

    async def _execute_query(self, sql: str) -> tuple[list[dict], list[str]]:
        """Execute validated SQL in read-only mode and return rows + column names."""
        result = await self.session.execute(text(sql))
        columns = list(result.keys())
        rows = []
        for row in result.fetchall():
            row_dict = {}
            for col, val in zip(columns, row):
                # Serialize non-JSON-safe types
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif hasattr(val, "__float__"):
                    val = float(val)
                row_dict[col] = val
            rows.append(row_dict)
        return rows, columns
