"""Legal domain exceptions.

These exceptions are raised by legal features when requirements are not met.
All inherit from LegalViolation (the domain's base exception).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import InvariantViolation

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

    from .types import AppealStatus, CleanTeamStatus, NDAStatus, ProceedingsStatus

__all__ = [
    # Requirement exceptions
    "AppealNotExhaustedError",
    "CleanTeamRequiredError",
    # Hold exceptions
    "LegalHoldViolationError",
    "LegalReviewRequiredError",
    # Base
    "LegalViolation",
    "NDARequiredError",
    "ProceedingsNotClosedError",
]


class LegalViolation(InvariantViolation):
    """Legal-related invariant violations.

    Covers violations of legal requirements under:
    - SOX Section 802 (Document destruction)
    - FRCP 37(e) (ESI preservation)
    - Hart-Scott-Rodino Act (M&A antitrust)
    - Attorney-Client Privilege
    - Administrative Procedure Act (due process)

    Invariant phrases:
    - appeal_must_be_exhausted
    - clean_team_must_be_verified
    - legal_review_must_be_complete
    - nda_must_be_valid
    - proceedings_must_be_closed
    """

    default_regulation = "SOX Section 802"
    default_message = "Legal requirement not satisfied"


class AppealNotExhaustedError(LegalViolation):
    """Appeal process is not exhausted.

    Raised when: require_appeal_exhausted finds appeals still pending or available.

    Regulatory basis:
    - Administrative Procedure Act (APA)
    - Due process requirements
    - Employment appeal procedures

    Phrase: appeal_must_be_exhausted
    """

    default_regulation = "Administrative Procedure Act"
    default_message = "Appeals must be exhausted before final action"

    __slots__ = ("appeal_deadline", "decision_id", "status")

    def __init__(
        self,
        decision_id: UUID,
        status: AppealStatus | None,
        *,
        appeal_deadline: datetime | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize appeal not exhausted error.

        Args:
            decision_id: UUID of the decision being appealed.
            status: Current appeal status (or None if no record found).
            appeal_deadline: Deadline for filing appeals (if any).
            reason: Additional context about why appeals are not exhausted.
            **kwargs: Additional arguments passed to parent.
        """
        self.decision_id = decision_id
        self.status = status
        self.appeal_deadline = appeal_deadline

        msg = reason or f"Appeals not exhausted for decision {decision_id}"
        if status:
            msg = f"Appeal status is {status.value} for decision {decision_id}"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "decision_id": str(decision_id),
            "status": status.value if status else None,
            "appeal_deadline": appeal_deadline.isoformat() if appeal_deadline else None,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class CleanTeamRequiredError(LegalViolation):
    """Clean team membership required but not verified.

    Raised when: require_clean_team_for_competitive_intel finds user not on clean team.

    Regulatory basis:
    - Hart-Scott-Rodino Act (gun-jumping prevention)
    - Sherman Act Section 1 (information sharing)
    - FTC/DOJ merger guidelines

    Phrase: clean_team_must_be_verified
    """

    default_regulation = "Hart-Scott-Rodino Act"
    default_message = "Clean team membership required for competitive intel access"

    __slots__ = ("deal_id", "status", "user_id")

    def __init__(
        self,
        user_id: UUID,
        deal_id: UUID,
        status: CleanTeamStatus,
        *,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize clean team required error.

        Args:
            user_id: UUID of the user attempting access.
            deal_id: UUID of the M&A deal.
            status: Current clean team membership status.
            reason: Additional context about the failure.
            **kwargs: Additional arguments passed to parent.
        """
        self.user_id = user_id
        self.deal_id = deal_id
        self.status = status

        msg = reason or f"User {user_id} not on clean team for deal {deal_id}"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "user_id": str(user_id),
            "deal_id": str(deal_id),
            "status": status.value,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class LegalReviewRequiredError(LegalViolation):
    """Legal review required but not complete.

    Raised when: require_legal_review_complete finds no completed review.

    Regulatory basis:
    - Attorney-Client Privilege (evidence preservation)
    - FRCP 26(b)(3) (Work product doctrine)
    - SOX Section 802 (Document retention)

    Phrase: legal_review_must_be_complete
    """

    default_regulation = "Attorney-Client Privilege"
    default_message = "Legal review required before proceeding"

    __slots__ = ("matter_id",)

    def __init__(
        self,
        matter_id: UUID,
        *,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize legal review required error.

        Args:
            matter_id: UUID of the legal matter.
            reason: Additional context about the failure.
            **kwargs: Additional arguments passed to parent.
        """
        self.matter_id = matter_id

        msg = reason or f"Legal review required for matter {matter_id}"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {"matter_id": str(matter_id)}
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class NDARequiredError(LegalViolation):
    """Valid NDA required but not found.

    Raised when: require_nda_valid finds no active NDA.

    Regulatory basis:
    - Trade secret law (DTSA)
    - M&A confidentiality requirements
    - Due diligence best practices

    Phrase: nda_must_be_valid
    """

    default_regulation = "Defend Trade Secrets Act (DTSA)"
    default_message = "Valid NDA required before information sharing"

    __slots__ = ("counterparty_id", "party_id", "status")

    def __init__(
        self,
        party_id: UUID,
        *,
        counterparty_id: UUID | None = None,
        status: NDAStatus | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize NDA required error.

        Args:
            party_id: UUID of the primary party.
            counterparty_id: UUID of the counterparty (if specified).
            status: Current NDA status.
            reason: Additional context about the failure.
            **kwargs: Additional arguments passed to parent.
        """
        self.party_id = party_id
        self.counterparty_id = counterparty_id
        self.status = status

        msg = reason or f"Valid NDA required for party {party_id}"
        if counterparty_id:
            msg = f"Valid NDA required between {party_id} and {counterparty_id}"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "party_id": str(party_id),
            "counterparty_id": str(counterparty_id) if counterparty_id else None,
            "status": status.value if status else None,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class ProceedingsNotClosedError(LegalViolation):
    """Legal proceedings must be closed but are still open.

    Raised when: require_proceedings_closed finds proceedings still open or stayed.

    Regulatory basis:
    - FRCP (Federal Rules of Civil Procedure)
    - Court record sealing requirements
    - Litigation hold release requirements

    Phrase: proceedings_must_be_closed
    """

    default_regulation = "FRCP"
    default_message = "Legal proceedings must be closed before action"

    __slots__ = ("matter_id", "status")

    def __init__(
        self,
        matter_id: UUID,
        status: ProceedingsStatus | None,
        *,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize proceedings not closed error.

        Args:
            matter_id: UUID of the legal matter.
            status: Current proceedings status.
            reason: Additional context about the failure.
            **kwargs: Additional arguments passed to parent.
        """
        self.matter_id = matter_id
        self.status = status

        msg = reason or f"Proceedings not closed for matter {matter_id}"
        if status:
            msg = f"Proceedings still {status.value} for matter {matter_id}"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "matter_id": str(matter_id),
            "status": status.value if status else None,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)


class LegalHoldViolationError(LegalViolation):
    """Attempted action on resource under legal hold.

    Raised when: require_deletion_clearance or require_modification_clearance
    blocks an action on a resource that is under legal hold.

    Regulatory basis:
    - SOX Section 802 (Prohibits destruction of evidence)
    - FRCP 37(e) (ESI preservation duty)
    - 18 U.S.C. Section 1519 (Obstruction)

    Phrase: legal_hold_must_not_block
    """

    default_regulation = "SOX Section 802"
    default_message = "Resource is under legal hold"

    __slots__ = ("action_type", "hold_id", "hold_type", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        action_type: str,
        *,
        hold_id: UUID | None = None,
        hold_type: str | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize legal hold violation error.

        Args:
            resource_id: UUID of the resource under hold.
            action_type: Type of action that was blocked (deletion, modification).
            hold_id: UUID of the blocking legal hold.
            hold_type: Type of hold (litigation, regulatory, etc.).
            reason: Additional context about the violation.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.hold_id = hold_id
        self.hold_type = hold_type
        self.action_type = action_type

        msg = reason or f"Cannot {action_type} resource {resource_id} - under legal hold"
        if hold_type:
            msg = f"Cannot {action_type} resource {resource_id} - under {hold_type} hold"

        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "action_type": action_type,
            "hold_id": str(hold_id) if hold_id else None,
            "hold_type": hold_type,
        }
        merged_context = {**base_context, **extra_context}

        super().__init__(msg, context=merged_context, **kwargs)
