"""Verify user is an active member of a clean team for M&A deal.

Returns verified=True if user has active clean team membership.

Regulatory:
    - Hart-Scott-Rodino Act (antitrust)
    - SEC M&A disclosure rules
    - Information barrier requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import CleanTeamStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyCleanTeamMembershipSpecs", "verify_clean_team_membership"]


class VerifyCleanTeamMembershipSpecs(BaseModel):
    """Specs for verify clean team membership phrase."""

    # inputs
    user_id: UUID
    deal_id: UUID
    # outputs
    verified: bool | None = None
    status: CleanTeamStatus | None = None
    membership_id: UUID | None = None
    joined_at: datetime | None = None
    clearance_level: str | None = None
    reason: str | None = None


verify_clean_team_membership_operable = Operable.from_structure(VerifyCleanTeamMembershipSpecs)


@canon_phrase(
    verify_clean_team_membership_operable,
    inputs={"user_id", "deal_id"},
    outputs={
        "verified",
        "user_id",
        "deal_id",
        "status",
        "membership_id",
        "joined_at",
        "clearance_level",
        "reason",
    },
)
async def verify_clean_team_membership(
    options: VerifyCleanTeamMembershipSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify user is an active member of a clean team for M&A deal.

    Args:
        options: Options containing user_id and deal_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with verification status and membership details.
    """
    user_id: UUID = options.user_id
    deal_id: UUID = options.deal_id

    row = await select_one(
        "clean_team_memberships",
        where={"user_id": user_id, "deal_id": deal_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "user_id": user_id,
            "deal_id": deal_id,
            "status": CleanTeamStatus.NOT_MEMBER,
            "membership_id": None,
            "joined_at": None,
            "clearance_level": None,
            "reason": "User not a clean team member",
        }

    status = CleanTeamStatus(row["status"])

    if status != CleanTeamStatus.ACTIVE:
        return {
            "verified": False,
            "user_id": user_id,
            "deal_id": deal_id,
            "status": status,
            "membership_id": row.get("membership_id"),
            "joined_at": row.get("joined_at"),
            "clearance_level": row.get("clearance_level"),
            "reason": f"Membership status: {status.value}",
        }

    return {
        "verified": True,
        "user_id": user_id,
        "deal_id": deal_id,
        "status": status,
        "membership_id": row.get("membership_id"),
        "joined_at": row.get("joined_at"),
        "clearance_level": row.get("clearance_level"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
VerifyCleanTeamMembershipOptions = verify_clean_team_membership.options_type
VerifyCleanTeamMembershipResult = verify_clean_team_membership.result_type
