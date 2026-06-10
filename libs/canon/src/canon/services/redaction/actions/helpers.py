"""Helper functions for redaction actions.

Contains LLM extraction logic, placeholder mapping, and boundary validation.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..types import (
    PIICategory,
    PIIEntity,
    RedactedChunk,
    SegmentBoundary,
    SpeakerRole,
    TextChunk,
)

if TYPE_CHECKING:
    from .._llm import iModel

__all__ = [
    "DEFAULT_PII_CONFIG",
    "MAX_RETRIES",
    "RETRY_DELAY_MS",
    "LLMInvocationMeta",
    "apply_redactions_to_chunks",
    "apply_redactions_to_text",
    "build_placeholder_map",
    "extract_pii_entities",
    "extract_segment_boundaries",
    "format_chunks_for_extraction",
    "slice_text_at_boundaries",
    "validate_boundaries",
]

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_MS = 500

# Default config for PII extraction (used if no model/config provided)
DEFAULT_PII_CONFIG = {
    "provider": "openrouter",
    "model": "google/gemini-2.5-flash",
    "endpoint": "chat/completions",
}

# LLM system prompts
_PII_SYSTEM_PROMPT = """You are a PII detection expert. Identify personally identifiable information in text.

Detect these PII types:
- person: People's names
- company: Company/organization names
- school: Educational institutions
- location: Specific locations (cities, addresses)
- email: Email addresses
- phone: Phone numbers
- date: Specific dates that could be identifying
- address: Physical addresses

For each entity, provide:
- category: One of the categories above
- original_text: The exact text as it appears
- confidence: 0.0-1.0 confidence score

Output as JSON: {"entities": [...]}
Be thorough - missing PII could lead to privacy violations."""

_SEGMENT_SYSTEM_PROMPT = """You are a text segmentation expert. Identify speaker turn boundaries in text.

Given raw text without speaker labels, identify:
1. Where each speaker turn STARTS and ENDS (character positions)
2. WHO is speaking - use CONSERVATIVE labels

Speaker labels (prefer uncertainty over false confidence):
- "speaker_a": HIGH confidence this is the first/primary speaker
- "speaker_b": HIGH confidence this is the second speaker
- "lean_a": Probably speaker A but not certain
- "lean_b": Probably speaker B but not certain
- "unsure": Cannot determine speaker with any confidence

Rules:
- NEVER LOSE DATA: Every character from position 0 to the end must be in exactly one segment
- Segments must be contiguous: end_char of one = start_char of next
- When uncertain, use "lean_*" or "unsure" - don't guess
- Be precise with character positions

Output format:
{"segments": [{"start_char": 0, "end_char": 52, "speaker": "speaker_a", "confidence": 0.95}]}

CRITICAL:
- First segment MUST start at 0
- Last segment MUST end at total character count
- NO gaps between segments"""


@dataclass(frozen=True, slots=True)
class LLMInvocationMeta:
    """Metadata from LLM invocation for evidence.

    Captured from Operation.execution after invoke().
    """

    model_name: str
    duration_ms: int | None = None
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for evidence storage."""
        d: dict[str, Any] = {"model_name": self.model_name, "status": self.status}
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        return d


# =============================================================================
# LLM Extraction Functions
# =============================================================================


async def extract_pii_entities(
    text: str,
    *,
    model: iModel | None = None,
    config_data: dict[str, Any] | None = None,
    entity_hints: dict[str, list[str]] | None = None,
    context: str | None = None,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[PIIEntity], LLMInvocationMeta | None, str | None]:
    """Extract PII entities from text using LLM.

    Args:
        text: Text to scan for PII
        model: iModel instance (from vendor service)
        config_data: Config dict if model not provided (creates model internally)
        entity_hints: Known entities to look for
        context: Context hint (e.g., "interview transcript")
        max_retries: Number of retry attempts

    Returns:
        (entities, meta, error) - error is None on success
    """
    from .._llm import iModel as iModelClass

    # Create model if not provided
    if model is None:
        config = config_data or DEFAULT_PII_CONFIG
        model = iModelClass(
            model=config.get("model", "google/gemini-2.5-flash"),
            provider=config.get("provider", "openrouter"),
        )

    last_error = ""

    for attempt in range(max_retries):
        try:
            entities, meta = await _extract_pii(text, model, entity_hints, context)
            return entities, meta, None
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY_MS * (attempt + 1) / 1000)

    return [], None, f"Failed after {max_retries} attempts: {last_error}"


async def extract_segment_boundaries(
    raw_text: str,
    *,
    model: iModel | None = None,
    config_data: dict[str, Any] | None = None,
    speaker_a_hint: str | None = None,
    speaker_b_hint: str | None = None,
    context: str | None = None,
    max_retries: int = MAX_RETRIES,
) -> tuple[list[SegmentBoundary], LLMInvocationMeta | None, str | None]:
    """Extract speaker segment boundaries from text using LLM.

    Args:
        raw_text: Unformatted text to segment
        model: iModel instance (from vendor service)
        config_data: Config dict if model not provided
        speaker_a_hint: Hint about speaker A identity
        speaker_b_hint: Hint about speaker B identity
        context: Context hint
        max_retries: Number of retry attempts

    Returns:
        (boundaries, meta, error) - error is None on success.
        On total failure, returns fallback single-segment boundary.
    """
    from .._llm import iModel as iModelClass

    # Create model if not provided
    if model is None:
        config = config_data or DEFAULT_PII_CONFIG
        model = iModelClass(
            model=config.get("model", "google/gemini-2.5-flash"),
            provider=config.get("provider", "openrouter"),
        )

    last_error = ""

    for attempt in range(max_retries):
        try:
            boundaries, meta = await _extract_boundaries(
                raw_text, model, speaker_a_hint, speaker_b_hint, context
            )
            return boundaries, meta, None
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY_MS * (attempt + 1) / 1000)

    # Return fallback on total failure
    fallback = [
        SegmentBoundary(
            start_char=0,
            end_char=len(raw_text),
            speaker=SpeakerRole.UNSURE,
            confidence=0.0,
        )
    ]
    return (
        fallback,
        None,
        f"Failed after {max_retries} attempts (using fallback): {last_error}",
    )


async def _extract_pii(
    text: str,
    model: iModel,
    entity_hints: dict[str, list[str]] | None,
    context: str | None,
) -> tuple[list[PIIEntity], LLMInvocationMeta]:
    """Extract PII entities using LLM."""
    # Build context hints
    hints = ""
    if entity_hints:
        for category, values in entity_hints.items():
            hints += f"\nKnown {category}: {', '.join(values)}"
    if context:
        hints += f"\nContext: {context}"

    user_prompt = f"""Extract ALL PII from this text:{hints}

<text>
{text}
</text>

Return JSON: {{"entities": [{{"category": "...", "original_text": "...", "confidence": 0.9}}]}}"""

    import time

    start_time = time.time()

    async with model:
        response = await model.invoke(
            messages=[
                {"role": "system", "content": _PII_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

    duration_ms = int((time.time() - start_time) * 1000)
    meta = LLMInvocationMeta(
        model_name=model.model if hasattr(model, "model") else "unknown",
        duration_ms=duration_ms,
        status="completed",
    )

    # Parse response
    items = _parse_json_response(response, "entities")
    return _parse_pii_entities(items), meta


async def _extract_boundaries(
    raw_text: str,
    model: iModel,
    speaker_a_hint: str | None,
    speaker_b_hint: str | None,
    context: str | None,
) -> tuple[list[SegmentBoundary], LLMInvocationMeta]:
    """Extract segment boundaries using LLM."""
    # Build context hints
    hints = ""
    if speaker_a_hint:
        hints += f"\nSpeaker A is likely: {speaker_a_hint}"
    if speaker_b_hint:
        hints += f"\nSpeaker B is likely: {speaker_b_hint}"
    if context:
        hints += f"\nContext: {context}"

    user_prompt = f"""Segment this text into speaker turns:{hints}

<text>
{raw_text}
</text>

Total characters: {len(raw_text)}

Return JSON with segments array."""

    import time

    start_time = time.time()

    async with model:
        response = await model.invoke(
            messages=[
                {"role": "system", "content": _SEGMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

    duration_ms = int((time.time() - start_time) * 1000)
    meta = LLMInvocationMeta(
        model_name=model.model if hasattr(model, "model") else "unknown",
        duration_ms=duration_ms,
        status="completed",
    )

    # Parse response
    items = _parse_json_response(response, "segments")
    boundaries = _parse_boundaries(items)
    return validate_boundaries(boundaries, len(raw_text)), meta


def _parse_json_response(response: Any, key: str) -> list[dict]:
    """Parse LLM JSON response to extract list of items."""
    if response is None:
        return []

    # Handle response object
    if hasattr(response, "response") and hasattr(response.response, "data"):
        data = response.response.data
        if isinstance(data, dict):
            if key in data:
                return data[key]
            if "choices" in data:
                content = data["choices"][0].get("message", {}).get("content", "{}")
                return json.loads(content).get(key, [])

    # Direct dict response
    if isinstance(response, dict):
        if key in response:
            return response[key]
        if "choices" in response:
            content = response["choices"][0].get("message", {}).get("content", "{}")
            return json.loads(content).get(key, [])

    # String response - parse as JSON
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
            if isinstance(parsed, dict) and key in parsed:
                return parsed[key]
        except json.JSONDecodeError:
            return []

    return []


def _parse_pii_entities(items: list[dict]) -> list[PIIEntity]:
    """Parse raw items into PIIEntity objects."""
    entities = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            category = PIICategory(item.get("category", "person"))
            entities.append(
                PIIEntity(
                    category=category,
                    original_text=item.get("original_text", ""),
                    placeholder="",  # Assigned by caller
                    confidence=float(item.get("confidence", 1.0)),
                )
            )
        except (ValueError, KeyError):
            continue
    return entities


def _parse_boundaries(items: list[dict]) -> list[SegmentBoundary]:
    """Parse raw items into SegmentBoundary objects."""
    speaker_map = {
        "speaker_a": SpeakerRole.SPEAKER_A,
        "speaker_b": SpeakerRole.SPEAKER_B,
        "lean_a": SpeakerRole.LEAN_A,
        "lean_b": SpeakerRole.LEAN_B,
        "unsure": SpeakerRole.UNSURE,
    }

    boundaries = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            speaker_str = item.get("speaker", "unsure").lower()
            boundaries.append(
                SegmentBoundary(
                    start_char=int(item.get("start_char", 0)),
                    end_char=int(item.get("end_char", 0)),
                    speaker=speaker_map.get(speaker_str, SpeakerRole.UNSURE),
                    confidence=float(item.get("confidence", 1.0)),
                )
            )
        except (ValueError, KeyError):
            continue
    return boundaries


# =============================================================================
# Transformation Utilities
# =============================================================================


def build_placeholder_map(
    entities: list[PIIEntity],
) -> dict[str, tuple[str, PIIEntity]]:
    """Build mapping of original text to placeholder.

    Returns:
        Dict mapping lowercase original text to (placeholder, entity) tuple.
        The entity's placeholder field is also updated in-place.
    """
    placeholder_templates = {
        PIICategory.PERSON: "[PERSON_{n}]",
        PIICategory.COMPANY: "[COMPANY_{n}]",
        PIICategory.SCHOOL: "[SCHOOL_{n}]",
        PIICategory.LOCATION: "[LOCATION]",
        PIICategory.DATE: "[DATE]",
        PIICategory.EMAIL: "[EMAIL]",
        PIICategory.PHONE: "[PHONE]",
        PIICategory.ADDRESS: "[ADDRESS]",
    }

    entity_map: dict[str, tuple[str, PIIEntity]] = {}
    counters: dict[PIICategory, int] = {}
    seen_text: dict[str, str] = {}

    for entity in entities:
        key = entity.original_text.lower().strip()

        if key in seen_text:
            entity.placeholder = seen_text[key]
            entity_map[key] = (seen_text[key], entity)
            continue

        template = placeholder_templates.get(entity.category, "[REDACTED]")

        if "{n}" in template:
            counters[entity.category] = counters.get(entity.category, 0) + 1
            placeholder = template.format(n=counters[entity.category])
        else:
            placeholder = template

        entity.placeholder = placeholder
        seen_text[key] = placeholder
        entity_map[key] = (placeholder, entity)

    return entity_map


def apply_redactions_to_text(
    text: str,
    entity_map: dict[str, tuple[str, PIIEntity]],
) -> str:
    """Apply redactions to simple text."""
    redacted = text
    for original_lower, (placeholder, _) in entity_map.items():
        pattern = re.compile(re.escape(original_lower), re.IGNORECASE)
        redacted = pattern.sub(placeholder, redacted)
    return redacted


def apply_redactions_to_chunks(
    chunks: list[TextChunk | dict],
    entity_map: dict[str, tuple[str, PIIEntity]],
) -> list[RedactedChunk]:
    """Apply redactions to text chunks."""
    redacted_chunks = []

    for chunk in chunks:
        speaker = chunk.speaker if hasattr(chunk, "speaker") else chunk.get("speaker", "")
        text = chunk.text if hasattr(chunk, "text") else chunk.get("text", "")
        start_time = chunk.start_time if hasattr(chunk, "start_time") else chunk.get("start_time")
        end_time = chunk.end_time if hasattr(chunk, "end_time") else chunk.get("end_time")
        chunk_index = (
            chunk.chunk_index if hasattr(chunk, "chunk_index") else chunk.get("chunk_index", 0)
        )

        redacted_text = text
        redacted_speaker = speaker
        entities_redacted = 0

        # Apply entity redactions
        for original_lower, (placeholder, _) in entity_map.items():
            pattern = re.compile(re.escape(original_lower), re.IGNORECASE)
            new_text, count = pattern.subn(placeholder, redacted_text)
            if count > 0:
                redacted_text = new_text
                entities_redacted += count

            if original_lower in redacted_speaker.lower():
                redacted_speaker = pattern.sub(placeholder, redacted_speaker)

        redacted_chunks.append(
            RedactedChunk(
                speaker=redacted_speaker,
                text=redacted_text,
                start_time=start_time,
                end_time=end_time,
                chunk_index=chunk_index,
                entities_redacted=entities_redacted,
                # Store originals for transform-time QA only
                original_speaker=speaker,
                original_text=text,
            )
        )

    return redacted_chunks


def format_chunks_for_extraction(chunks: list[TextChunk | dict]) -> str:
    """Format text chunks for PII extraction."""
    lines = []
    for i, chunk in enumerate(chunks):
        speaker = chunk.speaker if hasattr(chunk, "speaker") else chunk.get("speaker", "")
        text = chunk.text if hasattr(chunk, "text") else chunk.get("text", "")
        lines.append(f"[{i}] {speaker}: {text}")
    return "\n".join(lines)


# =============================================================================
# Boundary Validation
# =============================================================================


def validate_boundaries(
    boundaries: list[SegmentBoundary],
    text_length: int,
) -> list[SegmentBoundary]:
    """Validate and fix boundary issues - NEVER LOSE DATA."""
    if not boundaries:
        return [
            SegmentBoundary(
                start_char=0,
                end_char=text_length,
                speaker=SpeakerRole.UNSURE,
                confidence=0.0,
            )
        ]

    # Sort by start position
    sorted_bounds = sorted(boundaries, key=lambda b: b.start_char)
    fixed: list[SegmentBoundary] = []

    for b in sorted_bounds:
        start = max(0, min(b.start_char, text_length))
        end = max(0, min(b.end_char, text_length))

        if end <= start:
            continue

        # Fix gap with previous segment
        if fixed:
            if fixed[-1].end_char < start:
                fixed.append(
                    SegmentBoundary(
                        start_char=fixed[-1].end_char,
                        end_char=start,
                        speaker=SpeakerRole.UNSURE,
                        confidence=0.0,
                    )
                )
            elif fixed[-1].end_char > start:
                start = fixed[-1].end_char

        if end > start:
            fixed.append(
                SegmentBoundary(
                    start_char=start,
                    end_char=end,
                    speaker=b.speaker,
                    confidence=b.confidence,
                )
            )

    # Ensure first segment starts at 0
    if fixed and fixed[0].start_char > 0:
        fixed.insert(
            0,
            SegmentBoundary(
                start_char=0,
                end_char=fixed[0].start_char,
                speaker=SpeakerRole.UNSURE,
                confidence=0.0,
            ),
        )

    # Ensure last segment ends at text_length
    if fixed and fixed[-1].end_char < text_length:
        fixed.append(
            SegmentBoundary(
                start_char=fixed[-1].end_char,
                end_char=text_length,
                speaker=SpeakerRole.UNSURE,
                confidence=0.0,
            )
        )

    if not fixed:
        return [
            SegmentBoundary(
                start_char=0,
                end_char=text_length,
                speaker=SpeakerRole.UNSURE,
                confidence=0.0,
            )
        ]

    return fixed


def slice_text_at_boundaries(
    raw_text: str,
    boundaries: list[SegmentBoundary],
) -> list[TextChunk]:
    """Slice raw text at boundaries to create TextChunk segments."""
    segments = []
    for i, b in enumerate(boundaries):
        text_slice = raw_text[b.start_char : b.end_char]
        segments.append(
            TextChunk(
                speaker=b.speaker.value,
                text=text_slice,
                chunk_index=i,
            )
        )
    return segments
