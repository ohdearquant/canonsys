"""Check prior MFA exemptions for a subject.

Complete vertical slice:
- Wraps derive_prior_action_count for MFA_EXEMPTION action type
- Detects frequent MFA exemption requests
- May indicate device issues or social engineering attempts

Regulatory: Authentication - detects MFA exemption abuse.
Control: CS-018

Compliance Context:
    - SOC 2 CC6.1: Logical access controls
    - NIST 800-63B: Authentication requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .derive_prior_action_count import (
    DerivePriorActionCountSpecs,
    derive_prior_action_count,
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckPriorExemptionsSpecs", "check_prior_exemptions"]


class CheckPriorExemptionsSpecs(BaseModel):
    """Specs for check prior exemptions phrase."""

    # inputs
    subject_id: UUID
    days: int
    threshold: int = 2
    # outputs
    count: int | None = None
    action_type: str | None = None
    lookback_days: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(CheckPriorExemptionsSpecs),
    inputs={"subject_id", "days", "threshold"},
    outputs={
        "count",
        "subject_id",
        "action_type",
        "lookback_days",
        "window_start",
        "window_end",
    },
)
async def check_prior_exemptions(
    options: CheckPriorExemptionsSpecs,
    ctx: RequestContext,
) -> dict:
    """Check prior MFA exemptions for a subject.

    Detects users who frequently request MFA exemptions.
    Pattern may indicate device issues or social engineering attempts.

    Regulatory: Authentication - detects MFA exemption abuse.
    Control: CS-018

    Args:
        options: Options with subject_id, days, threshold (default: 2)
        ctx: Request context for audit trail

    Returns:
        Dict with count, subject_id, action_type, lookback_days, window_start, window_end

    Example:
        >>> result = await check_prior_exemptions(
        ...     CheckPriorExemptionsSpecs(subject_id=user_id, days=30), ctx
        ... )
        >>> if result["count"] >= 2:
        ...     # Require manager approval for next exemption
    """
    count_options = DerivePriorActionCountSpecs(
        entity_id=options.subject_id,
        action_type="MFA_EXEMPTION",
        lookback_days=options.days,
    )
    result = await derive_prior_action_count(count_options, ctx)

    return {
        "count": result["count"],
        "subject_id": options.subject_id,
        "action_type": result["action_type"],
        "lookback_days": result["lookback_days"],
        "window_start": result["window_start"],
        "window_end": result["window_end"],
    }
