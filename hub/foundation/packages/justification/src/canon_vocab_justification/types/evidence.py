"""Evidence requirement types for justification domain."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = (
    "EvidenceRequirement",
    "ReasonEvidenceMapping",
    "WaiverEvidenceMapping",
)


@dataclass(frozen=True, slots=True)
class EvidenceRequirement:
    """A single evidence requirement for a reason code.

    Attributes:
        evidence_type: Type identifier for the required evidence.
        required: Whether this evidence is mandatory (True) or optional (False).
        description: Human-readable description of what evidence is needed.
    """

    evidence_type: str
    required: bool
    description: str


@dataclass(frozen=True, slots=True)
class ReasonEvidenceMapping:
    """Mapping from reason code to required evidence.

    Attributes:
        reason_code: The reason code being mapped.
        context: Context in which this reason code is used (e.g., termination, transfer).
        requirements: Tuple of evidence requirements for this reason code.
        min_required: Minimum number of optional evidence items required.
    """

    reason_code: str
    context: str
    requirements: tuple[EvidenceRequirement, ...]
    min_required: int


@dataclass(frozen=True, slots=True)
class WaiverEvidenceMapping:
    """Mapping from waiver reason to required evidence.

    Attributes:
        waiver_reason: The normalized waiver reason.
        required_evidence: Tuple of mandatory evidence types.
        optional_evidence: Tuple of optional supporting evidence types.
        escalation_required: Whether this waiver requires escalation.
    """

    waiver_reason: str
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    escalation_required: bool
