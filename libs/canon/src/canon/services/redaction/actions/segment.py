"""Segment raw text into speaker-attributed turns.

Uses LLM to identify speaker boundaries in unformatted text.
Original text is never modified - we just identify where to slice.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from canon.enforcement import RequestContext

from ..types import SegmentationResult, SegmentOptions, SpeakerRole
from .helpers import extract_segment_boundaries, slice_text_at_boundaries

__all__ = [
    "SegmentResult",
    "segment_text",
]


@dataclass(frozen=True, slots=True)
class SegmentResult:
    """Result of segmentation action."""

    success: bool
    result: SegmentationResult | None = None
    error: str | None = None


async def segment_text(
    options: SegmentOptions,
    ctx: RequestContext,
) -> SegmentResult:
    """Segment raw text into speaker-attributed turns.

    Uses LLM to identify speaker boundaries in unformatted text.
    Original text is never modified - we just identify where to slice.

    Args:
        options: Segmentation options (raw_text, speaker hints, context)
        ctx: Request context

    Returns:
        SegmentResult with SegmentationResult on success, error on failure
    """
    if not options.raw_text or not options.raw_text.strip():
        return SegmentResult(
            success=False,
            error="raw_text is required for segmentation",
        )

    start_time = time.time()

    # Extract boundaries via LLM with retry
    boundaries, _meta, seg_error = await extract_segment_boundaries(
        options.raw_text,
        config_data={"model": options.model, "provider": options.provider},
        speaker_a_hint=options.speaker_a_hint,
        speaker_b_hint=options.speaker_b_hint,
        context=options.context,
    )

    # Note: seg_error may contain warning about fallback but boundaries will still exist
    if seg_error and not boundaries:
        return SegmentResult(
            success=False,
            error=f"Segmentation failed: {seg_error}",
        )

    # Slice original text at boundaries to create segments
    segments = slice_text_at_boundaries(options.raw_text, boundaries)

    # Count by speaker
    speaker_a_count = sum(
        1 for b in boundaries if b.speaker in (SpeakerRole.SPEAKER_A, SpeakerRole.LEAN_A)
    )
    speaker_b_count = sum(
        1 for b in boundaries if b.speaker in (SpeakerRole.SPEAKER_B, SpeakerRole.LEAN_B)
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    result = SegmentationResult(
        boundaries=boundaries,
        original_text=options.raw_text,
        original_length=len(options.raw_text),
        segments=segments,
        total_segments=len(boundaries),
        speaker_a_segments=speaker_a_count,
        speaker_b_segments=speaker_b_count,
        model_used=options.model,
        processing_time_ms=processing_time_ms,
    )

    return SegmentResult(success=True, result=result)
