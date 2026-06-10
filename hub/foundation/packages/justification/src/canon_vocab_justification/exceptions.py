"""Justification domain exceptions.

These exceptions are raised by justification features when requirements are violated.
All inherit from AuthorizationViolation (the closest domain base exception for
justification-related violations involving business decisions and documentation).
"""

from __future__ import annotations

from typing import Any

from canon.enforcement.exceptions import AuthorizationViolation

__all__ = [
    "EvidenceRequirementNotMetError",
    "JustificationIncompleteError",
    "JustificationNotValidError",
]


class JustificationNotValidError(AuthorizationViolation):
    """Justification does not meet validation requirements.

    Raised when: classify_justification determines a justification is too weak
    (cosmetic or low-confidence business convenience) without escalation.

    Regulatory basis:
    - SOX Section 404 (Controls over exceptions and waivers)
    - COSO Framework (Exception handling)
    - Audit standards (Documentation of control overrides)

    Phrase: justification_must_be_valid
    """

    default_regulation = "SOX Section 404"
    default_message = "Justification does not meet validation requirements"

    __slots__ = ("classification", "confidence", "requires_escalation")

    def __init__(
        self,
        classification: str,
        confidence: float,
        requires_escalation: bool,
        **kwargs: Any,
    ) -> None:
        """Initialize justification not valid error.

        Args:
            classification: The determined classification of the justification.
            confidence: Confidence score (0.0-1.0) in the classification.
            requires_escalation: Whether escalation was required but not obtained.
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.classification = classification
        self.confidence = confidence
        self.requires_escalation = requires_escalation
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "classification": classification,
            "confidence": confidence,
            "requires_escalation": requires_escalation,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Justification classified as '{classification}' with confidence {confidence:.2f} "
            f"{'requires escalation' if requires_escalation else 'is not sufficient'}",
            context=merged_context,
            **kwargs,
        )


class JustificationIncompleteError(AuthorizationViolation):
    """Business justification is missing required elements.

    Raised when: validate_business_justification finds the justification document
    is missing one or more required elements (reason, impact, plan, owner).

    Regulatory basis:
    - SOX Section 404 (Documentation of business decisions)
    - COSO Framework (Risk assessment and response)
    - IIA Standards (Audit trail requirements)

    Phrase: justification_must_be_complete
    """

    default_regulation = "SOX Section 404"
    default_message = "Business justification is incomplete"

    __slots__ = ("missing_elements",)

    def __init__(
        self,
        missing_elements: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize justification incomplete error.

        Args:
            missing_elements: Tuple of missing required element names.
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.missing_elements = missing_elements
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "missing_elements": list(missing_elements),
            "missing_count": len(missing_elements),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Business justification missing required elements: {', '.join(missing_elements)}",
            context=merged_context,
            **kwargs,
        )


class EvidenceRequirementNotMetError(AuthorizationViolation):
    """Required evidence for reason code or waiver not provided.

    Raised when: Evidence requirements mapped by map_reason_code_to_evidence_requirements
    or map_waiver_reason_to_evidence are not satisfied.

    Regulatory basis:
    - SOX Section 404 (Documentation of internal controls)
    - Employment law (Termination documentation requirements)
    - EEOC Guidelines (Evidence for adverse employment actions)
    - Transfer pricing regulations (Documentation requirements)

    Phrase: evidence_requirements_must_be_met
    """

    default_regulation = "SOX Section 404"
    default_message = "Evidence requirements not met"

    __slots__ = ("context_type", "missing_evidence", "reason_code")

    def __init__(
        self,
        reason_code: str,
        context_type: str,
        missing_evidence: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize evidence requirement not met error.

        Args:
            reason_code: The reason code whose evidence requirements were not met.
            context_type: The context (e.g., "termination", "waiver", "transfer").
            missing_evidence: Tuple of missing evidence type identifiers.
            **kwargs: Additional arguments passed to parent (including optional context to merge).
        """
        self.reason_code = reason_code
        self.context_type = context_type
        self.missing_evidence = missing_evidence
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "reason_code": reason_code,
            "context_type": context_type,
            "missing_evidence": list(missing_evidence),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Evidence requirements for '{reason_code}' ({context_type}) not met: "
            f"missing {', '.join(missing_evidence)}",
            context=merged_context,
            **kwargs,
        )
