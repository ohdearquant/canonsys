"""Redaction domain actions.

All redaction operations in one place:
- redact: LLM-based PII extraction and redaction
- segment: LLM-based speaker segmentation
- scan: Regex-based PII detection (safety gate)
"""

from .helpers import (
    DEFAULT_PII_CONFIG,
    MAX_RETRIES,
    RETRY_DELAY_MS,
    LLMInvocationMeta,
    apply_redactions_to_chunks,
    apply_redactions_to_text,
    build_placeholder_map,
    extract_pii_entities,
    extract_segment_boundaries,
    format_chunks_for_extraction,
    slice_text_at_boundaries,
    validate_boundaries,
)
from .redact import RedactResult, redact_text
from .scan import ScanActionResult, scan_text
from .segment import SegmentResult, segment_text

__all__ = [
    # Redact
    "redact_text",
    "RedactResult",
    # Segment
    "segment_text",
    "SegmentResult",
    # Scan
    "scan_text",
    "ScanActionResult",
    # Helpers
    "LLMInvocationMeta",
    "extract_pii_entities",
    "extract_segment_boundaries",
    "build_placeholder_map",
    "apply_redactions_to_text",
    "apply_redactions_to_chunks",
    "validate_boundaries",
    "slice_text_at_boundaries",
    "format_chunks_for_extraction",
    "MAX_RETRIES",
    "RETRY_DELAY_MS",
    "DEFAULT_PII_CONFIG",
]
