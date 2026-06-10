"""Controls domain exceptions.

These exceptions are raised when control requirements are not satisfied.
All inherit from ControlViolation (the domain's base exception).

Regulatory Context:
    - SOX Section 404 (Internal controls assessment)
    - SOC 2 CC4.1 (Control monitoring)
    - ISO 27001 A.18.2.1 (Compliance review)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import InvariantViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "ControlCoverageInsufficientError",
    "ControlEquivalenceInsufficientError",
    "ControlViolation",
    "RequiredControlsMissingError",
    "SanitizationCoverageInsufficientError",
]


class ControlViolation(InvariantViolation):
    """Control-related invariant violations.

    Covers violations of control requirements under:
    - SOX Section 404 (Internal controls assessment)
    - SOC 2 CC4.1 (Control monitoring and evaluation)
    - ISO 27001 A.18.2.1 (Compliance review)

    Invariant phrases:
    - control_coverage_must_be_sufficient
    - control_equivalence_must_be_sufficient
    - required_controls_must_be_present
    - sanitization_must_cover_required_types
    """

    default_regulation = "SOX Section 404"
    default_message = "Control requirement not satisfied"


class ControlCoverageInsufficientError(ControlViolation):
    """Control coverage is below the required threshold.

    Raised when: assess_control_coverage determines that coverage
    percentage is below the minimum acceptable threshold.

    Regulatory basis:
    - SOX Section 404: Requires adequate internal control coverage
    - SOC 2 CC4.1: Control monitoring requirements
    - ISO 27001 A.18.2.1: Independent review of security

    Phrase: control_coverage_must_be_sufficient
    """

    default_regulation = "SOX Section 404"
    default_message = "Control coverage insufficient"

    __slots__ = ("coverage_pct", "entity_id", "required_pct", "vulnerability_id")

    def __init__(
        self,
        entity_id: UUID,
        vulnerability_id: str,
        coverage_pct: int,
        required_pct: int = 80,
        **kwargs: Any,
    ) -> None:
        """Initialize control coverage insufficient error.

        Args:
            entity_id: UUID of the entity being assessed.
            vulnerability_id: CVE or internal vulnerability identifier.
            coverage_pct: Actual coverage percentage achieved.
            required_pct: Required coverage percentage threshold.
            **kwargs: Additional arguments passed to parent.
        """
        self.entity_id = entity_id
        self.vulnerability_id = vulnerability_id
        self.coverage_pct = coverage_pct
        self.required_pct = required_pct
        super().__init__(
            f"Control coverage {coverage_pct}% is below required {required_pct}% "
            f"for vulnerability {vulnerability_id}",
            context={
                "entity_id": str(entity_id),
                "vulnerability_id": vulnerability_id,
                "coverage_pct": coverage_pct,
                "required_pct": required_pct,
            },
            **kwargs,
        )


class ControlEquivalenceInsufficientError(ControlViolation):
    """Compensating control is not equivalent enough.

    Raised when: derive_control_equivalence_score determines that
    the compensating control does not provide adequate equivalence
    to the original control.

    Regulatory basis:
    - SOX Section 404: Compensating controls must provide equivalent assurance
    - SOC 2 CC4.1: Monitoring must ensure control objectives are met
    - ISO 27001 A.18.2.1: Alternative controls must be justified

    Phrase: control_equivalence_must_be_sufficient
    """

    default_regulation = "SOX Section 404"
    default_message = "Compensating control equivalence insufficient"

    __slots__ = (
        "compensating_control_id",
        "original_control_id",
        "required_score",
        "score",
    )

    def __init__(
        self,
        original_control_id: UUID,
        compensating_control_id: UUID,
        score: float,
        required_score: float = 0.8,
        **kwargs: Any,
    ) -> None:
        """Initialize control equivalence insufficient error.

        Args:
            original_control_id: UUID of the control being replaced.
            compensating_control_id: UUID of the proposed substitute.
            score: Actual equivalence score achieved.
            required_score: Required equivalence score threshold.
            **kwargs: Additional arguments passed to parent.
        """
        self.original_control_id = original_control_id
        self.compensating_control_id = compensating_control_id
        self.score = score
        self.required_score = required_score
        super().__init__(
            f"Compensating control equivalence {score:.2f} is below required {required_score:.2f}",
            context={
                "original_control_id": str(original_control_id),
                "compensating_control_id": str(compensating_control_id),
                "score": score,
                "required_score": required_score,
            },
            **kwargs,
        )


class RequiredControlsMissingError(ControlViolation):
    """Required controls are not present for a tool.

    Raised when: verify_required_controls_for_tool determines that
    one or more required controls are missing.

    Regulatory basis:
    - SOX Section 404: Application controls must be documented
    - SOC 2 CC6.1: Logical access controls for applications
    - NYC LL144: AEDT tools require bias audits and notices

    Phrase: required_controls_must_be_present
    """

    default_regulation = "SOX Section 404"
    default_message = "Required controls missing"

    __slots__ = ("missing_controls", "tool_category", "tool_id")

    def __init__(
        self,
        tool_id: UUID,
        tool_category: str,
        missing_controls: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize required controls missing error.

        Args:
            tool_id: UUID of the tool being verified.
            tool_category: Category of the tool.
            missing_controls: Tuple of control names that are missing.
            **kwargs: Additional arguments passed to parent.
        """
        self.tool_id = tool_id
        self.tool_category = tool_category
        self.missing_controls = missing_controls
        super().__init__(
            f"Tool {tool_id} ({tool_category}) missing required controls: "
            f"{', '.join(missing_controls)}",
            context={
                "tool_id": str(tool_id),
                "tool_category": tool_category,
                "missing_controls": list(missing_controls),
            },
            **kwargs,
        )


class SanitizationCoverageInsufficientError(ControlViolation):
    """Sanitization profile does not cover all required data types.

    Raised when: verify_sanitization_profile determines that the
    profile is missing coverage for one or more required data types.

    Regulatory basis:
    - GDPR Article 32: Appropriate security measures for processing
    - SOC 2 CC6.7: Secure disposal of data and media
    - NIST SP 800-88: Media sanitization categorization

    Phrase: sanitization_must_cover_required_types
    """

    default_regulation = "GDPR Article 32"
    default_message = "Sanitization coverage insufficient"

    __slots__ = ("missing_coverage", "profile_id")

    def __init__(
        self,
        profile_id: UUID,
        missing_coverage: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize sanitization coverage insufficient error.

        Args:
            profile_id: UUID of the sanitization profile.
            missing_coverage: Tuple of data types not covered.
            **kwargs: Additional arguments passed to parent.
        """
        self.profile_id = profile_id
        self.missing_coverage = missing_coverage
        super().__init__(
            f"Sanitization profile {profile_id} missing coverage for: "
            f"{', '.join(missing_coverage)}",
            context={
                "profile_id": str(profile_id),
                "missing_coverage": list(missing_coverage),
            },
            **kwargs,
        )
