"""Verify that an appeal/opt-out channel is available for decision type.

Generic appeal channel check for any AI/automated decision domain.
Ensures subjects have recourse for automated decisions.

Regulatory:
    - CO SB24-205 Section 6-1-1704 (Consumer appeal rights)
    - GDPR Art. 22 (Right not to be subject to automated decision)
    - EU AI Act Art. 14 (Human oversight)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import AppealChannelType

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyAppealChannelAvailableSpecs", "verify_appeal_channel_available"]


class VerifyAppealChannelAvailableSpecs(BaseModel):
    """Specs for verify appeal channel available phrase."""

    # inputs
    decision_type: str
    channel_type: AppealChannelType
    # outputs
    verified: bool | None = None
    channel_id: UUID | None = None
    channel_url: str | None = None
    contact_info: str | None = None
    reason: str | None = None


verify_appeal_channel_available_operable = Operable.from_structure(
    VerifyAppealChannelAvailableSpecs
)


@canon_phrase(
    verify_appeal_channel_available_operable,
    inputs={"decision_type", "channel_type"},
    outputs={
        "verified",
        "decision_type",
        "channel_type",
        "channel_id",
        "channel_url",
        "contact_info",
        "reason",
    },
)
async def verify_appeal_channel_available(
    options: VerifyAppealChannelAvailableSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that an appeal/opt-out channel is available for decision type.

    Args:
        options: Options containing decision_type and channel_type
        ctx: Request context (tenant, actor)

    Returns:
        dict with verification status and channel details.
    """
    decision_type: str = options.decision_type
    channel_type: AppealChannelType = options.channel_type

    row = await select_one(
        "appeal_channels",
        where={
            "decision_type": decision_type,
            "channel_type": channel_type.value,
            "is_active": True,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "decision_type": decision_type,
            "channel_type": channel_type,
            "channel_id": None,
            "channel_url": None,
            "contact_info": None,
            "reason": f"No active {channel_type.value} channel for {decision_type}",
        }

    return {
        "verified": True,
        "decision_type": decision_type,
        "channel_type": channel_type,
        "channel_id": row["channel_id"],
        "channel_url": row.get("channel_url"),
        "contact_info": row.get("contact_info"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
VerifyAppealChannelAvailableOptions = verify_appeal_channel_available.options_type
VerifyAppealChannelAvailableResult = verify_appeal_channel_available.result_type
