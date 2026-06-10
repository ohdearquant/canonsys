"""Data protection domain exceptions.

These exceptions are raised by data protection phrases when invariants are violated.
All inherit from DataProtectionViolation (the domain's base exception).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import DataProtectionViolation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from .types import AudienceScope, ConfidentialityLevel, ProcessorTermsStatus

__all__ = [
    "DataMinimizationError",
    "LimitedAudienceRequiredError",
    "ProcessorTermsNotVerifiedError",
    "PublicationRestrictedError",
    "PurposeLimitationError",
    "RetentionComplianceRequiredError",
]


class ProcessorTermsNotVerifiedError(DataProtectionViolation):
    """Processor terms are not verified.

    Raised when: require_processor_terms_verified finds no verified
    processor agreement for a data processor.

    Regulatory basis:
    - GDPR Art. 28: Processor requirements
    - CCPA Section 1798.140(w): Service provider contracts
    - HIPAA 164.308(b): Business associate contracts

    Phrase: require_processor_terms_verified
    """

    default_regulation = "GDPR Art. 28"
    default_message = "Processor terms must be verified before data sharing"

    __slots__ = ("processor_id", "status")

    def __init__(
        self,
        processor_id: UUID,
        status: ProcessorTermsStatus,
        **kwargs: Any,
    ) -> None:
        """Initialize processor terms not verified error.

        Args:
            processor_id: UUID of the processor without verified terms.
            status: Current status of the processor terms.
            **kwargs: Additional arguments passed to parent.
        """
        self.processor_id = processor_id
        self.status = status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "processor_id": str(processor_id),
            "status": status.value,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Processor {processor_id} terms status: {status.value}",
            context=merged_context,
            **kwargs,
        )


class DataMinimizationError(DataProtectionViolation):
    """Requested fields exceed what is allowed for the workflow.

    Raised when: verify_data_minimization finds fields being requested
    that are not in the workflow's allowlist.

    Regulatory basis:
    - GDPR Art. 5(1)(c): Data minimization
    - HIPAA 164.502(b): Minimum necessary
    - CCPA Section 1798.100(c): Collection limitation

    Phrase: verify_data_minimization
    """

    default_regulation = "GDPR Art. 5(1)(c)"
    default_message = "Requested fields exceed allowlist"

    __slots__ = ("excess_fields", "workflow_id")

    def __init__(
        self,
        workflow_id: UUID,
        excess_fields: tuple[str, ...],
        **kwargs: Any,
    ) -> None:
        """Initialize data minimization error.

        Args:
            workflow_id: UUID of the workflow requesting excess fields.
            excess_fields: Fields requested that are not allowed.
            **kwargs: Additional arguments passed to parent.
        """
        self.workflow_id = workflow_id
        self.excess_fields = excess_fields
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "workflow_id": str(workflow_id),
            "excess_fields": list(excess_fields),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Workflow {workflow_id} requested excess fields: {', '.join(excess_fields)}",
            context=merged_context,
            **kwargs,
        )


class PurposeLimitationError(DataProtectionViolation):
    """Requested use does not match declared purpose.

    Raised when: verify_purpose_limitation finds a use being
    requested that does not match the declared purpose.

    Regulatory basis:
    - GDPR Art. 5(1)(b): Purpose limitation
    - CCPA Section 1798.100(b): Collection limitation
    - HIPAA 164.502(a): Minimum necessary

    Phrase: verify_purpose_limitation
    """

    default_regulation = "GDPR Art. 5(1)(b)"
    default_message = "Requested use does not match declared purpose"

    __slots__ = ("declared_purpose", "requested_use", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        declared_purpose: str,
        requested_use: str,
        **kwargs: Any,
    ) -> None:
        """Initialize purpose limitation error.

        Args:
            resource_id: UUID of the resource being accessed.
            declared_purpose: The purpose for which data was collected.
            requested_use: The use being requested.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.declared_purpose = declared_purpose
        self.requested_use = requested_use
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "declared_purpose": declared_purpose,
            "requested_use": requested_use,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Use '{requested_use}' not permitted for purpose '{declared_purpose}'",
            context=merged_context,
            **kwargs,
        )


class LimitedAudienceRequiredError(DataProtectionViolation):
    """Confidential content requires a limited audience.

    Raised when: require_limited_audience finds confidential or restricted
    content being shared with an unlimited audience.

    Regulatory basis:
    - GDPR Art. 5(1)(f): Confidentiality
    - HIPAA 164.502: Minimum necessary
    - SOC 2 CC6.1: Access restrictions

    Phrase: require_limited_audience
    """

    default_regulation = "GDPR Art. 5(1)(f)"
    default_message = "Confidential content requires limited audience"

    __slots__ = ("confidentiality", "resource_id", "target_audience")

    def __init__(
        self,
        resource_id: UUID,
        confidentiality: ConfidentialityLevel,
        target_audience: AudienceScope,
        **kwargs: Any,
    ) -> None:
        """Initialize limited audience required error.

        Args:
            resource_id: UUID of the resource.
            confidentiality: Confidentiality level of the resource.
            target_audience: Attempted target audience scope.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.confidentiality = confidentiality
        self.target_audience = target_audience
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "confidentiality": confidentiality.value,
            "target_audience": target_audience.value,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"{confidentiality.value} content cannot target {target_audience.value} audience",
            context=merged_context,
            **kwargs,
        )


class RetentionComplianceRequiredError(DataProtectionViolation):
    """Data is being retained beyond its scheduled retention period.

    Raised when: require_retention_compliance finds data that has exceeded
    its retention schedule (unless under legal hold).

    Regulatory basis:
    - GDPR Art. 5(1)(e): Storage limitation
    - CCPA Section 1798.105: Right to deletion
    - SOX Section 802: Document retention

    Phrase: require_retention_compliance
    """

    default_regulation = "GDPR Art. 5(1)(e)"
    default_message = "Data retention period exceeded"

    __slots__ = ("days_beyond", "resource_id", "retention_end")

    def __init__(
        self,
        resource_id: UUID,
        retention_end: datetime,
        days_beyond: int,
        **kwargs: Any,
    ) -> None:
        """Initialize retention compliance required error.

        Args:
            resource_id: UUID of the resource.
            retention_end: When the retention period ended.
            days_beyond: Number of days beyond the scheduled end.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.retention_end = retention_end
        self.days_beyond = days_beyond
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "retention_end": retention_end.isoformat(),
            "days_beyond": days_beyond,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Data retained {days_beyond} days beyond schedule (ended {retention_end.isoformat()})",
            context=merged_context,
            **kwargs,
        )


class PublicationRestrictedError(DataProtectionViolation):
    """Content has publication restrictions that prevent external publication.

    Raised when: require_internal_publication finds content with active
    publication restrictions (embargo, trade secret, export control, etc.).

    Regulatory basis:
    - SEC Regulation FD: Fair disclosure
    - ITAR 22 CFR 120-130: Export controls
    - Trade secret law (DTSA)

    Phrase: require_internal_publication
    """

    default_regulation = "SEC Regulation FD"
    default_message = "Publication is restricted"

    __slots__ = ("embargo_until", "resource_id", "restriction", "restriction_reason")

    def __init__(
        self,
        resource_id: UUID,
        restriction: str,
        restriction_reason: str | None = None,
        embargo_until: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize publication restricted error.

        Args:
            resource_id: UUID of the resource.
            restriction: Type of restriction (e.g., "embargo", "trade_secret").
            restriction_reason: Human-readable reason for restriction.
            embargo_until: ISO8601 timestamp of embargo end, if applicable.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.restriction = restriction
        self.restriction_reason = restriction_reason
        self.embargo_until = embargo_until
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "restriction": restriction,
        }
        if restriction_reason:
            base_context["restriction_reason"] = restriction_reason
        if embargo_until:
            base_context["embargo_until"] = embargo_until
        merged_context = {**base_context, **extra_context}
        msg = f"Publication restricted: {restriction}"
        if embargo_until:
            msg += f" (until {embargo_until})"
        super().__init__(
            msg,
            context=merged_context,
            **kwargs,
        )
