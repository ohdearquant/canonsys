"""Gate on minimum time elapsed since an event.

Compliance Context:
    - FCRA Section 1681b(b)(3) (Waiting period requirements)
    - FCRA Section 1681m (Pre-adverse action timing)
    - WARN Act (60-day notice requirement)
    - GDPR Article 12 (Response timing)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireMinimumElapsedSpecs", "require_minimum_elapsed"]


class RequireMinimumElapsedSpecs(BaseModel):
    """Specs for require minimum elapsed phrase."""

    # inputs
    event_id: UUID
    event_occurred_at: datetime
    minimum_seconds: int = Field(gt=0, description="Minimum seconds that must elapse")
    # outputs
    satisfied: bool = False
    elapsed_seconds: float = 0.0
    remaining_seconds: float = 0.0
    earliest_allowed_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireMinimumElapsedSpecs),
    inputs={"event_id", "event_occurred_at", "minimum_seconds"},
    outputs={
        "satisfied",
        "event_id",
        "elapsed_seconds",
        "remaining_seconds",
        "earliest_allowed_at",
        "reason",
    },
)
async def require_minimum_elapsed(
    options,
    ctx: RequestContext,
) -> dict:
    """Gate: Require minimum time has elapsed since an event.

    Generic timing gate that blocks until a specified duration
    has passed since the triggering event.

    Args:
        options: Gate options (event_id, event_occurred_at, minimum_seconds)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with satisfied=True, event_id, elapsed_seconds, remaining_seconds=0,
        earliest_allowed_at, reason

    Raises:
        RequirementNotMetError: If minimum time has not elapsed
    """
    now = now_utc()
    event_id: UUID = options.event_id
    event_occurred_at: datetime = options.event_occurred_at
    minimum_seconds: int = options.minimum_seconds

    # Calculate elapsed time
    elapsed = (now - event_occurred_at).total_seconds()
    remaining = max(0.0, minimum_seconds - elapsed)
    earliest_allowed = event_occurred_at + timedelta(seconds=minimum_seconds)

    # require_* must raise on failure
    if elapsed < minimum_seconds:
        raise RequirementNotMetError(
            requirement="minimum_elapsed",
            reason=f"Must wait {remaining:.0f} more seconds",
        )

    return {
        "satisfied": True,
        "event_id": event_id,
        "elapsed_seconds": elapsed,
        "remaining_seconds": 0.0,
        "earliest_allowed_at": earliest_allowed,
        "reason": None,
    }
