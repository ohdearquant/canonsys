"""Corporate domain exceptions.

Exceptions for M&A compliance violations including clean team
requirements, conditional findings, carve-out readiness, and
condition satisfaction.

These are DERIVATION exceptions - they signal that anti-gaming
derivations have detected violations, not user assertion failures.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
    - SEC M&A disclosure rules
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import InvariantViolation

if TYPE_CHECKING:
    from uuid import UUID

    from .types import CarveOutStatus, CleanTeamReason

__all__ = [
    "CarveOutNotReadyError",
    "CleanTeamRequirementDerivedError",
    "ConditionsNotSatisfiedError",
    "CorporateViolation",
    "FindingsNotAddressedError",
]


class CorporateViolation(InvariantViolation):
    """Base exception for corporate/M&A compliance violations.

    Covers violations of M&A compliance requirements under:
    - Hart-Scott-Rodino Act (antitrust, gun-jumping)
    - Sherman Act Section 1 (information sharing)
    - FTC/DOJ Merger Guidelines (competition)
    - SEC M&A disclosure rules

    All corporate domain exceptions inherit from this.

    Invariant phrases:
    - clean_team_must_be_derived_required
    - findings_must_be_addressed
    - carve_out_must_be_ready
    - conditions_must_be_satisfied
    """

    default_regulation = "Hart-Scott-Rodino Act"
    default_message = "Corporate/M&A compliance requirement not satisfied"


class CleanTeamRequirementDerivedError(CorporateViolation):
    """Clean team is DERIVED as required based on data categories.

    Anti-gaming: This is raised based on DERIVED data categories,
    not user assertion. The system determines clean team requirement
    from the evidence by analyzing what types of data are present.

    Raised when: derive_clean_team_required detects sensitive data
    categories that mandate clean team access controls.

    Regulatory basis:
        - Hart-Scott-Rodino Act (antitrust, gun-jumping prevention)
        - Sherman Act Section 1 (competitively sensitive information)
        - FTC/DOJ Merger Guidelines (information barriers)

    Phrase: clean_team_must_be_derived_required
    """

    default_regulation = "Hart-Scott-Rodino Act"
    default_message = "Clean team required based on derived data categories"

    __slots__ = ("data_categories", "deal_id", "reason", "sensitivity_triggers")

    def __init__(
        self,
        deal_id: UUID,
        reason: CleanTeamReason,
        data_categories: tuple[str, ...],
        sensitivity_triggers: tuple[str, ...],
        *,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize clean team requirement derived error.

        Args:
            deal_id: UUID of the M&A deal.
            reason: Primary reason clean team is required.
            data_categories: All data categories found in deal.
            sensitivity_triggers: Specific categories that triggered requirement.
            message: Optional custom message.
            **kwargs: Additional arguments passed to parent.
        """
        self.deal_id = deal_id
        self.reason = reason
        self.data_categories = data_categories
        self.sensitivity_triggers = sensitivity_triggers

        msg = message or (
            f"Clean team required for deal {deal_id}: {reason.value}. "
            f"Sensitive data detected: {', '.join(sensitivity_triggers)}"
        )

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "deal_id": str(deal_id),
            "reason": reason.value,
            "data_categories": list(data_categories),
            "sensitivity_triggers": list(sensitivity_triggers),
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class FindingsNotAddressedError(CorporateViolation):
    """Conditional findings are not properly addressed.

    Anti-gaming: Derived from actual finding status records,
    not user assertion that findings are addressed.

    Raised when: derive_conditional_findings_addressed detects
    findings that are still open, blocked, or not properly resolved.

    Regulatory basis:
        - SEC M&A disclosure rules (material findings)
        - Fiduciary duty requirements (due diligence)
        - Due diligence best practices

    Phrase: findings_must_be_addressed
    """

    default_regulation = "SEC M&A Disclosure Rules"
    default_message = "Conditional findings not addressed"

    __slots__ = ("blocked_count", "blocking_findings", "deal_id", "open_count")

    def __init__(
        self,
        deal_id: UUID,
        open_count: int,
        blocked_count: int,
        blocking_findings: tuple[UUID, ...],
        *,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize findings not addressed error.

        Args:
            deal_id: UUID of the M&A deal.
            open_count: Number of findings still open.
            blocked_count: Number of findings that are blocked.
            blocking_findings: UUIDs of findings blocking deal progress.
            message: Optional custom message.
            **kwargs: Additional arguments passed to parent.
        """
        self.deal_id = deal_id
        self.open_count = open_count
        self.blocked_count = blocked_count
        self.blocking_findings = blocking_findings

        msg = message or (
            f"Conditional findings not addressed for deal {deal_id}: "
            f"{open_count} open, {blocked_count} blocked"
        )

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "deal_id": str(deal_id),
            "open_count": open_count,
            "blocked_count": blocked_count,
            "blocking_findings": [str(f) for f in blocking_findings],
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class CarveOutNotReadyError(CorporateViolation):
    """Regulatory carve-out is not ready for closing.

    Anti-gaming: Derived from actual carve-out preparation status,
    not user assertion that carve-out is ready.

    Raised when: derive_carve_out_readiness detects missing
    components or blocking issues in carve-out preparation.

    Regulatory basis:
        - FTC/DOJ divestiture requirements
        - Regulatory approval conditions
        - Competition law remedies

    Phrase: carve_out_must_be_ready
    """

    default_regulation = "FTC/DOJ Merger Guidelines"
    default_message = "Carve-out not ready for closing"

    __slots__ = ("blocking_issues", "deal_id", "missing_components", "status")

    def __init__(
        self,
        deal_id: UUID,
        status: CarveOutStatus,
        missing_components: tuple[str, ...],
        blocking_issues: tuple[str, ...],
        *,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize carve-out not ready error.

        Args:
            deal_id: UUID of the M&A deal.
            status: Current carve-out status.
            missing_components: Components required but not ready.
            blocking_issues: Issues blocking carve-out readiness.
            message: Optional custom message.
            **kwargs: Additional arguments passed to parent.
        """
        self.deal_id = deal_id
        self.status = status
        self.missing_components = missing_components
        self.blocking_issues = blocking_issues

        msg = message or (
            f"Carve-out not ready for deal {deal_id}: "
            f"status={status.value}, missing {len(missing_components)} components"
        )

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "deal_id": str(deal_id),
            "status": status.value,
            "missing_components": list(missing_components),
            "blocking_issues": list(blocking_issues),
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class ConditionsNotSatisfiedError(CorporateViolation):
    """Closing conditions are not satisfied.

    Anti-gaming: Derived from actual condition status records,
    not user assertion that conditions are met.

    Raised when: derive_condition_satisfaction_status detects
    conditions that are pending, failed, or not satisfied.

    Regulatory basis:
        - M&A contract law (closing conditions)
        - Shareholder protection requirements
        - Regulatory closing conditions

    Phrase: conditions_must_be_satisfied
    """

    default_regulation = "M&A Contract Law"
    default_message = "Closing conditions not satisfied"

    __slots__ = ("blocking_conditions", "deal_id", "failed_count", "pending_count")

    def __init__(
        self,
        deal_id: UUID,
        pending_count: int,
        failed_count: int,
        blocking_conditions: tuple[UUID, ...],
        *,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize conditions not satisfied error.

        Args:
            deal_id: UUID of the M&A deal.
            pending_count: Number of conditions still pending.
            failed_count: Number of conditions that have failed.
            blocking_conditions: UUIDs of conditions blocking closing.
            message: Optional custom message.
            **kwargs: Additional arguments passed to parent.
        """
        self.deal_id = deal_id
        self.pending_count = pending_count
        self.failed_count = failed_count
        self.blocking_conditions = blocking_conditions

        msg = message or (
            f"Closing conditions not satisfied for deal {deal_id}: "
            f"{pending_count} pending, {failed_count} failed"
        )

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "deal_id": str(deal_id),
            "pending_count": pending_count,
            "failed_count": failed_count,
            "blocking_conditions": [str(c) for c in blocking_conditions],
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)
