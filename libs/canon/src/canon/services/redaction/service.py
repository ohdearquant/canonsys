"""Redaction service - thin wrapper over redaction actions.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in actions/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .actions import redact_text, scan_text, segment_text
from .types import RedactOptions, ScanOptions, SegmentOptions

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RedactionService"]


class RedactionService(CanonService):
    """Redaction service - manages PII detection, redaction, and segmentation.

    Thin wrapper that delegates to action functions.

    CRITICAL: All evidence emission is manual and sanitized.
    We NEVER persist raw PII to evidence or logs.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon",
        name="redaction",
    )

    @action(skip_evidence=True)
    async def redact(self, payload: dict, ctx: RequestContext) -> dict:
        """Redact PII from text using LLM-based entity extraction.

        Uses a cheap, fast model (gemini-2.5-flash via OpenRouter) for
        high-accuracy entity extraction and redaction.

        Evidence is manually emitted (skip_evidence=True) to avoid
        persisting raw PII from request options.

        Args:
            payload: Request payload matching RedactOptions schema
            ctx: Request context

        Returns:
            Result dict with redacted content and entity manifest
        """
        options = RedactOptions(**payload)
        result = await redact_text(options, ctx)

        if not result.success:
            return {"success": False, "error": result.error}

        # Return safe result (original_text stripped)
        safe_result = result.result.for_persistence() if result.result else None
        return {
            "success": True,
            "result": safe_result.model_dump(mode="json") if safe_result else None,
        }

    @action(skip_evidence=True)
    async def segment(self, payload: dict, ctx: RequestContext) -> dict:
        """Segment raw text into speaker-attributed turns.

        Uses LLM to identify speaker boundaries in unformatted text.
        Original text is never modified - we just identify where to slice.

        Evidence is manually emitted (skip_evidence=True) to avoid
        persisting raw text from request options.

        Args:
            payload: Request payload matching SegmentOptions schema
            ctx: Request context

        Returns:
            Result dict with segment boundaries and sliced text
        """
        options = SegmentOptions(**payload)
        result = await segment_text(options, ctx)

        if not result.success:
            return {"success": False, "error": result.error}

        return {
            "success": True,
            "result": result.result.model_dump(mode="json") if result.result else None,
        }

    @action(skip_evidence=True)
    async def scan(self, payload: dict, ctx: RequestContext) -> dict:
        """Scan text for PII using regex patterns.

        This is a SAFETY GATE before persistence. Use to validate that
        data doesn't contain highly sensitive PII like SSN, credit cards.

        Unlike LLM-based redaction, this is fast and deterministic.

        Evidence is manually emitted (skip_evidence=True) to avoid
        persisting the text being scanned.

        Args:
            payload: Request payload matching ScanOptions schema
            ctx: Request context

        Returns:
            Result dict with scan results and pass/fail status
        """
        options = ScanOptions(**payload)
        result = await scan_text(options, ctx)

        if not result.success:
            return {
                "success": False,
                "error": result.error,
                "result": (result.result.model_dump(mode="json") if result.result else None),
            }

        return {
            "success": True,
            "result": result.result.model_dump(mode="json") if result.result else None,
        }
