"""Require active monitoring for a resource.

Gate check ensuring monitoring is active and healthy before
allowing sensitive operations.

Regulatory:
    - SOC 2 CC7.1 (Detection of anomalies)
    - ISO 27001 A.12.4 (Logging and monitoring)
    - PCI DSS v4.0 Req. 10 (Log monitoring)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import MonitoringStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireMonitoringActiveSpecs", "require_monitoring_active"]


class RequireMonitoringActiveSpecs(BaseModel):
    """Specs for require monitoring active phrase."""

    # inputs
    resource_id: UUID
    max_heartbeat_age_seconds: int = Field(default=300)
    # outputs
    satisfied: bool = False
    status: MonitoringStatus | None = None
    last_heartbeat: datetime | None = None
    monitor_id: UUID | None = None


require_monitoring_active_operable = Operable.from_structure(RequireMonitoringActiveSpecs)


@canon_phrase(
    require_monitoring_active_operable,
    inputs={"resource_id", "max_heartbeat_age_seconds"},
    outputs={"satisfied", "resource_id", "status", "last_heartbeat", "monitor_id"},
)
async def require_monitoring_active(
    options: RequireMonitoringActiveSpecs,
    ctx: RequestContext,
) -> dict:
    """Require active monitoring for a resource.

    Raises RequirementNotMetError if monitoring inactive or stale.

    Regulatory:
        - SOC 2 CC7.1 (Detection of anomalies)
        - ISO 27001 A.12.4 (Logging and monitoring)
        - PCI DSS v4.0 Req. 10 (Log monitoring)

    Args:
        options: Options containing resource_id and max_heartbeat_age_seconds
        ctx: Request context (tenant, actor)

    Returns:
        Dict indicating monitoring status.

    Raises:
        RequirementNotMetError: If monitoring is inactive or stale.
    """
    resource_id = options.resource_id
    max_heartbeat_age_seconds = options.max_heartbeat_age_seconds
    now = now_utc()

    row = await select_one(
        "resource_monitors",
        {
            "tenant_id": ctx.tenant_id,
            "resource_id": resource_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="monitoring_active",
            reason=f"No monitoring configured for resource {resource_id}",
        )

    status = MonitoringStatus(row["status"])
    last_heartbeat = row.get("last_heartbeat")

    if status != MonitoringStatus.ACTIVE:
        raise RequirementNotMetError(
            requirement="monitoring_active",
            reason=f"Monitoring not active: {status.value}",
        )

    # Check heartbeat freshness
    if last_heartbeat:
        age = (now - last_heartbeat).total_seconds()
        if age > max_heartbeat_age_seconds:
            raise RequirementNotMetError(
                requirement="monitoring_active",
                reason=f"Monitoring heartbeat stale ({age:.0f}s > {max_heartbeat_age_seconds}s)",
            )

    return {
        "satisfied": True,
        "resource_id": resource_id,
        "status": status,
        "last_heartbeat": last_heartbeat,
        "monitor_id": row.get("monitor_id"),
    }


# Export auto-generated types from the Phrase object
RequireMonitoringActiveOptions = require_monitoring_active.options_type
RequireMonitoringActiveResult = require_monitoring_active.result_type
