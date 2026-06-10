"""Corporate domain result types.

Frozen dataclasses returned by corporate derivation actions.

These are DERIVATION results - they derive requirements from evidence,
not verify user assertions. This is the anti-gaming pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from .enums import (
        CarveOutStatus,
        CleanTeamReason,
        ConditionSatisfactionStatus,
        ConditionType,
    )

__all__ = [
    "CarveOutReadinessResult",
    "CleanTeamRequiredResult",
    "ConditionSatisfactionResult",
    "ConditionalFindingsAddressedResult",
]


@dataclass(frozen=True, slots=True)
class CleanTeamRequiredResult:
    """Result of clean team requirement derivation.

    Anti-gaming: Derives whether clean team is required based on data
    categories present in the deal, NOT user assertion.

    Attributes:
        deal_id: M&A deal being assessed.
        required: Whether clean team is required (derived from evidence).
        reason: Primary reason clean team is required (if required).
        data_categories: Sensitive data categories found in deal.
        sensitivity_triggers: Which categories triggered the requirement.
        evidence_hash: Hash of evidence used for derivation (audit trail).
        derived_at: When the derivation was computed.
    """

    deal_id: UUID
    required: bool
    reason: CleanTeamReason
    data_categories: tuple[str, ...]
    sensitivity_triggers: tuple[str, ...]
    evidence_hash: str | None = None
    derived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConditionalFindingsAddressedResult:
    """Result of conditional findings addressed derivation.

    Anti-gaming: Derives whether ALL conditional findings from due
    diligence have been properly addressed (remediated, waived, or
    deferred with approval).

    Attributes:
        deal_id: M&A deal being assessed.
        addressed: Whether all findings are addressed.
        total_findings: Total number of conditional findings.
        open_count: Number of findings still open.
        in_progress_count: Number of findings in progress.
        remediated_count: Number of remediated findings.
        waived_count: Number of waived findings.
        blocked_count: Number of blocked findings.
        deferred_count: Number of findings deferred to closing.
        blocking_findings: IDs of findings blocking deal progress.
        evidence_hash: Hash of evidence used for derivation.
        derived_at: When the derivation was computed.
    """

    deal_id: UUID
    addressed: bool
    total_findings: int
    open_count: int
    in_progress_count: int
    remediated_count: int
    waived_count: int
    blocked_count: int
    deferred_count: int
    blocking_findings: tuple[UUID, ...]
    evidence_hash: str | None = None
    derived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CarveOutReadinessResult:
    """Result of carve-out readiness derivation.

    Anti-gaming: Derives whether regulatory carve-out requirements
    are ready for closing based on actual preparation status.

    Attributes:
        deal_id: M&A deal being assessed.
        ready: Whether carve-out is ready for closing.
        status: Current overall carve-out status.
        required_components: Components required for carve-out.
        ready_components: Components that are ready.
        missing_components: Components still needed.
        blocking_issues: Issues blocking readiness.
        regulatory_deadline: Deadline for carve-out completion.
        evidence_hash: Hash of evidence used for derivation.
        derived_at: When the derivation was computed.
    """

    deal_id: UUID
    ready: bool
    status: CarveOutStatus
    required_components: tuple[str, ...]
    ready_components: tuple[str, ...]
    missing_components: tuple[str, ...]
    blocking_issues: tuple[str, ...]
    regulatory_deadline: datetime | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ConditionSatisfactionResult:
    """Result of condition satisfaction status derivation.

    Anti-gaming: Derives the overall satisfaction status of closing
    conditions based on evidence, not user assertion.

    Attributes:
        deal_id: M&A deal being assessed.
        all_satisfied: Whether all conditions are satisfied or waived.
        total_conditions: Total number of closing conditions.
        satisfied_count: Number of satisfied conditions.
        waived_count: Number of waived conditions.
        pending_count: Number of pending conditions.
        failed_count: Number of failed conditions.
        conditions_by_type: Breakdown of conditions by type.
        blocking_conditions: IDs of conditions blocking closing.
        estimated_completion: Estimated date all conditions satisfied.
        evidence_hash: Hash of evidence used for derivation.
        derived_at: When the derivation was computed.
    """

    deal_id: UUID
    all_satisfied: bool
    total_conditions: int
    satisfied_count: int
    waived_count: int
    pending_count: int
    failed_count: int
    conditions_by_type: dict[ConditionType, ConditionSatisfactionStatus]
    blocking_conditions: tuple[UUID, ...]
    estimated_completion: datetime | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None
