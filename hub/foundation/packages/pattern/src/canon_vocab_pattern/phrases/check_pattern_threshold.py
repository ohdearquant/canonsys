"""Check if prior action count meets or exceeds threshold.

Complete vertical slice:
- Derives prior action count
- Compares against threshold
- Returns boolean exceeded flag

Critical for policy gates where repeated actions require escalation.

The "five small exceptions = one material" principle:
Individual actions may seem minor, but repeated patterns
indicate systemic issues requiring escalation.

Compliance Context:
    - SOX Section 302: Management assessment of internal controls
    - SOC 2 CC5.2: Control activities - anti-gaming
    - Employment law: Progressive discipline patterns
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .derive_prior_action_count import derive_prior_action_count

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckPatternThresholdSpecs", "check_pattern_threshold"]


class CheckPatternThresholdSpecs(BaseModel):
    """Specs for check pattern threshold phrase."""

    # inputs
    entity_id: UUID
    action_type: str
    threshold: int
    lookback_days: int
    # outputs
    exceeded: bool | None = None
    count: int | None = None


@canon_phrase(
    Operable.from_structure(CheckPatternThresholdSpecs),
    inputs={"entity_id", "action_type", "threshold", "lookback_days"},
    outputs={
        "exceeded",
        "count",
        "threshold",
        "entity_id",
        "action_type",
        "lookback_days",
    },
)
async def check_pattern_threshold(
    options: CheckPatternThresholdSpecs,
    ctx: RequestContext,
) -> dict:
    """Check if prior action count meets or exceeds threshold.

    Convenience wrapper that combines derive_prior_action_count with
    threshold comparison for use in policy gates.

    Args:
        options: Options with entity_id, action_type, threshold, lookback_days
        ctx: Request context for tenant scope

    Returns:
        Dict with exceeded, count, threshold, entity_id, action_type, lookback_days

    Regulatory context:
        - SOX Section 302: Management assessment of internal controls
        - SOC 2 CC5.2: Control activities - anti-gaming
        - Employment law: Progressive discipline patterns
    """
    from .derive_prior_action_count import DerivePriorActionCountSpecs

    count_options = DerivePriorActionCountSpecs(
        entity_id=options.entity_id,
        action_type=options.action_type,
        lookback_days=options.lookback_days,
    )
    count_result = await derive_prior_action_count(count_options, ctx)

    count = count_result["count"]

    return {
        "exceeded": count >= options.threshold,
        "count": count,
        "threshold": options.threshold,
        "entity_id": options.entity_id,
        "action_type": options.action_type,
        "lookback_days": options.lookback_days,
    }
