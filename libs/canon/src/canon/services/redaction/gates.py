"""PII gates - binary detection with no side effects.

Two gate types for different use cases:
1. RegexGate - Fast pattern matching (SSN, CC, phone, email)
   Use for: Pre-persistence validation, inline checks

2. SemanticGate - LLM-based detection (names, companies, context-aware)
   Use for: Content review, transcript analysis

Both gates are binary (pass/fail) with no transformations.
They detect PII presence - redaction is a separate operation.
"""

from __future__ import annotations

import time
from enum import Enum

from .types import (
    CATEGORY_SENSITIVITY,
    PIICategory,
    PIIGateResult,
    PIIPatterns,
    SensitivityLevel,
)

__all__ = [
    "GateMode",
    "RegexGate",
    "SemanticGate",
    "regex_gate",
    "regex_gate_full",
]


class GateMode(str, Enum):
    """Gate detection mode."""

    BLOCKING_ONLY = "blocking_only"  # Only highly sensitive (SSN, CC, passport)
    ALL = "all"  # All detectable patterns


class RegexGate:
    """Gate for fast regex-based PII detection.

    Binary check - returns pass/fail, no transformations.
    Uses compiled regex patterns for SSN, credit cards, etc.

    Use for:
    - Pre-persistence validation (Evidence, logs)
    - Inline validation in hot paths
    - Defense-in-depth safety checks

    Usage:
        gate = RegexGate()
        result = gate.check(text)
        if result.is_blocked:
            raise PIIDetectedError(result.block_reason)
    """

    name = "pii.regex"
    version = "1.0.0"
    description = "Fast regex-based PII detection"

    def __init__(self, mode: GateMode = GateMode.BLOCKING_ONLY):
        """Initialize gate.

        Args:
            mode: Detection mode.
                BLOCKING_ONLY: Only check for highly sensitive (SSN, CC, passport)
                ALL: Check all patterns including email, phone, IP
        """
        self.mode = mode

    def check(self, text: str) -> PIIGateResult:
        """Check text for PII patterns.

        This is a pure function - no side effects, no evidence emission.
        Fast enough for inline validation.

        Args:
            text: Text to scan

        Returns:
            PIIGateResult with pass/fail status
        """
        start_time = time.time()

        # Get patterns based on mode
        if self.mode == GateMode.BLOCKING_ONLY:
            patterns = PIIPatterns.get_blocking_patterns()
        else:
            patterns = PIIPatterns.get_patterns()

        # Scan for matches
        detections: list[tuple[PIICategory, int]] = []
        blocking_count = 0

        for category, pattern in patterns.items():
            matches = list(pattern.finditer(text))
            if matches:
                detections.append((category, len(matches)))
                sensitivity = CATEGORY_SENSITIVITY.get(category, SensitivityLevel.CONFIDENTIAL)
                if sensitivity == SensitivityLevel.HIGHLY_SENSITIVE:
                    blocking_count += len(matches)

        # Build result
        total_count = sum(count for _, count in detections)
        categories = [cat for cat, _ in detections]

        passed = blocking_count == 0
        block_reason = None
        if not passed:
            blocked_cats = [
                cat.value
                for cat, _ in detections
                if CATEGORY_SENSITIVITY.get(cat) == SensitivityLevel.HIGHLY_SENSITIVE
            ]
            block_reason = f"Highly sensitive PII detected: {', '.join(set(blocked_cats))}"

        scan_time_ms = int((time.time() - start_time) * 1000)

        return PIIGateResult(
            gate_id=self.name,
            passed=passed,
            block_reason=block_reason,
            detected_categories=categories,
            detection_count=total_count,
            blocking_count=blocking_count,
            scan_time_ms=scan_time_ms,
        )

    async def check_async(self, text: str) -> PIIGateResult:
        """Async wrapper for check.

        Same as check() but for async contexts.
        """
        return self.check(text)


class SemanticGate:
    """Gate for LLM-based semantic PII detection.

    Binary check - returns pass/fail, no transformations.
    Uses LLM to detect context-dependent PII (names, companies).

    Use for:
    - Content review before publication
    - Transcript analysis
    - Cases where context matters (e.g., "John" as name vs product)

    Usage:
        gate = SemanticGate()
        result = await gate.check(text, context="interview transcript")
        if result.is_blocked:
            raise PIIDetectedError(result.block_reason)
    """

    name = "pii.semantic"
    version = "1.0.0"
    description = "LLM-based semantic PII detection"

    def __init__(
        self,
        *,
        model: str = "google/gemini-2.5-flash",
        provider: str = "openrouter",
        block_on_detection: bool = True,
    ):
        """Initialize gate.

        Args:
            model: LLM model to use for detection
            provider: Provider for the model
            block_on_detection: If True, any PII detection blocks.
                               If False, only highly sensitive blocks.
        """
        self.model = model
        self.provider = provider
        self.block_on_detection = block_on_detection

    async def check(
        self,
        text: str,
        *,
        context: str | None = None,
        entity_hints: dict[str, list[str]] | None = None,
    ) -> PIIGateResult:
        """Check text for PII using LLM.

        This is a detection-only operation - no redaction.

        Args:
            text: Text to scan
            context: Optional context hint (e.g., "interview transcript")
            entity_hints: Known entities to look for

        Returns:
            PIIGateResult with pass/fail status
        """

        from ._llm import iModel

        start_time = time.time()

        system_prompt = """You are a PII detection expert. Identify if text contains personally identifiable information.

Detect these PII types:
- person: People's names
- company: Company/organization names
- school: Educational institutions
- location: Specific locations (cities, addresses)
- email: Email addresses
- phone: Phone numbers
- date: Specific dates that could be identifying

Return JSON: {"contains_pii": true/false, "categories": ["person", "company"], "count": 5}
Be thorough - report all PII found."""

        # Build hints
        hints = ""
        if entity_hints:
            for category, values in entity_hints.items():
                hints += f"\nKnown {category}: {', '.join(values)}"
        if context:
            hints += f"\nContext: {context}"

        user_prompt = f"""Does this text contain PII?{hints}

<text>
{text}
</text>

Return JSON with contains_pii (bool), categories (list), and count (int)."""

        contains_pii = False
        categories: list[PIICategory] = []
        count = 0

        try:
            async with iModel(model=self.model, provider=self.provider) as llm:
                response = await llm.invoke(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )

                # Parse response inside async with to ensure it's bound
                if response.response and response.response.data:
                    data = response.response.data
                    if isinstance(data, dict):
                        contains_pii = data.get("contains_pii", False)
                        cat_strs = data.get("categories", [])
                        count = data.get("count", 0)

                        for cat_str in cat_strs:
                            try:
                                categories.append(PIICategory(cat_str))
                            except ValueError:
                                pass

            scan_time_ms = int((time.time() - start_time) * 1000)

            # Determine pass/fail
            if self.block_on_detection:
                passed = not contains_pii
            else:
                # Only block on highly sensitive
                blocking = [
                    c
                    for c in categories
                    if CATEGORY_SENSITIVITY.get(c) == SensitivityLevel.HIGHLY_SENSITIVE
                ]
                passed = len(blocking) == 0

            block_reason = None
            if not passed:
                block_reason = f"PII detected: {', '.join(c.value for c in categories)}"

            return PIIGateResult(
                gate_id=self.name,
                passed=passed,
                block_reason=block_reason,
                detected_categories=categories,
                detection_count=count,
                blocking_count=count if not passed else 0,
                scan_time_ms=scan_time_ms,
            )

        except Exception as e:
            # On LLM failure, fail closed (block)
            scan_time_ms = int((time.time() - start_time) * 1000)
            return PIIGateResult(
                gate_id=self.name,
                passed=False,
                block_reason=f"PII detection failed: {e}",
                detected_categories=[],
                detection_count=0,
                blocking_count=0,
                scan_time_ms=scan_time_ms,
            )


# Gate instances for convenient import

# Default regex gate - blocks only highly sensitive PII
regex_gate = RegexGate(mode=GateMode.BLOCKING_ONLY)

# Full regex gate - detects all patterns
regex_gate_full = RegexGate(mode=GateMode.ALL)
