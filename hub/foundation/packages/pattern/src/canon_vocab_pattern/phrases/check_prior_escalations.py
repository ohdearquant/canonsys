"""Check prior privilege escalations for a subject.

Complete vertical slice:
- Wraps derive_prior_action_count for PRIVILEGE_ESCALATION action type
- Detects frequent privilege escalation requests
- Indicates access control abuse or improper permission assignment

Regulatory: Access control - detects privilege renewal abuse.

Compliance Context:
    - SOC 2 CC6.1: Logical access controls
    - Internal controls: Privilege management
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

__all__ = ["CheckPriorEscalationsSpecs", "check_prior_escalations"]


class CheckPriorEscalationsSpecs(BaseModel):
    """Specs for check prior escalations phrase."""

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
    Operable.from_structure(CheckPriorEscalationsSpecs),
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
async def check_prior_escalations(
    options: CheckPriorEscalationsSpecs,
    ctx: RequestContext,
) -> dict:
    """Check prior privilege escalations for a subject.

    Detects users who frequently request temporary privilege escalations.
    Multiple escalation requests may indicate access control abuse or
    improper permanent permission assignment.

    Regulatory: Access control - detects privilege renewal abuse.

    Args:
        options: Options with subject_id, days, threshold (default: 2)
        ctx: Request context for audit trail

    Returns:
        Dict with count, subject_id, action_type, lookback_days, window_start, window_end

    Example:
        >>> result = await check_prior_escalations(
        ...     CheckPriorEscalationsSpecs(subject_id=user_id, days=90), ctx
        ... )
        >>> if result["count"] >= 2:
        ...     # Consider permanent permission grant
    """
    count_options = DerivePriorActionCountSpecs(
        entity_id=options.subject_id,
        action_type="PRIVILEGE_ESCALATION",
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
