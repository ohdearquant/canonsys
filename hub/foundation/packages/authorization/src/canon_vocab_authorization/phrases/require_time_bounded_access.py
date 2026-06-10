"""Require time-bounded access with expiry verification.

Complete vertical slice:
- Verifies access grant exists and has not expired
- Checks access is within valid time window
- Raises RequirementNotMetError if outside bounds

Regulatory:
    - SOC 2 CC6.1 (Logical access controls - time restrictions)
    - ISO 27001 A.9.4.1 (Information access restriction)
    - NIST SP 800-53 AC-2 (Account management - time-based)
    - PCI DSS 7.1 (Limit access to system components)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireTimeBoundedAccessSpecs", "require_time_bounded_access"]


class RequireTimeBoundedAccessSpecs(BaseModel):
    """Specs for require time bounded access phrase."""

    # inputs
    access_grant_id: UUID
    resource_id: UUID | None = None
    actor_id: UUID | None = None
    grace_period_minutes: int = 0  # Allow early access by this many minutes
    # outputs (defaults required for instantiation with inputs only)
    valid: bool = False
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    checked_at: datetime | None = None
    remaining_minutes: int | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireTimeBoundedAccessSpecs),
    inputs={"access_grant_id", "resource_id", "actor_id", "grace_period_minutes"},
    outputs={
        "valid",
        "access_grant_id",
        "starts_at",
        "expires_at",
        "checked_at",
        "remaining_minutes",
        "reason",
    },
)
async def require_time_bounded_access(
    options: RequireTimeBoundedAccessSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that access is within valid time bounds.

    Verifies that an access grant is currently valid based on its
    time window. Access must be:
    - After starts_at (with optional grace period)
    - Before expires_at

    This supports JIT (Just-In-Time) access patterns where access
    is granted for limited time windows.

    Args:
        options: Options containing access_grant_id and optional filters
        ctx: Request context with connection

    Returns:
        Dict with validity status and time metadata.

    Raises:
        RequirementNotMetError: If access is outside valid time bounds
    """
    now = now_utc()
    access_grant_id: UUID = options.access_grant_id
    grace_period = timedelta(minutes=options.grace_period_minutes)

    # Query access grant
    query = """
        SELECT id, actor_id, resource_id, starts_at, expires_at, is_revoked
        FROM access_grants
        WHERE id = $1
    """
    row = await ctx.conn.fetchrow(query, access_grant_id)

    if not row:
        raise RequirementNotMetError(
            requirement="time_bounded_access",
            reason=f"Access grant {access_grant_id} not found",
        )

    # Check if revoked
    if row["is_revoked"]:
        raise RequirementNotMetError(
            requirement="time_bounded_access",
            reason=f"Access grant {access_grant_id} has been revoked",
        )

    starts_at: datetime | None = row["starts_at"]
    expires_at: datetime | None = row["expires_at"]

    # Check time bounds
    effective_start = starts_at - grace_period if starts_at else None

    if effective_start and now < effective_start:
        raise RequirementNotMetError(
            requirement="time_bounded_access",
            reason=f"Access not yet valid. Starts at {starts_at}",
        )

    if expires_at and now > expires_at:
        raise RequirementNotMetError(
            requirement="time_bounded_access",
            reason=f"Access has expired at {expires_at}",
        )

    # Calculate remaining time
    remaining_minutes: int | None = None
    if expires_at:
        remaining = expires_at - now
        remaining_minutes = int(remaining.total_seconds() / 60)

    return {
        "valid": True,
        "access_grant_id": access_grant_id,
        "starts_at": starts_at,
        "expires_at": expires_at,
        "checked_at": now,
        "remaining_minutes": remaining_minutes,
        "reason": None,
    }
