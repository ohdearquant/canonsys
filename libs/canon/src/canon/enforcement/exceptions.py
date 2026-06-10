"""Truth machine exception hierarchy for regulatory invariant violations.

This module defines the exception hierarchy for invariant violations in the
truth machine phrase system. These exceptions inherit from CanonError to unify
the exception hierarchy, allowing `catch(CanonError)` to catch all Canon
exceptions including regulatory violations.

Key characteristics of invariant violations:

1. **Semantic failures**: Represent violated regulatory requirements, not technical errors
2. **Deterministic**: Retrying with the same inputs will always fail (retryable=False)
3. **Auditable**: Carry structured context for compliance logging
4. **Traceable**: Each exception cites specific regulatory requirements

Hierarchy:
    CanonError (base)
    +-- InvariantViolation (regulatory, never retryable)
        +-- ConsentViolation: FCRA, GDPR consent requirements
        +-- TimingViolation: FCRA waiting periods, notice timing
        +-- AuthorizationViolation: SOX SoD, approval chains
        +-- EvidenceViolation: Evidence integrity, CEP requirements
        +-- DataProtectionViolation: GDPR data protection, encryption
        +-- AIGovernanceViolation: EU AI Act, NYC LL144 compliance

Usage:
    >>> from canon.enforcement.exceptions import (
    ...     InvariantViolation,
    ...     ConsentNotValidError,
    ...     WaitingPeriodNotElapsedError,
    ... )
    >>> from canon.exceptions import CanonError
    >>> try:
    ...     await consent_must_be_valid(subject_id, scope, ctx)
    ... except CanonError as e:  # Catches both operational and regulatory errors
    ...     if isinstance(e, InvariantViolation):
    ...         await save_evidence(e.to_dict(), "invariant_violation", ctx)
    ...     raise
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from canon.exceptions import CanonError

__all__: list[str] = [
    # Base
    "InvariantViolation",
    # Category Classes
    "ConsentViolation",
    "TimingViolation",
    "AuthorizationViolation",
    "EvidenceViolation",
    "DataProtectionViolation",
    "AIGovernanceViolation",
    # Consent Domain - import from canon.hub.packages.consent.exceptions
    # Timing Domain
    "WaitingPeriodNotElapsedError",
    "NoticePrecedenceError",
    "EvidenceStaleError",
    # Authorization Domain
    "SoDViolationError",
    "DualApprovalMissingError",
    "ClearanceInsufficientError",
    # Evidence Domain
    "EvidenceNotBoundError",
    "ChainBrokenError",
    "HashMismatchError",
    "CEPNotSealedError",
    # Data Protection Domain
    "PIIPublicExposureError",
    "PIIExposureError",
    "EncryptionMissingError",
    "UnencryptedTransmissionError",
    "ClassificationViolationError",
    "RetentionExceededError",
    # AI Governance Domain
    "HumanReviewMissingError",
    "BiasAssessmentMissingError",
    "ToolConfigMismatchError",
    "DisclosureMissingError",
]


# =============================================================================
# Base Class
# =============================================================================


class InvariantViolation(CanonError):
    """Base exception for all regulatory invariant violations.

    Invariant violations represent semantic failures where a regulatory
    requirement is not satisfied. Unlike operational errors (network timeout,
    database connection), invariant violations are deterministic - retrying
    with the same inputs will always fail.

    This exception inherits from CanonError to unify the exception hierarchy,
    allowing `catch(CanonError)` to catch all Canon exceptions including
    regulatory violations. However, invariant violations are NEVER retryable
    (retryable=False is enforced).

    Attributes:
        regulation: Citation string (e.g., "FCRA Section 1681b(b)(3)")
        message: Human-readable explanation of the violation
        context: Structured audit context (identifiers, timestamps, operands)
        retryable: Always False - regulatory violations cannot be retried

    Example:
        >>> try:
        ...     await consent_must_be_valid(subject_id, scope, ctx)
        ... except InvariantViolation as e:
        ...     await save_evidence(e.to_dict(), "invariant_violation", ctx)
        ...     raise

    Note:
        These exceptions should NOT be caught for retry logic. They indicate
        a fundamental requirement failure that requires either different inputs
        or human intervention to resolve.
    """

    # Subclasses override these defaults
    default_regulation: str = "CANON"
    default_message: str = "Regulatory invariant violation"
    default_retryable: bool = False  # Regulatory violations are NEVER retryable

    __slots__ = ("regulation",)

    def __init__(
        self,
        message: str | None = None,
        *,
        regulation: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """Initialize an invariant violation.

        Args:
            message: Human-readable description. Defaults to class default.
            regulation: Regulatory citation. Defaults to class default.
            context: Structured audit context for evidence logging.
            cause: Underlying exception that caused this violation.
        """
        self.regulation = regulation or self.default_regulation
        resolved_message = message or self.default_message

        # Format message with regulation prefix
        formatted_message = f"[{self.regulation}] {resolved_message}"

        # Call CanonError.__init__ with retryable=False enforced
        super().__init__(
            formatted_message,
            details=context,
            retryable=False,  # Regulatory violations are NEVER retryable
            cause=cause,
        )

    @property
    def context(self) -> dict[str, Any]:
        """Alias for details to maintain backward compatibility."""
        return self.details

    def to_dict(self) -> dict[str, Any]:
        """Serialize for audit logging and evidence emission.

        Returns:
            Dictionary with violation type, regulation, message, context,
            and retryable flag. Suitable for JSON serialization and storage
            in evidence tables.
        """
        return {
            "violation_type": self.__class__.__name__,
            "regulation": self.regulation,
            "message": self.message,
            "context": self.context,
            "retryable": self.retryable,
        }

    def to_evidence_context(self) -> dict[str, Any]:
        """Extract context suitable for evidence binding.

        Returns:
            Flattened dictionary with violation metadata merged into context.
            Suitable for inclusion in CEP evidence payloads.
        """
        return {
            "violation_type": self.__class__.__name__,
            "regulation_cited": self.regulation,
            **self.context,
        }


# =============================================================================
# Category Classes
# =============================================================================


class ConsentViolation(InvariantViolation):
    """Consent-related invariant violations.

    Covers violations of consent requirements under:
    - FCRA Section 1681b(b)(2): Consumer consent for background checks
    - GDPR Article 7: Conditions for valid consent
    - GDPR Article 6(1)(a): Lawful basis - consent
    - CCPA Section 1798.100: Consumer right to deletion

    Invariant phrases:
    - consent_must_be_valid
    - consent_must_not_be_expired
    - consent_must_not_be_withdrawn
    - consent_scope_must_match
    """

    default_regulation = "GDPR Article 7"
    default_message = "Consent requirement not satisfied"


class TimingViolation(InvariantViolation):
    """Timing-related invariant violations.

    Covers violations of temporal requirements under:
    - FCRA Section 1681b(b)(3): Reasonable waiting period before adverse action
    - FCRA Section 1681m: Pre-adverse action notice timing
    - GDPR Article 12(3): Response without undue delay
    - SOX Section 802: Document retention schedules

    Invariant phrases:
    - waiting_period_must_be_elapsed
    - notice_must_precede_action
    - deadline_must_not_be_exceeded
    - evidence_must_be_fresh
    """

    default_regulation = "FCRA Section 1681b(b)(3)"
    default_message = "Timing requirement not satisfied"


class AuthorizationViolation(InvariantViolation):
    """Authorization-related invariant violations.

    Covers violations of access control and approval requirements under:
    - SOX Section 404: Segregation of duties in internal controls
    - SOX Section 302: Corporate responsibility for financial reports
    - SOC 2 CC5.1: Control activities - segregation of duties
    - PCI DSS 6.4.2: Separation of duties in change management
    - COSO Framework: Control environment principles

    Invariant phrases:
    - preparer_must_not_be_approver (SoD)
    - dual_approval_must_be_present
    - clearance_must_be_sufficient
    - access_must_have_justification
    """

    default_regulation = "SOX Section 404"
    default_message = "Authorization requirement not satisfied"


class EvidenceViolation(InvariantViolation):
    """Evidence-related invariant violations.

    Covers violations of evidence integrity requirements under:
    - SOX Section 802: Document integrity and retention
    - FRCP Rule 37(e): ESI preservation duty
    - EU AI Act Article 12: Record-keeping for AI systems
    - ISO 27001 A.12.4.1: Event logging integrity

    Invariant phrases:
    - evidence_must_be_bound
    - chain_must_be_intact
    - hash_must_match
    - provenance_must_be_documented
    """

    default_regulation = "SOX Section 802"
    default_message = "Evidence requirement not satisfied"


class DataProtectionViolation(InvariantViolation):
    """Data protection-related invariant violations.

    Covers violations of data classification and protection under:
    - GDPR Article 5(1)(c): Data minimisation principle
    - GDPR Article 5(1)(f): Integrity and confidentiality
    - GDPR Article 32: Security of processing
    - PCI DSS 3.4, 4.1: Encryption requirements
    - HIPAA 164.312: Technical safeguards

    Invariant phrases:
    - pii_must_not_be_public
    - pci_must_be_confidential
    - phi_must_be_confidential
    - transmission_must_be_encrypted
    """

    default_regulation = "GDPR Article 32"
    default_message = "Data protection requirement not satisfied"


class AIGovernanceViolation(InvariantViolation):
    """AI governance-related invariant violations.

    Covers violations of AI/ML compliance requirements under:
    - EU AI Act Article 14: Human oversight for high-risk AI
    - EU AI Act Article 9: Risk management system
    - NYC LL144 Section 20-870: AEDT bias audit requirements
    - NYC LL144 Section 20-871: AEDT candidate notice
    - Colorado SB 21-169 / SB 205: Algorithmic discrimination

    Invariant phrases:
    - human_review_must_be_present
    - bias_assessment_must_be_documented
    - high_risk_must_have_oversight
    - same_tool_must_be_verified
    """

    default_regulation = "EU AI Act Article 14"
    default_message = "AI governance requirement not satisfied"


# =============================================================================
# Consent Domain Exceptions
# =============================================================================
# NOTE: Consent exceptions live in canon.hub.packages.consent.exceptions
# Import directly from there:
#   from canon.hub.packages.consent.exceptions import (
#       ConsentExpiredError, ConsentNotValidError, ConsentWithdrawnError
#   )

# =============================================================================
# Timing Domain Exceptions
# =============================================================================


class WaitingPeriodNotElapsedError(TimingViolation):
    """Required waiting period has not yet elapsed.

    Raised when: check_waiting_period_elapsed determines the dispute window
    or other required waiting period has not completed.

    Regulatory basis:
    - FCRA Section 1681b(b)(3): "reasonable period" (typically 5 business days)
    - State law variations (California, New York waiting periods)

    Phrase: waiting_period_must_be_elapsed
    """

    default_regulation = "FCRA Section 1681b(b)(3)"
    default_message = "Waiting period has not elapsed"

    __slots__ = ("elapsed_days", "notice_id", "required_days")

    def __init__(
        self,
        notice_id: UUID,
        required_days: int,
        elapsed_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize waiting period not elapsed error.

        Args:
            notice_id: UUID of the notice that started the waiting period.
            required_days: Number of days required to wait.
            elapsed_days: Number of days that have actually elapsed.
            **kwargs: Additional arguments passed to parent.
        """
        self.notice_id = notice_id
        self.required_days = required_days
        self.elapsed_days = elapsed_days
        remaining = required_days - elapsed_days
        super().__init__(
            f"Waiting period not elapsed: {elapsed_days}/{required_days} days "
            f"({remaining} days remaining)",
            context={
                "notice_id": str(notice_id),
                "required_days": required_days,
                "elapsed_days": elapsed_days,
                "remaining_days": remaining,
            },
            **kwargs,
        )


class NoticePrecedenceError(TimingViolation):
    """Required notice was not delivered before the action.

    Raised when: An action requiring prior notice is attempted without the
    notice having been sent/delivered.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action notice must precede adverse action
    - WARN Act: 60-day notice for mass layoffs
    - State WARN variations (California, New York)

    Phrase: notice_must_precede_action
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "Notice must precede action"

    __slots__ = ("action_type", "notice_required", "notice_status")

    def __init__(
        self,
        action_type: str,
        notice_required: str,
        notice_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize notice precedence error.

        Args:
            action_type: Type of action being attempted.
            notice_required: Type of notice required before action.
            notice_status: Current status of the required notice.
            **kwargs: Additional arguments passed to parent.
        """
        self.action_type = action_type
        self.notice_required = notice_required
        self.notice_status = notice_status
        super().__init__(
            f"Action '{action_type}' requires '{notice_required}' notice "
            f"(current status: {notice_status})",
            context={
                "action_type": action_type,
                "notice_required": notice_required,
                "notice_status": notice_status,
            },
            **kwargs,
        )


class EvidenceStaleError(TimingViolation):
    """Evidence is older than the allowed freshness window.

    Raised when: Evidence used for a decision exceeds the maximum age
    allowed by policy or regulation.

    Regulatory basis:
    - SOC 2 CC4.1: Information quality and currency
    - FCRA Section 1681c: 7-year limit on certain information
    - Organization-specific freshness policies

    Phrase: evidence_must_be_fresh
    """

    default_regulation = "SOC 2 CC4.1"
    default_message = "Evidence exceeds freshness requirements"

    __slots__ = ("actual_age_hours", "evidence_id", "max_age_hours")

    def __init__(
        self,
        evidence_id: UUID,
        max_age_hours: int,
        actual_age_hours: int,
        **kwargs: Any,
    ) -> None:
        """Initialize evidence stale error.

        Args:
            evidence_id: UUID of the stale evidence.
            max_age_hours: Maximum allowed age in hours.
            actual_age_hours: Actual age of the evidence in hours.
            **kwargs: Additional arguments passed to parent.
        """
        self.evidence_id = evidence_id
        self.max_age_hours = max_age_hours
        self.actual_age_hours = actual_age_hours
        super().__init__(
            f"Evidence {evidence_id} is {actual_age_hours}h old (max allowed: {max_age_hours}h)",
            context={
                "evidence_id": str(evidence_id),
                "max_age_hours": max_age_hours,
                "actual_age_hours": actual_age_hours,
            },
            **kwargs,
        )


# =============================================================================
# Authorization Domain Exceptions
# =============================================================================


class SoDViolationError(AuthorizationViolation):
    """Segregation of Duties violation - same person in conflicting roles.

    Raised when: require_distinct_identities finds the same identity in
    two roles that must be performed by different people.

    Regulatory basis:
    - SOX Section 404: Segregation of duties in internal controls
    - COSO Framework: Control activities principle
    - SOC 2 CC5.1: Control activities - segregation of duties
    - PCI DSS 6.4.2: Separation between development and production

    Phrase: preparer_must_not_be_approver
    """

    default_regulation = "SOX Section 404"
    default_message = "Segregation of Duties violation"

    __slots__ = ("identity_id", "role_a", "role_b")

    def __init__(
        self,
        identity_id: UUID,
        role_a: str,
        role_b: str,
        **kwargs: Any,
    ) -> None:
        """Initialize SoD violation error.

        Args:
            identity_id: UUID of the person in both conflicting roles.
            role_a: First conflicting role (e.g., "preparer").
            role_b: Second conflicting role (e.g., "approver").
            **kwargs: Additional arguments passed to parent.
        """
        self.identity_id = identity_id
        self.role_a = role_a
        self.role_b = role_b
        super().__init__(
            f"SoD violation: '{role_a}' and '{role_b}' must be different people "
            f"(both are {identity_id})",
            context={
                "identity_id": str(identity_id),
                "role_a": role_a,
                "role_b": role_b,
            },
            **kwargs,
        )


class DualApprovalMissingError(AuthorizationViolation):
    """Required dual approval not present.

    Raised when: require_dual_approval finds fewer approvals than required
    for a high-risk operation.

    Regulatory basis:
    - SOX Section 302: Corporate responsibility (dual sign-off)
    - SOX Section 404: Internal controls requiring multiple approvers
    - PCI DSS v4.0 Req. 8.6: Multi-person authorization

    Phrase: dual_approval_must_be_present
    """

    default_regulation = "SOX Section 302"
    default_message = "Dual approval required"

    __slots__ = ("action_type", "approvals_present", "approvals_required")

    def __init__(
        self,
        action_type: str,
        approvals_present: int,
        approvals_required: int = 2,
        **kwargs: Any,
    ) -> None:
        """Initialize dual approval missing error.

        Args:
            action_type: Type of action requiring dual approval.
            approvals_present: Number of approvals currently obtained.
            approvals_required: Number of approvals required (default 2).
            **kwargs: Additional arguments passed to parent.
        """
        self.action_type = action_type
        self.approvals_present = approvals_present
        self.approvals_required = approvals_required
        super().__init__(
            f"Action '{action_type}' requires {approvals_required} approvals "
            f"(found: {approvals_present})",
            context={
                "action_type": action_type,
                "approvals_present": approvals_present,
                "approvals_required": approvals_required,
            },
            **kwargs,
        )


class ClearanceInsufficientError(AuthorizationViolation):
    """Actor lacks required clearance level.

    Raised when: Access control check finds the actor's clearance level
    is below what's required for the operation.

    Regulatory basis:
    - PCI DSS 7.1: Restrict access to need-to-know
    - SOC 2 CC6.1: Logical and physical access controls
    - NIST SP 800-53 AC-3: Access enforcement

    Phrase: clearance_must_be_sufficient
    """

    default_regulation = "PCI DSS 7.1"
    default_message = "Insufficient clearance level"

    __slots__ = ("actor_id", "actual_level", "required_level")

    def __init__(
        self,
        actor_id: UUID,
        required_level: str,
        actual_level: str,
        **kwargs: Any,
    ) -> None:
        """Initialize clearance insufficient error.

        Args:
            actor_id: UUID of the actor attempting access.
            required_level: Clearance level required for the operation.
            actual_level: Actor's actual clearance level.
            **kwargs: Additional arguments passed to parent.
        """
        self.actor_id = actor_id
        self.required_level = required_level
        self.actual_level = actual_level
        super().__init__(
            f"Clearance insufficient: required '{required_level}', "
            f"actor {actor_id} has '{actual_level}'",
            context={
                "actor_id": str(actor_id),
                "required_level": required_level,
                "actual_level": actual_level,
            },
            **kwargs,
        )


# =============================================================================
# Evidence Domain Exceptions
# =============================================================================


class EvidenceNotBoundError(EvidenceViolation):
    """Required evidence not bound to decision.

    Raised when: A decision is attempted without the required CEP or other
    evidence being bound to justify it.

    Regulatory basis:
    - SOX Section 802: Documentation requirements
    - FCRA Section 1681m: Include copy of consumer report with adverse action
    - Employment law: Document factual basis for termination

    Phrase: evidence_must_be_bound
    """

    default_regulation = "SOX Section 802"
    default_message = "Evidence not bound to decision"

    __slots__ = ("decision_id", "evidence_type")

    def __init__(
        self,
        decision_id: UUID,
        evidence_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize evidence not bound error.

        Args:
            decision_id: UUID of the decision missing evidence.
            evidence_type: Type of evidence required (e.g., "cep", "attestation").
            **kwargs: Additional arguments passed to parent.
        """
        self.decision_id = decision_id
        self.evidence_type = evidence_type
        super().__init__(
            f"Decision {decision_id} requires bound evidence of type '{evidence_type}'",
            context={
                "decision_id": str(decision_id),
                "evidence_type": evidence_type,
            },
            **kwargs,
        )


class ChainBrokenError(EvidenceViolation):
    """Evidence chain integrity verification failed.

    Raised when: verify_chain finds a hash mismatch in the evidence chain,
    indicating tampering or corruption.

    Regulatory basis:
    - FRCP Rule 37(e): ESI preservation duty
    - FRE 901: Authentication of evidence
    - ISO 27037: Digital evidence handling

    Phrase: chain_must_be_intact
    """

    default_regulation = "FRCP Rule 37(e)"
    default_message = "Evidence chain is broken"

    __slots__ = ("actual_hash", "break_point", "chain_id", "expected_hash")

    def __init__(
        self,
        chain_id: UUID,
        break_point: UUID,
        expected_hash: str,
        actual_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize chain broken error.

        Args:
            chain_id: UUID of the evidence chain.
            break_point: UUID of the evidence item where the break occurred.
            expected_hash: Hash value that was expected.
            actual_hash: Hash value that was found.
            **kwargs: Additional arguments passed to parent.
        """
        self.chain_id = chain_id
        self.break_point = break_point
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"Chain {chain_id} broken at {break_point}: "
            f"hash mismatch (expected {expected_hash[:8]}..., got {actual_hash[:8]}...)",
            context={
                "chain_id": str(chain_id),
                "break_point": str(break_point),
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
            **kwargs,
        )


class HashMismatchError(EvidenceViolation):
    """Content hash does not match stored value.

    Raised when: verify_case_integrity or similar finds the computed hash
    of content does not match the recorded hash.

    Regulatory basis:
    - ISO 27001 A.12.4.1: Event logging integrity
    - SOX Section 802: Document integrity
    - NIST SP 800-53 SI-7: Software and information integrity

    Phrase: hash_must_match
    """

    default_regulation = "ISO 27001 A.12.4.1"
    default_message = "Content hash mismatch"

    __slots__ = ("actual_hash", "entity_id", "entity_type", "expected_hash")

    def __init__(
        self,
        entity_id: UUID,
        entity_type: str,
        expected_hash: str,
        actual_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize hash mismatch error.

        Args:
            entity_id: UUID of the entity with mismatched hash.
            entity_type: Type of entity (e.g., "evidence", "document", "cep").
            expected_hash: Hash value that was expected (stored).
            actual_hash: Hash value computed from current content.
            **kwargs: Additional arguments passed to parent.
        """
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"{entity_type} {entity_id} content hash mismatch "
            f"(expected {expected_hash[:8]}..., got {actual_hash[:8]}...)",
            context={
                "entity_id": str(entity_id),
                "entity_type": entity_type,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
            **kwargs,
        )


class CEPNotSealedError(EvidenceViolation):
    """Certified Evidence Packet is not in SEALED status.

    Raised when: An operation requires a sealed CEP but the CEP
    status is DRAFT, SUPERSEDED, or otherwise not SEALED.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action notice requires sealed evidence
    - Employment law: Termination decisions require sealed evidence packets
    - SOX Section 802: Document integrity for financial decisions

    Phrase: cep_must_be_sealed
    """

    default_regulation = "FCRA Section 1681m"
    default_message = "CEP must be sealed before use"

    __slots__ = ("cep_id", "current_status")

    def __init__(
        self,
        cep_id: UUID,
        current_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize CEP not sealed error.

        Args:
            cep_id: UUID of the CEP that is not sealed.
            current_status: Current status of the CEP (e.g., "DRAFT").
            **kwargs: Additional arguments passed to parent.
        """
        self.cep_id = cep_id
        self.current_status = current_status
        super().__init__(
            f"CEP {cep_id} has status '{current_status}' but must be SEALED",
            context={
                "cep_id": str(cep_id),
                "current_status": current_status,
                "required_status": "SEALED",
            },
            **kwargs,
        )


# =============================================================================
# Data Protection Domain Exceptions
# =============================================================================


class PIIPublicExposureError(DataProtectionViolation):
    """PII cannot be exposed to public audience.

    Raised when: Data classification check finds PII being shared with
    an audience level that doesn't have appropriate clearance.

    Regulatory basis:
    - GDPR Article 5(1)(f): Integrity and confidentiality principle
    - CCPA Section 1798.100: Consumer personal information protections
    - HIPAA 164.502: Uses and disclosures of PHI

    Phrase: pii_must_not_be_public
    """

    default_regulation = "GDPR Article 5(1)(f)"
    default_message = "PII cannot be exposed to public"

    __slots__ = ("data_classification", "target_audience")

    def __init__(
        self,
        data_classification: str,
        target_audience: str,
        **kwargs: Any,
    ) -> None:
        """Initialize PII public exposure error.

        Args:
            data_classification: Classification of the data (e.g., "PII", "PHI").
            target_audience: Audience the data would be shared with.
            **kwargs: Additional arguments passed to parent.
        """
        self.data_classification = data_classification
        self.target_audience = target_audience
        super().__init__(
            f"Data classified as '{data_classification}' cannot be "
            f"shared with audience '{target_audience}'",
            context={
                "data_classification": data_classification,
                "target_audience": target_audience,
            },
            **kwargs,
        )


class EncryptionMissingError(DataProtectionViolation):
    """Data transmission requires encryption.

    Raised when: A data transmission is attempted without the required
    encryption standard being in place.

    Regulatory basis:
    - GDPR Article 32: Security of processing (encryption)
    - PCI DSS 4.1: Encrypt transmission over open, public networks
    - HIPAA 164.312(e)(1): Transmission security

    Phrase: transmission_must_be_encrypted
    """

    default_regulation = "GDPR Article 32"
    default_message = "Data transmission requires encryption"

    __slots__ = ("actual_standard", "channel", "required_standard")

    def __init__(
        self,
        channel: str,
        required_standard: str,
        actual_standard: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize encryption missing error.

        Args:
            channel: Communication channel (e.g., "api", "email", "webhook").
            required_standard: Encryption standard required (e.g., "TLS 1.3").
            actual_standard: Encryption actually in use, if any.
            **kwargs: Additional arguments passed to parent.
        """
        self.channel = channel
        self.required_standard = required_standard
        self.actual_standard = actual_standard
        msg = f"Channel '{channel}' requires {required_standard} encryption"
        if actual_standard:
            msg += f" (found: {actual_standard})"
        else:
            msg += " (none found)"
        super().__init__(
            msg,
            context={
                "channel": channel,
                "required_standard": required_standard,
                "actual_standard": actual_standard,
            },
            **kwargs,
        )


class PIIExposureError(DataProtectionViolation):
    """PII exposed in inappropriate visibility context.

    Raised when: pii_must_not_be_public finds PII-containing data
    with public visibility.

    Regulatory basis:
    - GDPR Article 5: Principles relating to processing of personal data
    - CCPA Section 1798.100: Consumer personal information protections

    Phrase: pii_must_not_be_public
    """

    default_regulation = "GDPR Article 5"
    default_message = "PII cannot be exposed publicly"

    __slots__ = ("contains_pii", "visibility")

    def __init__(
        self,
        visibility: str,
        contains_pii: bool,
        **kwargs: Any,
    ) -> None:
        """Initialize PII exposure error.

        Args:
            visibility: The visibility level of the data (e.g., "public").
            contains_pii: Whether the data contains PII.
            **kwargs: Additional arguments passed to parent.
        """
        self.visibility = visibility
        self.contains_pii = contains_pii
        super().__init__(
            f"Data containing PII cannot have visibility '{visibility}'",
            context={
                "visibility": visibility,
                "contains_pii": contains_pii,
            },
            **kwargs,
        )


class UnencryptedTransmissionError(DataProtectionViolation):
    """Sensitive data transmitted without encryption.

    Raised when: transmission_must_be_encrypted finds unencrypted
    transmission of confidential, restricted, or PII data.

    Regulatory basis:
    - GDPR Article 32: Security of processing
    - HIPAA Section 164.312: Technical safeguards

    Phrase: transmission_must_be_encrypted
    """

    default_regulation = "GDPR Article 32"
    default_message = "Sensitive data transmission requires encryption"

    __slots__ = ("data_classification", "is_encrypted")

    def __init__(
        self,
        is_encrypted: bool,
        data_classification: str,
        **kwargs: Any,
    ) -> None:
        """Initialize unencrypted transmission error.

        Args:
            is_encrypted: Whether the transmission is encrypted (False).
            data_classification: Classification of the data being transmitted.
            **kwargs: Additional arguments passed to parent.
        """
        self.is_encrypted = is_encrypted
        self.data_classification = data_classification
        super().__init__(
            f"Data classified as '{data_classification}' must be encrypted during transmission",
            context={
                "is_encrypted": is_encrypted,
                "data_classification": data_classification,
            },
            **kwargs,
        )


class ClassificationViolationError(DataProtectionViolation):
    """Operation not allowed for data classification level.

    Raised when: data_classification_must_allow finds an operation
    that is not permitted for the data's classification level.

    Regulatory basis:
    - SOC 2 CC6.1: Logical and physical access controls
    - ISO 27001: Information security management

    Phrase: data_classification_must_allow
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Operation not allowed for data classification"

    __slots__ = ("allowed_operations", "classification", "operation")

    def __init__(
        self,
        classification: str,
        operation: str,
        allowed_operations: set[str],
        **kwargs: Any,
    ) -> None:
        """Initialize classification violation error.

        Args:
            classification: The data classification level.
            operation: The attempted operation.
            allowed_operations: Set of operations allowed for this classification.
            **kwargs: Additional arguments passed to parent.
        """
        self.classification = classification
        self.operation = operation
        self.allowed_operations = allowed_operations
        super().__init__(
            f"Operation '{operation}' not allowed for classification '{classification}'. "
            f"Allowed: {sorted(allowed_operations)}",
            context={
                "classification": classification,
                "operation": operation,
                "allowed_operations": sorted(allowed_operations),
            },
            **kwargs,
        )


class RetentionExceededError(DataProtectionViolation):
    """Data retained beyond allowed retention period.

    Raised when: retention_must_not_be_exceeded finds data that has
    exceeded its retention period and should have been deleted.

    Regulatory basis:
    - GDPR Article 5(1)(e): Storage limitation principle
    - CCPA Section 1798.105: Consumer's right to deletion

    Phrase: retention_must_not_be_exceeded
    """

    default_regulation = "GDPR Article 5(1)(e)"
    default_message = "Data retention period exceeded"

    __slots__ = ("current_time", "retention_end")

    def __init__(
        self,
        retention_end: datetime,
        current_time: datetime,
        **kwargs: Any,
    ) -> None:
        """Initialize retention exceeded error.

        Args:
            retention_end: When the retention period ended.
            current_time: The current time when violation was detected.
            **kwargs: Additional arguments passed to parent.
        """
        self.retention_end = retention_end
        self.current_time = current_time
        exceeded_by = current_time - retention_end
        super().__init__(
            f"Data retention period ended at {retention_end.isoformat()}, "
            f"exceeded by {exceeded_by}",
            context={
                "retention_end": retention_end.isoformat(),
                "current_time": current_time.isoformat(),
                "exceeded_by_seconds": int(exceeded_by.total_seconds()),
            },
            **kwargs,
        )


# =============================================================================
# AI Governance Domain Exceptions
# =============================================================================


class HumanReviewMissingError(AIGovernanceViolation):
    """Human review required but not present.

    Raised when: require_human_review_present finds no completed human
    review record for a decision requiring human oversight.

    Regulatory basis:
    - EU AI Act Article 14: Human oversight for high-risk AI
    - GDPR Article 22: Right to human intervention in automated decisions
    - NYC LL144 Section 20-871: AEDT candidate notice requirements

    Phrase: human_review_must_be_present
    """

    default_regulation = "EU AI Act Article 14"
    default_message = "Human review required"

    __slots__ = ("decision_id", "risk_level")

    def __init__(
        self,
        decision_id: UUID,
        risk_level: str,
        **kwargs: Any,
    ) -> None:
        """Initialize human review missing error.

        Args:
            decision_id: UUID of the decision requiring human review.
            risk_level: Risk classification of the decision (e.g., "high", "medium").
            **kwargs: Additional arguments passed to parent.
        """
        self.decision_id = decision_id
        self.risk_level = risk_level
        super().__init__(
            f"Decision {decision_id} (risk level: {risk_level}) "
            f"requires human review before execution",
            context={
                "decision_id": str(decision_id),
                "risk_level": risk_level,
            },
            **kwargs,
        )


class BiasAssessmentMissingError(AIGovernanceViolation):
    """Bias assessment required but not documented.

    Raised when: require_bias_assessment_documented finds no completed
    bias audit for an AI/ML tool used in employment decisions.

    Regulatory basis:
    - NYC LL144 Section 20-870: Annual bias audit requirement for AEDT
    - EU AI Act Article 9: Risk management for high-risk AI
    - Colorado SB 21-169 / SB 205: Algorithmic discrimination protections

    Phrase: bias_assessment_must_be_documented
    """

    default_regulation = "NYC LL144"
    default_message = "Bias assessment required"

    __slots__ = ("assessment_type", "tool_id")

    def __init__(
        self,
        tool_id: UUID,
        assessment_type: str,
        **kwargs: Any,
    ) -> None:
        """Initialize bias assessment missing error.

        Args:
            tool_id: UUID of the AI/ML tool requiring bias assessment.
            assessment_type: Type of assessment required (e.g., "disparate_impact").
            **kwargs: Additional arguments passed to parent.
        """
        self.tool_id = tool_id
        self.assessment_type = assessment_type
        super().__init__(
            f"Tool {tool_id} requires documented {assessment_type} bias assessment",
            context={
                "tool_id": str(tool_id),
                "assessment_type": assessment_type,
            },
            **kwargs,
        )


class ToolConfigMismatchError(AIGovernanceViolation):
    """Tool configuration differs from validated version.

    Raised when: verify_same_tool finds the current configuration hash
    differs from the hash recorded during bias audit validation.

    Regulatory basis:
    - NYC LL144: AEDT must be same tool as audited
    - EU AI Act Article 9: Change management for high-risk AI
    - FDA 21 CFR Part 11: Validated system requirements

    Phrase: same_tool_must_be_verified
    """

    default_regulation = "NYC LL144"
    default_message = "Tool configuration mismatch"

    __slots__ = ("actual_config_hash", "expected_config_hash", "tool_id")

    def __init__(
        self,
        tool_id: UUID,
        expected_config_hash: str,
        actual_config_hash: str,
        **kwargs: Any,
    ) -> None:
        """Initialize tool config mismatch error.

        Args:
            tool_id: UUID of the AI/ML tool.
            expected_config_hash: Configuration hash from bias audit.
            actual_config_hash: Current configuration hash.
            **kwargs: Additional arguments passed to parent.
        """
        self.tool_id = tool_id
        self.expected_config_hash = expected_config_hash
        self.actual_config_hash = actual_config_hash
        super().__init__(
            f"Tool {tool_id} configuration changed since validation "
            f"(expected {expected_config_hash[:8]}..., found {actual_config_hash[:8]}...)",
            context={
                "tool_id": str(tool_id),
                "expected_config_hash": expected_config_hash,
                "actual_config_hash": actual_config_hash,
            },
            **kwargs,
        )


class DisclosureMissingError(AIGovernanceViolation):
    """Required AI/AEDT disclosure not provided before action.

    Raised when: An employment decision using AI/AEDT is attempted
    without prior disclosure to the candidate/employee as required
    by various AI transparency laws.

    Regulatory basis:
    - NYC LL144 Section 20-871(b): Notice to candidates before AEDT use
    - Illinois BIPA: Biometric data disclosure requirements
    - Colorado SB 205: AI disclosure for consequential decisions
    - EU AI Act Article 13: Transparency obligations

    Phrase: disclosure_must_be_provided
    """

    default_regulation = "NYC LL144 Section 20-871(b)"
    default_message = "AI/AEDT disclosure required before action"

    __slots__ = ("action_type", "disclosure_status")

    def __init__(
        self,
        action_type: str,
        disclosure_status: str,
        **kwargs: Any,
    ) -> None:
        """Initialize disclosure missing error.

        Args:
            action_type: Type of action requiring disclosure (e.g., "aedt_screening").
            disclosure_status: Current status of disclosure (e.g., "not_provided", "after_action").
            **kwargs: Additional arguments passed to parent.
        """
        self.action_type = action_type
        self.disclosure_status = disclosure_status
        super().__init__(
            f"Action '{action_type}' requires prior AI/AEDT disclosure "
            f"(current status: {disclosure_status})",
            context={
                "action_type": action_type,
                "disclosure_status": disclosure_status,
            },
            **kwargs,
        )
