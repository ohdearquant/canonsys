"""Corporate service - thin wrapper over M&A compliance phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

ANTI-GAMING ARCHITECTURE:

The Corporate domain implements DERIVATION phrases rather than verification
actions. Users cannot assert compliance status - the system derives it from evidence.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention
    - SEC M&A disclosure rules
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    derive_carve_out_readiness,
    derive_clean_team_required,
    derive_condition_satisfaction_status,
    derive_conditional_findings_addressed,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["CorporateService"]


class CorporateService(CanonService):
    """Corporate service - M&A compliance derivations.

    Thin wrapper that delegates to phrase functions.
    All phrases are DERIVATIONS (anti-gaming) - they examine evidence
    and derive requirements rather than accepting user assertions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="corporate")

    @action(skip_evidence=True)
    async def derive_clean_team_required(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive whether clean team is required based on data categories.

        Anti-gaming: Examines data categories present in the deal and
        determines whether clean team access controls are required.
        Users cannot assert 'clean team not required'.
        """
        return await derive_clean_team_required(payload, ctx)

    @action(skip_evidence=True)
    async def derive_conditional_findings_addressed(
        self, payload: dict, ctx: RequestContext
    ) -> dict:
        """Derive whether conditional findings have been addressed.

        Anti-gaming: Examines finding records and resolution evidence
        to determine if all conditions have been satisfied.
        """
        return await derive_conditional_findings_addressed(payload, ctx)

    @action(skip_evidence=True)
    async def derive_carve_out_readiness(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive carve-out readiness status from evidence.

        Anti-gaming: Examines separation activities and readiness
        evidence to derive current carve-out status.
        """
        return await derive_carve_out_readiness(payload, ctx)

    @action(skip_evidence=True)
    async def derive_condition_satisfaction_status(
        self, payload: dict, ctx: RequestContext
    ) -> dict:
        """Derive condition satisfaction status from evidence.

        Anti-gaming: Examines condition records and satisfaction
        evidence to derive current status of deal conditions.
        """
        return await derive_condition_satisfaction_status(payload, ctx)
