"""Derive degraded hours over last 30 days.

Aggregates all degradation events for a system to track cumulative
downtime against SLA commitments.

Regulatory Context:
    - SOC 2 CC7.3: Security event evaluation
    - ISO 27001 A.16.1.5: Incident analysis for future prevention
    - SLA Compliance: Monthly availability reporting
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .constants import DEFAULT_SLA_HOURS

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveDegradedHoursSpecs", "derive_degraded_hours_last_30d"]


class DeriveDegradedHoursSpecs(BaseModel):
    """Specs for degraded hours derivation phrase."""

    # inputs
    system_id: UUID
    sla_hours: int = DEFAULT_SLA_HOURS
    # outputs
    hours: int | None = None
    incidents: int | None = None
    is_above_sla: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveDegradedHoursSpecs),
    inputs={"system_id", "sla_hours"},
    outputs={"hours", "incidents", "is_above_sla", "sla_hours"},
)
async def derive_degraded_hours_last_30d(
    options: DeriveDegradedHoursSpecs,
    ctx: RequestContext,
) -> dict:
    """Count total degraded hours in the past 30 days.

    Aggregates all degradation events for a system to track cumulative
    downtime against SLA commitments. Used for compliance reporting
    and trend analysis.

    Regulatory Citations:
        - SOC 2 CC7.3: "The entity evaluates security events to determine
          whether they could or have resulted in a failure of the entity
          to meet its objectives."
        - ISO 27001 A.16.1.5: "Knowledge gained from analysing and resolving
          information security incidents shall be used to reduce the
          likelihood or impact of future incidents."
        - SLA Compliance: Required for monthly availability reporting
          and breach notification.

    Args:
        options: Derivation options (system_id, sla_hours)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with hours, incidents, is_above_sla, sla_hours

    SLA Context:
        4 hours over 30 days = ~99.5% availability
        8 hours over 30 days = ~99% availability
        72 hours over 30 days = ~90% availability
    """
    system_id = options.system_id
    sla_hours = options.sla_hours
    _ = system_id  # Will query incident_records

    # Placeholder - would aggregate actual degradation events
    # In production: SUM(duration) WHERE status='degraded' AND timestamp > now()-30d
    hours = 2  # Example value
    incidents = 1  # Example value

    is_above_sla = hours > sla_hours

    return {
        "hours": hours,
        "incidents": incidents,
        "is_above_sla": is_above_sla,
        "sla_hours": sla_hours,
    }
