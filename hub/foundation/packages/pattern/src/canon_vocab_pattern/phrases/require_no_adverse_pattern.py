"""Require adverse pattern analysis shows no discriminatory pattern.

Complete vertical slice:
- Validates prior action count is below threshold
- Wraps check_pattern_threshold with gate semantics
- Raises PatternThresholdExceededError if threshold exceeded

Regulatory: SOX Section 302 - Management assessment of internal controls
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import PatternThresholdExceededError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "PatternThresholdExceededError",
    "RequireNoAdversePatternSpecs",
    "require_no_adverse_pattern",
]


class RequireNoAdversePatternSpecs(BaseModel):
    """Specs for require no adverse pattern phrase."""

    # inputs
    entity_id: UUID
    action_type: str
    threshold: int
    lookback_days: int
    # outputs
    satisfied: bool = False
    count: int | None = None


@canon_phrase(
    Operable.from_structure(RequireNoAdversePatternSpecs),
    inputs={"entity_id", "action_type", "threshold", "lookback_days"},
    outputs={
        "satisfied",
        "entity_id",
        "action_type",
        "count",
        "threshold",
        "lookback_days",
    },
)
async def require_no_adverse_pattern(
    options: RequireNoAdversePatternSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that adverse pattern analysis shows no discriminatory pattern.

    Gate pattern that enforces pattern threshold limits. Wraps
    check_pattern_threshold with raise-on-failure semantics.

    Args:
        options: Options containing entity_id, action_type, threshold, lookback_days.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if action count is below threshold.

    Raises:
        PatternThresholdExceededError: If pattern threshold is exceeded.

    Regulatory citations:
        - SOX Section 302: Management assessment of internal controls
        - SOC 2 CC5.2: Control activities - anti-gaming detection
        - BSA/AML: Suspicious activity pattern detection
        - EEOC Guidelines: Adverse impact pattern detection
    """
    from .check_pattern_threshold import (
        CheckPatternThresholdSpecs,
        check_pattern_threshold,
    )

    check_options = CheckPatternThresholdSpecs(
        entity_id=options.entity_id,
        action_type=options.action_type,
        threshold=options.threshold,
        lookback_days=options.lookback_days,
    )
    result = await check_pattern_threshold(check_options, ctx)

    if result["exceeded"]:
        raise PatternThresholdExceededError(
            entity_id=options.entity_id,
            action_type=options.action_type,
            count=result["count"],
            threshold=options.threshold,
            lookback_days=options.lookback_days,
        )

    return {
        "satisfied": True,
        "entity_id": options.entity_id,
        "action_type": options.action_type,
        "count": result["count"],
        "threshold": options.threshold,
        "lookback_days": options.lookback_days,
    }
