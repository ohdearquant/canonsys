"""Check DR test cooldown period.

Prevents excessive DR testing that could impact operations while
ensuring tests occur with appropriate frequency.

Regulatory Context:
    - SOC 2 CC7.5: Recovery procedure testing
    - ISO 27001 A.17.1.3: Business continuity testing
    - PCI DSS 12.10.2: Annual testing of incident response
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from .constants import DEFAULT_COOLDOWN_HOURS

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckDRTestCooldownSpecs", "check_dr_test_cooldown"]


class CheckDRTestCooldownSpecs(BaseModel):
    """Specs for DR test cooldown check phrase."""

    # inputs
    system_id: UUID
    cooldown_hours: int = DEFAULT_COOLDOWN_HOURS
    # outputs
    cooldown_active: bool | None = None
    last_test: datetime | None = None
    hours_remaining: int | None = None


@canon_phrase(
    Operable.from_structure(CheckDRTestCooldownSpecs),
    inputs={"system_id", "cooldown_hours"},
    outputs={"cooldown_active", "last_test", "cooldown_hours", "hours_remaining"},
)
async def check_dr_test_cooldown(
    options: CheckDRTestCooldownSpecs,
    ctx: RequestContext,
) -> dict:
    """Check if DR test cooldown period is active for a system.

    Prevents excessive DR testing that could impact operations while
    ensuring tests occur with appropriate frequency. Balances compliance
    requirements with operational stability.

    Regulatory Citations:
        - SOC 2 CC7.5: "Recovery procedures...are tested periodically
          to meet its objectives."
        - ISO 27001 A.17.1.3: "The organization shall verify the
          established and implemented information security continuity
          controls at regular intervals."
        - PCI DSS 12.10.2: "Review and test the plan, including all
          elements listed in Requirement 12.10.1, at least annually."

    Args:
        options: Check options (system_id, cooldown_hours)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with cooldown_active, last_test, cooldown_hours, hours_remaining

    Usage:
        Before initiating DR test:
        - If cooldown_active=True, test should be deferred
        - hours_remaining indicates when test can proceed
    """
    now = now_utc()
    system_id = options.system_id
    cooldown_hours = options.cooldown_hours
    _ = system_id  # Will query dr_test_history

    # Placeholder - would query actual DR test history
    last_test = None
    cooldown_active = False
    hours_remaining = None

    if last_test is not None:
        elapsed_seconds = (now - last_test).total_seconds()
        elapsed_hours = int(elapsed_seconds / 3600)

        if elapsed_hours < cooldown_hours:
            cooldown_active = True
            hours_remaining = cooldown_hours - elapsed_hours

    return {
        "cooldown_active": cooldown_active,
        "last_test": last_test,
        "cooldown_hours": cooldown_hours,
        "hours_remaining": hours_remaining,
    }
