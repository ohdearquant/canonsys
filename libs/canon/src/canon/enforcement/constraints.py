"""Cross-cutting truth machine constraints for regulatory invariants.

This module provides the vocabulary of constraints that encode regulatory
requirements as executable assertions. Each constraint either succeeds
silently (invariant satisfied) or raises a typed exception (invariant
violated).

Design Philosophy:
    Constraints are truth assertions - they encode regulatory invariants as
    self-documenting propositions. Unlike features (async DB operations),
    constraints are:

    1. Pure functions - No side effects, no DB access
    2. Sync by default - Only async when absolutely necessary
    3. Fail-fast - Raise immediately on violation (no soft booleans)
    4. Domain-bound - Named for regulatory concepts, not generic utilities

    The constraint IS the law. Reading the constraint name tells you the
    regulatory requirement being enforced.

Truth Machine Semantics:
    If a constraint executes without raising, the regulatory requirement is
    satisfied BY CONSTRUCTION. There is no need to check return values
    or handle success cases - the act of successful execution IS the proof.

Module Organization:
    Cross-cutting constraints (this file) vs. feature-local constraints:
    - This file: Timing, authorization, evidence, AI governance, data protection
    - Feature-local: Consent constraints in features/consent/actions/constraints.py

Usage:
    from canon.enforcement.constraints import (
        # Timing
        waiting_period_must_be_elapsed,
        notice_must_precede_action,
        evidence_must_be_fresh,
        deadline_must_not_be_exceeded,
        # Authorization
        preparer_must_not_be_approver,
        dual_approval_must_be_present,
        clearance_must_be_sufficient,
        approvers_must_be_distinct,
        # Evidence
        evidence_must_be_bound,
        chain_must_be_intact,
        hash_must_match,
        cep_must_be_sealed,
        # AI governance
        human_review_must_be_present,
        bias_assessment_must_be_documented,
        same_tool_must_be_verified,
        disclosure_must_be_provided,
        # Data protection
        pii_must_not_be_public,
        transmission_must_be_encrypted,
        data_classification_must_allow,
        retention_must_not_be_exceeded,
    )

    # Truth machine composition - if we reach the end, ALL invariants hold
    preparer_must_not_be_approver(preparer_id, approver_id)
    waiting_period_must_be_elapsed(period)
    # If we reach here, ALL invariants are satisfied by construction
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

from canon.enforcement.exceptions import (
    BiasAssessmentMissingError,
    CEPNotSealedError,
    ChainBrokenError,
    ClassificationViolationError,
    ClearanceInsufficientError,
    DisclosureMissingError,
    DualApprovalMissingError,
    EvidenceNotBoundError,
    EvidenceStaleError,
    HashMismatchError,
    HumanReviewMissingError,
    NoticePrecedenceError,
    PIIExposureError,
    RetentionExceededError,
    SoDViolationError,
    TimingViolation,
    ToolConfigMismatchError,
    UnencryptedTransmissionError,
    WaitingPeriodNotElapsedError,
)

__all__ = [
    # Timing
    "waiting_period_must_be_elapsed",
    "notice_must_precede_action",
    "evidence_must_be_fresh",
    "deadline_must_not_be_exceeded",
    # Authorization
    "preparer_must_not_be_approver",
    "dual_approval_must_be_present",
    "clearance_must_be_sufficient",
    "approvers_must_be_distinct",
    # Evidence
    "evidence_must_be_bound",
    "chain_must_be_intact",
    "hash_must_match",
    "cep_must_be_sealed",
    # AI governance
    "human_review_must_be_present",
    "bias_assessment_must_be_documented",
    "same_tool_must_be_verified",
    "disclosure_must_be_provided",
    # Data protection
    "pii_must_not_be_public",
    "transmission_must_be_encrypted",
    "data_classification_must_allow",
    "retention_must_not_be_exceeded",
]


# =============================================================================
# Helpers
# =============================================================================


def _utc_now() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(UTC)


def _ensure_tz_aware(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware, assuming UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# Classifications that require encryption during transmission
_SENSITIVE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        "confidential",
        "restricted",
        "pii",
    }
)


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class HasApproverId(Protocol):
    """Protocol for objects with an approver_id attribute."""

    @property
    def approver_id(self) -> UUID:
        """UUID of the approver."""
        ...


@runtime_checkable
class WaitingPeriodLike(Protocol):
    """Structural type for waiting period state objects.

    Defines the interface expected by waiting_period_must_be_elapsed().
    Implemented by timing package's waiting period query results.
    """

    @property
    def elapsed(self) -> bool: ...

    @property
    def paused_at(self) -> datetime | None: ...

    @property
    def resumed_at(self) -> datetime | None: ...

    @property
    def started_at(self) -> datetime: ...

    @property
    def notice_id(self) -> UUID: ...

    @property
    def required_days(self) -> int: ...


# =============================================================================
# Timing Constraints
# =============================================================================


def waiting_period_must_be_elapsed(period: WaitingPeriodLike) -> None:
    """Assert FCRA waiting period has elapsed.

    Regulatory basis: FCRA Section 1681b(b)(3) requires a "reasonable
    period" (typically 5 business days) between pre-adverse action
    notice and final adverse action.

    Args:
        period: The waiting period state object from get_waiting_period.

    Raises:
        WaitingPeriodNotElapsedError: If period is not elapsed,
            if period is paused, or if ends_at is in the future.

    Truth Machine Semantics:
        If this function returns, the dispute window has elapsed and
        adverse action may legally proceed.
    """
    # Check if period is paused (dispute in progress)
    if period.paused_at is not None and period.resumed_at is None:
        started = _ensure_tz_aware(period.started_at)
        paused = _ensure_tz_aware(period.paused_at)
        elapsed_days = (paused - started).days
        raise WaitingPeriodNotElapsedError(
            notice_id=period.notice_id,
            required_days=period.required_days,
            elapsed_days=elapsed_days,
        )

    if not period.elapsed:
        started = _ensure_tz_aware(period.started_at)
        now = _utc_now()
        elapsed_days = (now - started).days
        raise WaitingPeriodNotElapsedError(
            notice_id=period.notice_id,
            required_days=period.required_days,
            elapsed_days=elapsed_days,
        )


def notice_must_precede_action(
    notice_sent_at: datetime | None,
    action_at: datetime,
    notice_type: str,
) -> None:
    """Assert required notice was sent before the action.

    Regulatory basis: FCRA Section 1681m requires pre-adverse action
    notice before adverse action. WARN Act requires 60-day notice
    for mass layoffs.

    Args:
        notice_sent_at: Timestamp when notice was sent (None if not sent).
        action_at: Timestamp of the intended action.
        notice_type: Type of notice (e.g., "pre_adverse_action", "warn_act").

    Raises:
        NoticePrecedenceError: If notice_sent_at is None or >= action_at.
    """
    if notice_sent_at is None:
        raise NoticePrecedenceError(
            action_type="adverse_action",
            notice_required=notice_type,
            notice_status="not_sent",
        )

    notice_tz = _ensure_tz_aware(notice_sent_at)
    action_tz = _ensure_tz_aware(action_at)

    if notice_tz >= action_tz:
        raise NoticePrecedenceError(
            action_type="adverse_action",
            notice_required=notice_type,
            notice_status="sent_after_action",
        )


def evidence_must_be_fresh(
    evidence_timestamp: datetime,
    max_age_hours: int,
    now: datetime | None = None,
    *,
    evidence_id: UUID | None = None,
) -> None:
    """Assert evidence is within acceptable freshness window.

    Regulatory basis: SOC 2 CC4.1 requires information to be current.

    Args:
        evidence_timestamp: When the evidence was created/collected.
        max_age_hours: Maximum allowed age in hours.
        now: Reference time (defaults to utcnow).
        evidence_id: Optional UUID of the evidence for error context.

    Raises:
        EvidenceStaleError: If evidence age exceeds max_age_hours.
    """
    reference = now if now is not None else _utc_now()

    evidence_tz = _ensure_tz_aware(evidence_timestamp)
    reference_tz = _ensure_tz_aware(reference)

    age_delta = reference_tz - evidence_tz
    actual_age_hours = int(age_delta.total_seconds() / 3600)

    if actual_age_hours > max_age_hours:
        eid = evidence_id if evidence_id is not None else UUID(int=0)
        raise EvidenceStaleError(
            evidence_id=eid,
            max_age_hours=max_age_hours,
            actual_age_hours=actual_age_hours,
        )


def deadline_must_not_be_exceeded(
    deadline: datetime,
    now: datetime | None = None,
) -> None:
    """Assert a regulatory or contractual deadline has not passed.

    Args:
        deadline: The deadline that must not be exceeded.
        now: Reference time (defaults to utcnow).

    Raises:
        TimingViolation: If now > deadline.
    """
    reference = now if now is not None else _utc_now()

    deadline_tz = _ensure_tz_aware(deadline)
    reference_tz = _ensure_tz_aware(reference)

    if reference_tz > deadline_tz:
        raise TimingViolation(
            message=f"Deadline exceeded: {deadline.isoformat()} < {reference.isoformat()}",
            regulation="Timing Requirement",
            context={
                "deadline": deadline.isoformat(),
                "current_time": reference.isoformat(),
                "exceeded_by_seconds": int((reference_tz - deadline_tz).total_seconds()),
            },
        )


# =============================================================================
# Authorization Constraints
# =============================================================================


def preparer_must_not_be_approver(
    preparer_id: UUID,
    approver_id: UUID,
) -> None:
    """Assert segregation of duties between preparer and approver.

    Regulatory basis: SOX Section 404 requires segregation of duties
    in internal controls.

    Args:
        preparer_id: UUID of the person who prepared the transaction.
        approver_id: UUID of the person approving the transaction.

    Raises:
        SoDViolationError: If preparer_id == approver_id.
    """
    if preparer_id == approver_id:
        raise SoDViolationError(
            identity_id=preparer_id,
            role_a="preparer",
            role_b="approver",
        )


def dual_approval_must_be_present(
    approvals: Sequence[HasApproverId],
    min_required: int = 2,
) -> None:
    """Assert required number of approvals are present.

    Regulatory basis: SOX Section 302 and 404 require dual control
    for high-risk operations.

    Args:
        approvals: Sequence of approval records (must have approver_id).
        min_required: Minimum approvals required (default 2 per SOX).

    Raises:
        DualApprovalMissingError: If len(approvals) < min_required.
    """
    present = len(approvals)
    if present < min_required:
        raise DualApprovalMissingError(
            action_type="operation_requiring_approval",
            approvals_present=present,
            approvals_required=min_required,
        )


def clearance_must_be_sufficient(
    actor_level: str,
    required_level: str,
    level_order: Sequence[str],
) -> None:
    """Assert actor has sufficient clearance level for the operation.

    Regulatory basis: PCI DSS 7.1 requires access restricted to
    need-to-know basis with appropriate clearance levels.

    Args:
        actor_level: The actor's current clearance level.
        required_level: The clearance level required for the operation.
        level_order: Ordered sequence of levels from lowest to highest.

    Raises:
        ClearanceInsufficientError: If actor_level < required_level.
        ValueError: If actor_level or required_level not in level_order.
    """
    if actor_level not in level_order:
        msg = f"Actor level '{actor_level}' not in level_order: {list(level_order)}"
        raise ValueError(msg)
    if required_level not in level_order:
        msg = f"Required level '{required_level}' not in level_order: {list(level_order)}"
        raise ValueError(msg)

    level_list = list(level_order)
    actor_rank = level_list.index(actor_level)
    required_rank = level_list.index(required_level)

    if actor_rank < required_rank:
        raise ClearanceInsufficientError(
            actor_id=UUID(int=0),
            required_level=required_level,
            actual_level=actor_level,
        )


def approvers_must_be_distinct(
    approver_ids: Sequence[UUID],
) -> None:
    """Assert all approvers in a chain are distinct identities.

    Regulatory basis: SOX Section 404 requires independent approvers.

    Args:
        approver_ids: Sequence of approver UUIDs to check for uniqueness.

    Raises:
        SoDViolationError: If any UUID appears more than once.
    """
    seen: set[UUID] = set()

    for approver_id in approver_ids:
        if approver_id in seen:
            raise SoDViolationError(
                identity_id=approver_id,
                role_a="approver",
                role_b="approver",
            )
        seen.add(approver_id)


# =============================================================================
# Evidence Constraints
# =============================================================================


def evidence_must_be_bound(
    evidence_id: UUID | str,
    case_id: UUID | str,
    *,
    bound_case_id: UUID | str | None = None,
) -> Literal[True]:
    """Assert evidence is bound to the specified case.

    Regulatory basis:
    - FRCP Rule 37: ESI must be preserved and traceable to matters
    - SOX Section 802: Documents supporting decisions must be bound

    Args:
        evidence_id: UUID of the evidence item to validate.
        case_id: UUID of the case the evidence should be bound to.
        bound_case_id: Actual case_id the evidence is bound to.

    Raises:
        EvidenceNotBoundError: If evidence is not bound or bound to wrong case.

    Returns:
        Literal[True]: Evidence is confirmed bound to the specified case.
    """
    case_str = str(case_id)

    if bound_case_id is None:
        try:
            decision_uuid = UUID(case_str) if len(case_str) == 36 else UUID(int=0)
        except (ValueError, AttributeError):
            decision_uuid = UUID(int=0)

        raise EvidenceNotBoundError(
            decision_id=decision_uuid,
            evidence_type="evidence",
            regulation="FRCP Rule 37",
        )

    bound_case_str = str(bound_case_id)

    if bound_case_str != case_str:
        try:
            decision_uuid = UUID(case_str) if len(case_str) == 36 else UUID(int=0)
        except (ValueError, AttributeError):
            decision_uuid = UUID(int=0)

        raise EvidenceNotBoundError(
            decision_id=decision_uuid,
            evidence_type="evidence",
            regulation="SOX Section 802",
        )

    return True


def chain_must_be_intact(
    evidence_ids: Sequence[UUID | str],
    *,
    chain_hashes: Sequence[tuple[str, str]] | None = None,
) -> Literal[True]:
    """Assert evidence chain linkage is intact (no tampering).

    Regulatory basis:
    - SOX Section 802: Document integrity for audit trails
    - SOC 2 CC6.1: System integrity controls

    Args:
        evidence_ids: Sequence of evidence UUIDs in chain order.
        chain_hashes: Sequence of (prev_hash, current_hash) tuples.

    Raises:
        ChainBrokenError: If any link has a hash mismatch.

    Returns:
        Literal[True]: Chain integrity is confirmed.
    """
    if chain_hashes is None or len(chain_hashes) == 0:
        if len(evidence_ids) > 0:
            try:
                first_id = evidence_ids[0]
                chain_uuid = (
                    UUID(str(first_id))
                    if isinstance(first_id, str) and len(str(first_id)) == 36
                    else (first_id if isinstance(first_id, UUID) else UUID(int=0))
                )
                break_uuid = chain_uuid
            except (ValueError, AttributeError):
                chain_uuid = UUID(int=0)
                break_uuid = UUID(int=0)

            raise ChainBrokenError(
                chain_id=chain_uuid,
                break_point=break_uuid,
                expected_hash="<chain_data_required>",
                actual_hash="<no_chain_data_provided>",
                regulation="SOX Section 802",
            )
        return True

    if len(evidence_ids) != len(chain_hashes):
        first_id = evidence_ids[0] if evidence_ids else UUID(int=0)
        try:
            chain_uuid = UUID(str(first_id)) if isinstance(first_id, str) else first_id
        except (ValueError, AttributeError):
            chain_uuid = UUID(int=0)

        raise ChainBrokenError(
            chain_id=chain_uuid,
            break_point=chain_uuid,
            expected_hash=f"<{len(evidence_ids)}_entries>",
            actual_hash=f"<{len(chain_hashes)}_entries>",
            regulation="SOC 2 CC6.1",
        )

    expected_prev_hash = ""

    for _i, (evidence_id, (prev_hash, current_hash)) in enumerate(zip(evidence_ids, chain_hashes)):
        evidence_str = str(evidence_id)

        if prev_hash != expected_prev_hash:
            try:
                chain_uuid = UUID(str(evidence_ids[0])) if evidence_ids else UUID(int=0)
                break_uuid = UUID(evidence_str) if len(evidence_str) == 36 else UUID(int=0)
            except (ValueError, AttributeError):
                chain_uuid = UUID(int=0)
                break_uuid = UUID(int=0)

            raise ChainBrokenError(
                chain_id=chain_uuid,
                break_point=break_uuid,
                expected_hash=expected_prev_hash or "<genesis>",
                actual_hash=prev_hash or "<genesis>",
                regulation="SOX Section 802",
            )

        expected_prev_hash = current_hash

    return True


def hash_must_match(
    content: bytes,
    expected_hash: str,
    *,
    algorithm: str = "sha256",
) -> Literal[True]:
    """Assert content hash matches expected value.

    Regulatory basis:
    - SOX Section 802: Document integrity verification
    - SOC 2 CC6.1: Data integrity controls

    Args:
        content: The content bytes to hash.
        expected_hash: The expected hash value (hex-encoded).
        algorithm: Hash algorithm to use (default: sha256).

    Raises:
        HashMismatchError: If computed hash does not match expected_hash.

    Returns:
        Literal[True]: Hash integrity is confirmed.
    """
    hasher = hashlib.new(algorithm)
    hasher.update(content)
    actual_hash = hasher.hexdigest()

    if actual_hash.lower() != expected_hash.lower():
        raise HashMismatchError(
            entity_id=UUID(int=0),
            entity_type="content",
            expected_hash=expected_hash,
            actual_hash=actual_hash,
            regulation="SOX Section 802",
        )

    return True


def cep_must_be_sealed(
    cep_status: str,
    *,
    cep_id: UUID | str | None = None,
) -> Literal[True]:
    """Assert Certified Evidence Packet is in SEALED status.

    Regulatory basis:
    - FCRA Section 1681m: Pre-adverse action requires sealed evidence
    - Employment law: Termination decisions require sealed CEPs

    Args:
        cep_status: Current status of the CEP (e.g., "DRAFT", "SEALED").
        cep_id: Optional CEP UUID for error context.

    Raises:
        CEPNotSealedError: If cep_status is not "SEALED".

    Returns:
        Literal[True]: CEP is confirmed sealed.
    """
    if cep_status.upper() != "SEALED":
        if cep_id is not None:
            try:
                cep_uuid = UUID(str(cep_id)) if isinstance(cep_id, str) else cep_id
            except (ValueError, AttributeError):
                cep_uuid = UUID(int=0)
        else:
            cep_uuid = UUID(int=0)

        raise CEPNotSealedError(
            cep_id=cep_uuid,
            current_status=cep_status,
            regulation="FCRA Section 1681m",
        )

    return True


# =============================================================================
# AI Governance Constraints
# =============================================================================


def human_review_must_be_present(
    human_review_id: UUID | str | None,
) -> Literal[True]:
    """Assert human review record exists for high-risk AI decision.

    Regulatory basis:
    - EU AI Act Article 14: Human oversight for high-risk AI systems
    - NYC LL144: AEDT use requires documented human involvement

    Args:
        human_review_id: UUID or string ID of the human review record.

    Returns:
        Literal[True] if human review is present.

    Raises:
        HumanReviewMissingError: If human_review_id is None.
    """
    if human_review_id is None:
        raise HumanReviewMissingError(
            decision_id=UUID(int=0),
            risk_level="high",
        )
    return True


def bias_assessment_must_be_documented(
    assessment_id: UUID | str | None,
) -> Literal[True]:
    """Assert bias assessment is documented for AI/AEDT tool.

    Regulatory basis:
    - NYC LL144 Section 20-870: AEDT must have bias audit within past year
    - Colorado SB 21-169 / SB 205: Algorithmic disparate impact assessment

    Args:
        assessment_id: UUID or string ID of the bias assessment record.

    Returns:
        Literal[True] if bias assessment is documented.

    Raises:
        BiasAssessmentMissingError: If assessment_id is None.
    """
    if assessment_id is None:
        raise BiasAssessmentMissingError(
            tool_id=UUID(int=0),
            assessment_type="disparate_impact",
        )
    return True


def same_tool_must_be_verified(
    tool_hash: str,
    expected_hash: str,
) -> Literal[True]:
    """Assert AEDT tool configuration matches validated/audited version.

    Regulatory basis:
    - NYC LL144: AEDT in production must match bias-audited version

    Args:
        tool_hash: Current configuration hash of the AEDT tool.
        expected_hash: Configuration hash from the bias audit record.

    Returns:
        Literal[True] if hashes match.

    Raises:
        ToolConfigMismatchError: If tool_hash != expected_hash.
    """
    if tool_hash != expected_hash:
        raise ToolConfigMismatchError(
            tool_id=UUID(int=0),
            expected_config_hash=expected_hash,
            actual_config_hash=tool_hash,
        )
    return True


def disclosure_must_be_provided(
    disclosure_timestamp: datetime | None,
    action_timestamp: datetime,
) -> Literal[True]:
    """Assert AI/AEDT disclosure was provided before the action.

    Regulatory basis:
    - NYC LL144 Section 20-871(b): Notify candidates 10 days before AEDT use
    - Illinois BIPA: Disclosure required before biometric data collection

    Args:
        disclosure_timestamp: When disclosure was provided.
        action_timestamp: When the AI-assisted action is/was taken.

    Returns:
        Literal[True] if disclosure preceded action.

    Raises:
        DisclosureMissingError: If disclosure_timestamp is None or after action.
    """
    if disclosure_timestamp is None:
        raise DisclosureMissingError(
            action_type="aedt_decision",
            disclosure_status="not_provided",
        )

    disclosure_tz = _ensure_tz_aware(disclosure_timestamp)
    action_tz = _ensure_tz_aware(action_timestamp)

    if disclosure_tz >= action_tz:
        raise DisclosureMissingError(
            action_type="aedt_decision",
            disclosure_status="provided_after_action",
        )

    return True


# =============================================================================
# Data Protection Constraints
# =============================================================================


def pii_must_not_be_public(
    visibility: str,
    contains_pii: bool,
) -> Literal[True]:
    """Assert PII data is not exposed with public visibility.

    Regulatory basis:
    - GDPR Article 5: Principles relating to processing of personal data
    - CCPA Section 1798.100: Consumer personal information protections

    Args:
        visibility: The visibility level of the data.
        contains_pii: Whether the data contains PII.

    Returns:
        Literal[True]: Proves the invariant holds.

    Raises:
        PIIExposureError: If visibility is "public" and contains_pii is True.
    """
    if visibility == "public" and contains_pii:
        raise PIIExposureError(
            visibility=visibility,
            contains_pii=contains_pii,
            regulation="GDPR Article 5, CCPA Section 1798.100",
        )
    return True


def transmission_must_be_encrypted(
    is_encrypted: bool,
    data_classification: str,
) -> Literal[True]:
    """Assert sensitive data transmission is encrypted.

    Regulatory basis:
    - GDPR Article 32: Security of processing
    - HIPAA Section 164.312: Technical safeguards

    Args:
        is_encrypted: Whether the transmission channel is encrypted.
        data_classification: Classification of the data being transmitted.

    Returns:
        Literal[True]: Proves the invariant holds.

    Raises:
        UnencryptedTransmissionError: If not encrypted and classification
            is in ("confidential", "restricted", "pii").
    """
    classification_lower = data_classification.lower()

    if not is_encrypted and classification_lower in _SENSITIVE_CLASSIFICATIONS:
        raise UnencryptedTransmissionError(
            is_encrypted=is_encrypted,
            data_classification=data_classification,
            regulation="GDPR Article 32, HIPAA Section 164.312",
        )
    return True


def data_classification_must_allow(
    classification: str,
    operation: str,
    allowed_operations: set[str],
) -> Literal[True]:
    """Assert operation is allowed for the data classification level.

    Regulatory basis:
    - SOC 2 CC6.1: Logical and physical access controls
    - ISO 27001: Information security management

    Args:
        classification: The data classification level.
        operation: The operation being attempted.
        allowed_operations: Set of operations allowed for this classification.

    Returns:
        Literal[True]: Proves the invariant holds.

    Raises:
        ClassificationViolationError: If operation is not in allowed_operations.
    """
    if operation not in allowed_operations:
        raise ClassificationViolationError(
            classification=classification,
            operation=operation,
            allowed_operations=allowed_operations,
            regulation="SOC 2 CC6.1, ISO 27001",
        )
    return True


def retention_must_not_be_exceeded(
    retention_end: datetime,
    current_time: datetime,
) -> Literal[True]:
    """Assert data retention period has not been exceeded.

    Regulatory basis:
    - GDPR Article 5(1)(e): Storage limitation principle
    - CCPA Section 1798.105: Consumer's right to deletion

    Args:
        retention_end: The datetime when the retention period ends.
        current_time: The current datetime to check against.

    Returns:
        Literal[True]: Proves the invariant holds.

    Raises:
        RetentionExceededError: If current_time > retention_end.
    """
    retention_end_tz = _ensure_tz_aware(retention_end)
    current_time_tz = _ensure_tz_aware(current_time)

    if current_time_tz > retention_end_tz:
        raise RetentionExceededError(
            retention_end=retention_end,
            current_time=current_time,
            regulation="GDPR Article 5(1)(e), CCPA Section 1798.105",
        )
    return True
