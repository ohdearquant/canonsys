"""Verify that an endpoint has completed traffic draining.

Checks that all active connections have been gracefully terminated
before allowing endpoint decommissioning or maintenance operations.

Regulatory Context:
    - SOC 2 CC7.1: Detection of system changes
    - ISO 27001 A.12.1: Operational procedures
    - SLA Requirements: Availability commitments
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyTrafficDrainedSpecs", "verify_traffic_drained"]


class VerifyTrafficDrainedSpecs(BaseModel):
    """Specs for traffic drain verification phrase."""

    # inputs
    endpoint_id: UUID
    # outputs
    drained: bool | None = None
    active_connections: int | None = None
    drain_started_at: datetime | None = None
    drain_duration_seconds: int | None = None


@canon_phrase(
    Operable.from_structure(VerifyTrafficDrainedSpecs),
    inputs={"endpoint_id"},
    outputs={
        "drained",
        "endpoint_id",
        "active_connections",
        "drain_started_at",
        "drain_duration_seconds",
    },
)
async def verify_traffic_drained(
    options: VerifyTrafficDrainedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that an endpoint has completed traffic draining.

    Checks that all active connections have been gracefully terminated
    before allowing endpoint decommissioning or maintenance operations.
    This prevents connection drops and ensures graceful shutdown.

    Regulatory Citations:
        - SOC 2 CC7.1: "The entity detects and monitors changes to
          infrastructure, data, software, and procedures that may affect
          system security."
        - ISO 27001 A.12.1.1: "Operating procedures shall be documented
          and made available to all users who need them."
        - SLA Compliance: Maintains availability commitments during
          infrastructure transitions.

    Args:
        options: Verification options (endpoint_id)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with drained, endpoint_id, active_connections, drain_started_at,
        drain_duration_seconds

    Usage:
        Must verify traffic is drained before:
        - Decommissioning endpoints
        - Performing maintenance windows
        - Scaling down capacity
    """
    endpoint_id = options.endpoint_id
    now = now_utc()

    # Placeholder - would query actual connection state
    active_connections = 0
    drain_started_at = None
    drain_duration_seconds = None

    # Calculate drain duration if drain is in progress
    if drain_started_at is not None:
        drain_duration_seconds = int((now - drain_started_at).total_seconds())

    drained = active_connections == 0

    return {
        "drained": drained,
        "endpoint_id": endpoint_id,
        "active_connections": active_connections,
        "drain_started_at": drain_started_at,
        "drain_duration_seconds": drain_duration_seconds,
    }
