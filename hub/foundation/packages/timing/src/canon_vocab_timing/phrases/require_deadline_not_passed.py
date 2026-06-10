"""Gate on deadline not having passed.

Compliance Context:
    - FCRA Section 1681i (Dispute response deadlines)
    - GDPR Article 12 (Response timing deadlines)
    - State employment laws (Various deadlines)
    - SOC 2 CC7.4 (Incident response timeliness)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireDeadlineNotPassedSpecs", "require_deadline_not_passed"]


class RequireDeadlineNotPassedSpecs(BaseModel):
    """Specs for require deadline not passed phrase."""

    # inputs
    reference_id: UUID = Field(description="ID of the entity/event with the deadline")
    deadline_at: datetime
    # outputs
    satisfied: bool = False
    is_overdue: bool = False
    seconds_until_deadline: float = 0.0
    seconds_overdue: float = 0.0
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireDeadlineNotPassedSpecs),
    inputs={"reference_id", "deadline_at"},
    outputs={
        "satisfied",
        "reference_id",
        "deadline_at",
        "is_overdue",
        "seconds_until_deadline",
        "seconds_overdue",
        "reason",
    },
)
async def require_deadline_not_passed(
    options,
    ctx: RequestContext,
) -> dict:
    """Gate: Require that a deadline has not passed.

    Blocks if the current time is past the specified deadline.
    Used for response requirements, filing deadlines, etc.

    Args:
        options: Gate options (reference_id, deadline_at) - typed frozen dataclass
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with satisfied=True, reference_id, deadline_at, is_overdue=False,
        seconds_until_deadline, seconds_overdue, reason

    Raises:
        RequirementNotMetError: If deadline has passed
    """
    now = now_utc()
    reference_id: UUID = options.reference_id
    deadline_at: datetime = options.deadline_at

    # Calculate time relative to deadline
    delta = (deadline_at - now).total_seconds()
    is_overdue = delta < 0

    # require_* must raise on failure
    if is_overdue:
        raise RequirementNotMetError(
            requirement="deadline_not_passed",
            reason=f"Deadline passed {abs(delta):.0f} seconds ago",
        )

    return {
        "satisfied": True,
        "reference_id": reference_id,
        "deadline_at": deadline_at,
        "is_overdue": False,
        "seconds_until_deadline": max(0.0, delta),
        "seconds_overdue": 0.0,
        "reason": None,
    }
