"""Redaction feature - vertical slice for PII management.

This module provides the complete PII detection and redaction domain:
- Types: PIICategory, PIIEntity, PIIRedactionResult, ScanResult, etc.
- Actions: redact_text, segment_text, scan_text
- Gates: RegexGate, SemanticGate for binary PII detection
- Exceptions: BlockingPIIDetectedError, PIIDetectionError, etc.
- Service: RedactionService with gate-protected operations

Two detection modes:
1. LLM-based (semantic) - For names, companies, context-dependent entities
   - redact: Extract and redact PII using LLM
   - segment: Segment text into speaker turns

2. Regex-based (pattern) - For SSN, credit card, phone, email
   - scan: Safety gate before persistence

Usage:
    from hub.services.redaction import (
        # Types
        PIICategory,
        PIIEntity,
        PIIRedactionResult,
        RedactOptions,
        # Actions
        redact_text,
        scan_text,
        # Gates
        RegexGate,
        regex_gate,
        # Exceptions
        BlockingPIIDetectedError,
    )

For quick safety checks:
    from hub.services.redaction import regex_gate

    result = regex_gate.check(evidence_data)
    if result.is_blocked:
        raise BlockingPIIDetectedError(
            result.detected_categories,
            result.detection_count,
        )
"""

# Actions
from .actions import (
    DEFAULT_PII_CONFIG,
    MAX_RETRIES,
    RETRY_DELAY_MS,
    LLMInvocationMeta,
    RedactResult,
    ScanActionResult,
    SegmentResult,
    apply_redactions_to_chunks,
    apply_redactions_to_text,
    build_placeholder_map,
    extract_pii_entities,
    extract_segment_boundaries,
    format_chunks_for_extraction,
    redact_text,
    scan_text,
    segment_text,
    slice_text_at_boundaries,
    validate_boundaries,
)

# Exceptions
from .exceptions import (
    BlockingPIIDetectedError,
    InvalidCategoryError,
    PIIDetectionError,
    RedactionError,
    RedactionModelError,
    SegmentationError,
)

# Gates
from .gates import GateMode, RegexGate, SemanticGate, regex_gate, regex_gate_full

# Service
from .service import RedactionService

# Types
from .types import (
    CATEGORY_SENSITIVITY,
    PIICategory,
    PIIDetection,
    PIIEntity,
    PIIGateResult,
    PIIPatterns,
    PIIRedactionResult,
    RedactedChunk,
    RedactOptions,
    ScanOptions,
    ScanResult,
    SegmentationResult,
    SegmentBoundary,
    SegmentOptions,
    SensitivityLevel,
    SpeakerRole,
    TextChunk,
)

__all__ = [
    # Types - Category
    "PIICategory",
    "SensitivityLevel",
    "CATEGORY_SENSITIVITY",
    # Types - Patterns
    "PIIPatterns",
    "SpeakerRole",
    # Types - Entity
    "PIIEntity",
    "PIIDetection",
    # Types - Chunk
    "TextChunk",
    "RedactedChunk",
    "SegmentBoundary",
    # Types - Options
    "RedactOptions",
    "SegmentOptions",
    "ScanOptions",
    # Types - Results
    "PIIRedactionResult",
    "ScanResult",
    "SegmentationResult",
    "PIIGateResult",
    # Actions - Redact
    "redact_text",
    "RedactResult",
    # Actions - Segment
    "segment_text",
    "SegmentResult",
    # Actions - Scan
    "scan_text",
    "ScanActionResult",
    # Actions - Helpers
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
    # Gates
    "GateMode",
    "RegexGate",
    "SemanticGate",
    "regex_gate",
    "regex_gate_full",
    # Exceptions
    "RedactionError",
    "PIIDetectionError",
    "SegmentationError",
    "InvalidCategoryError",
    "BlockingPIIDetectedError",
    "RedactionModelError",
    # Service
    "RedactionService",
]
