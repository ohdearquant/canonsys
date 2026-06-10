"""Legal service - thin wrapper over legal phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory context:
    - SOX Section 802 (Document destruction)
    - FRCP 37(e) (ESI preservation)
    - Hart-Scott-Rodino Act (M&A antitrust)
    - Attorney-Client Privilege
    - Administrative Procedure Act (due process)
    - Defend Trade Secrets Act (DTSA)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (  # Lock phrases; Require phrases; Verify phrases
    lock_criteria,
    require_appeal_exhausted,
    require_clean_team_for_competitive_intel,
    require_deletion_clearance,
    require_legal_review_complete,
    require_modification_clearance,
    require_nda_valid,
    require_proceedings_closed,
    verify_appeal_channel_available,
    verify_clean_team_membership,
    verify_nda_status,
    verify_privileged_review_complete,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["LegalService"]


class LegalService(CanonService):
    """Legal service - manages legal compliance operations.

    Thin wrapper that delegates to phrase functions.

    Operations include:
    - Criteria locking for workflow immutability
    - Deletion/modification clearance (legal hold checks)
    - Appeal and proceedings management
    - NDA status verification
    - Clean team requirements
    - Legal review completion
    - Privileged review verification
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="legal")

    # -------------------------------------------------------------------------
    # Lock Operations (mutations - emit evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="legal.lock_criteria")
    async def lock_criteria(self, payload: dict, ctx: RequestContext) -> dict:
        """Lock evaluation criteria for workflow immutability.

        Creates immutable record proving criteria were defined
        BEFORE any selection/evaluation occurred.
        """
        return await lock_criteria(payload, ctx)

    # -------------------------------------------------------------------------
    # Clearance Operations (mutations - emit evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="legal.deletion_clearance")
    async def require_deletion_clearance(self, payload: dict, ctx: RequestContext) -> dict:
        """Require deletion clearance (resource not under legal hold).

        Raises LegalHoldViolationError if resource is under legal hold.
        SOX 802, FRCP 37(e) compliance.
        """
        return await require_deletion_clearance(payload, ctx)

    @action(evidence_type="legal.modification_clearance")
    async def require_modification_clearance(self, payload: dict, ctx: RequestContext) -> dict:
        """Require modification clearance (resource not under legal hold).

        Raises LegalHoldViolationError if resource is under legal hold.
        SOX 802, FRCP 37(e) compliance.
        """
        return await require_modification_clearance(payload, ctx)

    # -------------------------------------------------------------------------
    # Requirement Operations (mutations - emit evidence)
    # -------------------------------------------------------------------------

    @action(evidence_type="legal.appeal_exhausted")
    async def require_appeal_exhausted(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that all appeals have been exhausted.

        Administrative Procedure Act compliance.
        """
        return await require_appeal_exhausted(payload, ctx)

    @action(evidence_type="legal.clean_team")
    async def require_clean_team_for_competitive_intel(
        self, payload: dict, ctx: RequestContext
    ) -> dict:
        """Require clean team for competitive intelligence access.

        Hart-Scott-Rodino Act compliance for M&A antitrust.
        """
        return await require_clean_team_for_competitive_intel(payload, ctx)

    @action(evidence_type="legal.legal_review")
    async def require_legal_review_complete(self, payload: dict, ctx: RequestContext) -> dict:
        """Require legal review completion before proceeding.

        Attorney-Client Privilege protection.
        """
        return await require_legal_review_complete(payload, ctx)

    @action(evidence_type="legal.nda_valid")
    async def require_nda_valid(self, payload: dict, ctx: RequestContext) -> dict:
        """Require valid NDA before information disclosure.

        Defend Trade Secrets Act (DTSA) compliance.
        """
        return await require_nda_valid(payload, ctx)

    @action(evidence_type="legal.proceedings_closed")
    async def require_proceedings_closed(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that legal proceedings are closed.

        Ensures no action taken during active litigation.
        """
        return await require_proceedings_closed(payload, ctx)

    # -------------------------------------------------------------------------
    # Verification Operations (reads - skip evidence)
    # -------------------------------------------------------------------------

    @action(skip_evidence=True)
    async def verify_appeal_channel_available(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that appeal channels are available (hot path).

        Due process verification for Administrative Procedure Act.
        """
        return await verify_appeal_channel_available(payload, ctx)

    @action(skip_evidence=True)
    async def verify_clean_team_membership(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify clean team membership status (hot path).

        Hart-Scott-Rodino Act compliance check.
        """
        return await verify_clean_team_membership(payload, ctx)

    @action(skip_evidence=True)
    async def verify_nda_status(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify NDA status between parties (hot path).

        Trade secret law (DTSA) compliance check.
        """
        return await verify_nda_status(payload, ctx)

    @action(skip_evidence=True)
    async def verify_privileged_review_complete(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify privileged review completion status (hot path).

        Attorney-Client Privilege verification.
        """
        return await verify_privileged_review_complete(payload, ctx)
