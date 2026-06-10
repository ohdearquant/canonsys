"""Count manager posting bypasses in last 12 months.

Complete vertical slice:
- Wraps check_pattern_threshold for POSTING_BYPASS action type
- Fixed 12-month lookback window
- Detects systematic posting requirement bypass

Regulatory: Employment law - prevents systematic posting bypass abuse.

Compliance Context:
    - Employment law: Job posting requirements
    - Internal controls: Manager override monitoring
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .check_pattern_threshold import CheckPatternThresholdSpecs, check_pattern_threshold

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveManagerBypassCount12mSpecs", "derive_manager_bypass_count_12m"]

# Constants for lookback periods
TWELVE_MONTHS_DAYS = 365


class DeriveManagerBypassCount12mSpecs(BaseModel):
    """Specs for derive manager bypass count 12m phrase."""

    # inputs
    manager_id: UUID
    threshold: int = 3
    # outputs
    count: int | None = None
    period_months: int | None = None
    exceeds_threshold: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveManagerBypassCount12mSpecs),
    inputs={"manager_id", "threshold"},
    outputs={"manager_id", "count", "period_months", "exceeds_threshold", "threshold"},
)
async def derive_manager_bypass_count_12m(
    options: DeriveManagerBypassCount12mSpecs,
    ctx: RequestContext,
) -> dict:
    """Count manager posting bypasses in last 12 months.

    Detects when managers systematically bypass job posting requirements.
    Three or more bypasses in 12 months triggers review escalation.

    Regulatory: Employment law - prevents systematic posting bypass abuse.

    Args:
        options: Options with manager_id, threshold (default: 3)
        ctx: Request context for audit trail

    Returns:
        Dict with manager_id, count, period_months, exceeds_threshold, threshold

    Example:
        >>> result = await derive_manager_bypass_count_12m(
        ...     DeriveManagerBypassCount12mSpecs(manager_id=manager_id), ctx
        ... )
        >>> if result["exceeds_threshold"]:
        ...     # Require HR review for future bypass requests
    """
    threshold_options = CheckPatternThresholdSpecs(
        entity_id=options.manager_id,
        action_type="POSTING_BYPASS",
        threshold=options.threshold,
        lookback_days=TWELVE_MONTHS_DAYS,
    )
    threshold_result = await check_pattern_threshold(threshold_options, ctx)

    return {
        "manager_id": options.manager_id,
        "count": threshold_result["count"],
        "period_months": 12,
        "exceeds_threshold": threshold_result["exceeded"],
        "threshold": options.threshold,
    }
