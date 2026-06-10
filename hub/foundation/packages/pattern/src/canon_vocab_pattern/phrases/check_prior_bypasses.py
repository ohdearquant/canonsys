"""Check prior application bypasses for a subject on a specific app.

Complete vertical slice:
- Wraps derive_prior_action_count for APP_BYPASS:{app_id} action type
- App-scoped pattern detection
- Detects frequent security control bypasses for specific applications

Regulatory: Application security - detects bypass abuse.
Control: CS-019

Compliance Context:
    - SOC 2 CC6.1: Logical access controls
    - Application security: Per-app bypass monitoring
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

__all__ = ["CheckPriorBypassesSpecs", "check_prior_bypasses"]


class CheckPriorBypassesSpecs(BaseModel):
    """Specs for check prior bypasses phrase."""

    # inputs
    subject_id: UUID
    app_id: UUID
    days: int
    threshold: int = 2
    # outputs
    count: int | None = None
    action_type: str | None = None
    lookback_days: int | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


@canon_phrase(
    Operable.from_structure(CheckPriorBypassesSpecs),
    inputs={"subject_id", "app_id", "days", "threshold"},
    outputs={
        "count",
        "subject_id",
        "app_id",
        "action_type",
        "lookback_days",
        "window_start",
        "window_end",
    },
)
async def check_prior_bypasses(
    options: CheckPriorBypassesSpecs,
    ctx: RequestContext,
) -> dict:
    """Check prior application bypasses for a subject on a specific app.

    Detects users who frequently bypass security controls for a specific
    application. Pattern may indicate improper access needs or policy abuse.

    Regulatory: Application security - detects bypass abuse.
    Control: CS-019

    Args:
        options: Options with subject_id, app_id, days, threshold (default: 2)
        ctx: Request context for audit trail

    Returns:
        Dict with count, subject_id, app_id, action_type, lookback_days, window_start, window_end

    Note:
        The app_id is encoded in the action_type to scope the pattern
        detection to a specific application. This prevents cross-app
        bypass patterns from triggering false positives.

    Example:
        >>> result = await check_prior_bypasses(
        ...     CheckPriorBypassesSpecs(
        ...         subject_id=user_id, app_id=salesforce_app_id, days=30
        ...     ),
        ...     ctx,
        ... )
        >>> if result["count"] >= 2:
        ...     # Require security review for app access
    """
    # Encode app_id in action_type for app-scoped pattern detection
    action_type = f"APP_BYPASS:{options.app_id}"

    count_options = DerivePriorActionCountSpecs(
        entity_id=options.subject_id,
        action_type=action_type,
        lookback_days=options.days,
    )
    result = await derive_prior_action_count(count_options, ctx)

    return {
        "count": result["count"],
        "subject_id": options.subject_id,
        "app_id": options.app_id,
        "action_type": result["action_type"],
        "lookback_days": result["lookback_days"],
        "window_start": result["window_start"],
        "window_end": result["window_end"],
    }
