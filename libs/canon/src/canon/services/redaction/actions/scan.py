"""Scan text for PII using regex patterns.

This is a SAFETY GATE before persistence. Use to validate that
data doesn't contain highly sensitive PII like SSN, credit cards.

Unlike LLM-based redaction, this is fast and deterministic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from canon.enforcement import RequestContext

from ..types import (
    CATEGORY_SENSITIVITY,
    PIIDetection,
    PIIPatterns,
    ScanOptions,
    ScanResult,
    SensitivityLevel,
)

__all__ = [
    "ScanActionResult",
    "scan_text",
]


@dataclass(frozen=True, slots=True)
class ScanActionResult:
    """Result of scan action."""

    success: bool
    result: ScanResult | None = None
    error: str | None = None


async def scan_text(
    options: ScanOptions,
    ctx: RequestContext,
) -> ScanActionResult:
    """Scan text for PII using regex patterns.

    This is a SAFETY GATE before persistence. Use to validate that
    data doesn't contain highly sensitive PII like SSN, credit cards.

    Args:
        options: Scan options (text, block_only mode, fail_on_detection)
        ctx: Request context

    Returns:
        ScanActionResult with ScanResult on success, error on failure
    """
    if not options.text:
        return ScanActionResult(
            success=False,
            error="text is required for PII scan",
        )

    start_time = time.time()

    # Get patterns based on mode
    if options.block_only:
        patterns = PIIPatterns.get_blocking_patterns()
    else:
        patterns = PIIPatterns.get_patterns()

    # Scan for matches
    detections: list[PIIDetection] = []
    blocking_violations = 0

    for category, pattern in patterns.items():
        sensitivity = CATEGORY_SENSITIVITY.get(category, SensitivityLevel.CONFIDENTIAL)

        for match in pattern.finditer(options.text):
            detections.append(
                PIIDetection(
                    category=category,
                    sensitivity=sensitivity,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    # Never store matched value - positions only
                    matched_value="[REDACTED]",
                    confidence=0.95,
                )
            )

            # Count blocking violations
            if sensitivity == SensitivityLevel.HIGHLY_SENSITIVE:
                blocking_violations += 1

    # Sort by position
    detections.sort(key=lambda d: d.start_pos)

    # Build result
    categories_detected = list(set(d.category for d in detections))
    safe_to_persist = blocking_violations == 0

    block_reason = None
    if not safe_to_persist:
        blocked_categories = [
            d.category.value
            for d in detections
            if d.sensitivity == SensitivityLevel.HIGHLY_SENSITIVE
        ]
        block_reason = f"Highly sensitive PII detected: {', '.join(set(blocked_categories))}"

    processing_time_ms = int((time.time() - start_time) * 1000)

    result = ScanResult(
        detections=detections,
        total_detections=len(detections),
        blocking_violations=blocking_violations,
        categories_detected=categories_detected,
        safe_to_persist=safe_to_persist,
        block_reason=block_reason,
        text_length=len(options.text),
        scan_time_ms=processing_time_ms,
    )

    # Fail if requested and violations found
    if options.fail_on_detection and not safe_to_persist:
        return ScanActionResult(
            success=False,
            result=result,
            error=block_reason or "PII detected",
        )

    return ScanActionResult(success=True, result=result)
