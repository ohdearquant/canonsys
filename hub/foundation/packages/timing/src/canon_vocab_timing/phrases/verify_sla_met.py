"""Verify service level agreement timing has been met.

Compliance Context:
    - SOC 2 CC7.4 (Incident response timeliness)
    - GDPR Article 33 (72-hour breach notification)
    - Industry SLAs (Support response times, etc.)
    - Contract obligations
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["SlaType", "VerifySlametSpecs", "verify_sla_met"]


class SlaType(StrEnum):
    """Types of SLAs."""

    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    FIRST_CONTACT = "first_contact"
    NOTIFICATION = "notification"
    ACKNOWLEDGMENT = "acknowledgment"


class VerifySlametSpecs(BaseModel):
    """Specs for verify SLA met phrase."""

    # inputs
    reference_id: UUID = Field(description="ID of the ticket/incident/request")
    sla_type: SlaType
    started_at: datetime
    completed_at: datetime | None = None
    sla_target_seconds: int = Field(gt=0, description="Target time in seconds")
    # outputs
    verified: bool = False
    met: bool = False
    actual_seconds: float = 0.0
    target_seconds: int = 0
    variance_seconds: float = 0.0
    variance_percent: float = 0.0
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifySlametSpecs),
    inputs={
        "reference_id",
        "sla_type",
        "started_at",
        "completed_at",
        "sla_target_seconds",
    },
    outputs={
        "verified",
        "reference_id",
        "sla_type",
        "met",
        "actual_seconds",
        "target_seconds",
        "variance_seconds",
        "variance_percent",
        "reason",
    },
)
async def verify_sla_met(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify that a service level agreement timing has been met.

    Compares the actual time taken against the SLA target.

    Args:
        options: Verification options - typed frozen dataclass
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with verified, reference_id, sla_type, met, actual_seconds,
        target_seconds, variance_seconds, variance_percent, reason

    Example:
        >>> result = await verify_sla_met(
        ...     {
        ...         "reference_id": ticket_id,
        ...         "sla_type": SlaType.RESPONSE_TIME,
        ...         "started_at": ticket_created,
        ...         "completed_at": first_response,
        ...         "sla_target_seconds": 4 * 3600,  # 4 hours
        ...     },
        ...     ctx,
        ... )
        >>> if not result["met"]:
        ...     log_sla_breach(ticket_id, result["variance_seconds"])
    """
    now = now_utc()
    reference_id: UUID = options.reference_id
    sla_type: SlaType = options.sla_type
    started_at: datetime = options.started_at
    completed_at: datetime | None = options.completed_at
    sla_target_seconds: int = options.sla_target_seconds

    # Use completion time or current time
    end_time = completed_at or now

    # Calculate actual time
    actual_seconds = (end_time - started_at).total_seconds()

    # Determine if SLA is met
    met = actual_seconds <= sla_target_seconds

    # Calculate variance
    variance_seconds = actual_seconds - sla_target_seconds
    variance_percent = (
        (variance_seconds / sla_target_seconds) * 100 if sla_target_seconds > 0 else 0.0
    )

    return {
        "verified": True,
        "reference_id": reference_id,
        "sla_type": sla_type,
        "met": met,
        "actual_seconds": actual_seconds,
        "target_seconds": sla_target_seconds,
        "variance_seconds": variance_seconds,
        "variance_percent": variance_percent,
        "reason": (
            None
            if met
            else f"SLA breached by {variance_seconds:.0f} seconds ({variance_percent:.1f}%)"
        ),
    }
