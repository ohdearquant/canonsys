"""Redact PII from text using LLM-based entity extraction.

This action provides provable evidence that AI processing could not have
been biased on PII it never saw - because it was redacted first.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from canon.enforcement import RequestContext

from ..types import PIICategory, PIIRedactionResult, RedactOptions
from .helpers import (
    apply_redactions_to_chunks,
    apply_redactions_to_text,
    build_placeholder_map,
    extract_pii_entities,
    format_chunks_for_extraction,
)

__all__ = [
    "RedactResult",
    "redact_text",
]


@dataclass(frozen=True, slots=True)
class RedactResult:
    """Result of redaction action."""

    success: bool
    result: PIIRedactionResult | None = None
    error: str | None = None


async def redact_text(
    options: RedactOptions,
    ctx: RequestContext,
) -> RedactResult:
    """Redact PII from text using LLM-based entity extraction.

    Uses a cheap, fast model (gemini-2.5-flash via OpenRouter) for
    high-accuracy entity extraction and redaction.

    Args:
        options: Redaction options (text or chunks, entity hints, context)
        ctx: Request context

    Returns:
        RedactResult with PIIRedactionResult on success, error on failure
    """
    if not options.text and not options.chunks:
        return RedactResult(
            success=False,
            error="Either text or chunks required for PII redaction",
        )

    start_time = time.time()

    # Format input for LLM
    if options.chunks:
        input_text = format_chunks_for_extraction(options.chunks)
    else:
        input_text = options.text or ""

    # Extract entities via LLM with retry
    entities, _meta, extraction_error = await extract_pii_entities(
        input_text,
        config_data={"model": options.model, "provider": options.provider},
        entity_hints=options.entity_hints,
        context=options.context,
    )

    if extraction_error:
        return RedactResult(
            success=False,
            error=f"PII extraction failed: {extraction_error}",
        )

    # Build placeholder mapping
    entity_map = build_placeholder_map(entities)

    # Apply redactions
    if options.chunks:
        redacted_chunks = apply_redactions_to_chunks(options.chunks, entity_map)
        redacted_text = None
    else:
        redacted_text = apply_redactions_to_text(input_text, entity_map)
        redacted_chunks = None

    # Calculate stats
    total_redactions = sum(e.occurrences for e in entities)
    categories = list(set(e.category for e in entities))

    processing_time_ms = int((time.time() - start_time) * 1000)

    result = PIIRedactionResult(
        redacted_text=redacted_text,
        redacted_chunks=redacted_chunks,
        detected_entities=entities,
        total_entities_detected=len(entities),
        total_redactions_applied=total_redactions,
        categories_detected=categories,
        company_count=len([e for e in entities if e.category == PIICategory.COMPANY]),
        person_count=len([e for e in entities if e.category == PIICategory.PERSON]),
        model_used=options.model,
        processing_time_ms=processing_time_ms,
    )

    return RedactResult(success=True, result=result)
