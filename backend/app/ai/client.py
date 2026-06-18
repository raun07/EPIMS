"""
Anthropic API client wrapper for EPIMS AI Copilot.

Responsibilities:
- Single entry point for all LLM calls
- Retry with exponential backoff (max 2 retries)
- Token counting and cost estimation before call
- Latency tracking
- Structured JSON output enforcement + Pydantic validation
- Graceful degradation: returns None on failure (callers handle)
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Cost per million tokens (USD) — update as pricing changes
_COST_PER_MTK = {
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.80,  "output": 4.00},
}

def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_PER_MTK.get(model, {"input": 3.00, "output": 15.00})
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


class LLMResult:
    __slots__ = ("content", "model", "input_tokens", "output_tokens", "latency_ms", "cost_usd")

    def __init__(
        self,
        content: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
    ) -> None:
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.cost_usd = _estimate_cost(model, input_tokens, output_tokens)


class AIClient:
    """
    Wrapper around anthropic.AsyncAnthropic.
    All AI agents call this — never the SDK directly.
    """

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            if not settings.ANTHROPIC_API_KEY:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Add it to your .env file to enable AI features."
                )
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        image_base64: str | None = None,
        image_media_type: str = "application/pdf",
    ) -> LLMResult | None:
        """
        Send a message and return an LLMResult.
        Returns None on all failures (callers must handle None gracefully).
        """
        if not settings.AI_ENABLED:
            logger.info("AI disabled via AI_ENABLED=False — skipping call")
            return None

        effective_model = model or settings.AI_MODEL_PRIMARY
        effective_max_tokens = max_tokens or settings.AI_MAX_TOKENS
        effective_temp = temperature if temperature is not None else settings.AI_TEMPERATURE

        # Build message content
        if image_base64:
            content: list[dict] = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_base64,
                    },
                },
                {"type": "text", "text": user},
            ]
        else:
            content = [{"type": "text", "text": user}]

        client = self._get_client()
        last_err: Exception | None = None

        for attempt in range(3):
            try:
                t0 = time.monotonic()
                response = await client.messages.create(
                    model=effective_model,
                    max_tokens=effective_max_tokens,
                    temperature=effective_temp,
                    system=system,
                    messages=[{"role": "user", "content": content}],
                )
                latency_ms = int((time.monotonic() - t0) * 1000)

                raw_text = response.content[0].text if response.content else ""
                return LLMResult(
                    content=raw_text,
                    model=effective_model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    latency_ms=latency_ms,
                )

            except anthropic.RateLimitError as e:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                logger.warning("Rate limit hit (attempt %d). Waiting %ds. %s", attempt + 1, wait, e)
                import asyncio
                await asyncio.sleep(wait)
                last_err = e

            except anthropic.APIStatusError as e:
                logger.error("Anthropic API error (attempt %d): %s %s", attempt + 1, e.status_code, e.message)
                last_err = e
                if e.status_code < 500:
                    break  # Don't retry 4xx errors

            except Exception as e:
                logger.exception("Unexpected error calling Anthropic (attempt %d): %s", attempt + 1, e)
                last_err = e
                break

        logger.error("All LLM attempts failed. Last error: %s", last_err)
        return None

    async def complete_structured(
        self,
        system: str,
        user: str,
        schema: Type[T],
        model: str | None = None,
        max_tokens: int | None = None,
        image_base64: str | None = None,
        image_media_type: str = "application/pdf",
    ) -> tuple[T | None, LLMResult | None]:
        """
        Call LLM and parse the result into a Pydantic model.
        Returns (parsed_model, llm_result).
        If parsing fails after retry, returns (None, llm_result).
        """
        schema_json = schema.model_json_schema()
        enhanced_system = (
            f"{system}\n\n"
            f"OUTPUT REQUIREMENT: Respond ONLY with a valid JSON object matching this schema. "
            f"No preamble, no explanation, no markdown fences.\n"
            f"Schema: {json.dumps(schema_json, indent=2)}"
        )

        result = await self.complete(
            system=enhanced_system,
            user=user,
            model=model,
            max_tokens=max_tokens,
            image_base64=image_base64,
            image_media_type=image_media_type,
        )
        if result is None:
            return None, None

        # Strip possible markdown fences
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
            parsed = schema.model_validate(data)
            return parsed, result
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning("JSON parse failed on first attempt (%s). Retrying with error context.", e)

        # Retry with error feedback
        retry_system = (
            f"{system}\n\n"
            f"Your previous response failed JSON validation with error: {e}\n"
            f"Output ONLY valid JSON matching this schema: {json.dumps(schema_json)}"
        )
        result2 = await self.complete(
            system=retry_system,
            user=user,
            model=model,
            max_tokens=max_tokens,
        )
        if result2 is None:
            return None, result

        raw2 = result2.content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        try:
            data2 = json.loads(raw2)
            parsed2 = schema.model_validate(data2)
            return parsed2, result2
        except (json.JSONDecodeError, ValidationError) as e2:
            logger.error("Structured output failed after retry: %s", e2)
            return None, result2


# Singleton — import and use directly
ai_client = AIClient()
