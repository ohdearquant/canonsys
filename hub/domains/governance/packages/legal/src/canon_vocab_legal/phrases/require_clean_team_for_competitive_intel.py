"""Require clean team membership for competitive intelligence access.

Raises CleanTeamRequiredError if user not on clean team.

Regulatory:
    - Hart-Scott-Rodino Act (gun-jumping)
    - Sherman Act Section 1 (information sharing)
    - FTC/DOJ merger guidelines
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import CleanTeamRequiredError
from .verify_clean_team_membership import verify_clean_team_membership

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireCleanTeamForCompetitiveIntelSpecs",
    "require_clean_team_for_competitive_intel",
]


class RequireCleanTeamForCompetitiveIntelSpecs(BaseModel):
    """Specs for require clean team for competitive intel phrase."""

    # inputs
    user_id: UUID
    deal_id: UUID
    # outputs
    satisfied: bool | None = None
    membership_id: UUID | None = None
    clearance_level: str | None = None
    reason: str | None = None


require_clean_team_for_competitive_intel_operable = Operable.from_structure(
    RequireCleanTeamForCompetitiveIntelSpecs
)


@canon_phrase(
    require_clean_team_for_competitive_intel_operable,
    inputs={"user_id", "deal_id"},
    outputs={
        "satisfied",
        "user_id",
        "deal_id",
        "membership_id",
        "clearance_level",
        "reason",
    },
)
async def require_clean_team_for_competitive_intel(
    options: RequireCleanTeamForCompetitiveIntelSpecs,
    ctx: RequestContext,
) -> dict:
    """Require clean team membership for competitive intelligence access.

    Args:
        options: Options containing user_id and deal_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfaction status if user is on clean team.

    Raises:
        CleanTeamRequiredError: If user is not an active clean team member.
    """
    user_id: UUID = options.user_id
    deal_id: UUID = options.deal_id

    verify_result = await verify_clean_team_membership(
        {"user_id": user_id, "deal_id": deal_id}, ctx
    )

    if not verify_result["verified"]:
        raise CleanTeamRequiredError(
            user_id=user_id,
            deal_id=deal_id,
            status=verify_result["status"],
            reason=verify_result["reason"] or "Clean team membership required",
        )

    return {
        "satisfied": True,
        "user_id": user_id,
        "deal_id": deal_id,
        "membership_id": verify_result["membership_id"],
        "clearance_level": verify_result["clearance_level"],
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireCleanTeamForCompetitiveIntelOptions = require_clean_team_for_competitive_intel.options_type
RequireCleanTeamForCompetitiveIntelResult = require_clean_team_for_competitive_intel.result_type
