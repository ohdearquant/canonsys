"""Require retention compliance gate.

Raises RetentionComplianceRequiredError if data is being retained beyond
schedule. Note: Returns success if under legal hold (retention allowed).

Regulatory context:
    - GDPR Art. 5(1)(e): Storage limitation
    - CCPA Section 1798.105: Right to deletion
    - SOX Section 802: Document retention
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import RetentionComplianceRequiredError
from ..types import RetentionStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireRetentionComplianceSpecs", "require_retention_compliance"]


class RequireRetentionComplianceSpecs(BaseModel):
    """Specs for require retention compliance phrase."""

    # inputs
    resource_id: UUID
    # outputs
    status: RetentionStatus | None = None
    retention_end: datetime | None = None


require_retention_compliance_operable = Operable.from_structure(RequireRetentionComplianceSpecs)


@canon_phrase(
    require_retention_compliance_operable,
    inputs={"resource_id"},
    outputs={"resource_id", "status", "retention_end"},
)
async def require_retention_compliance(
    options: RequireRetentionComplianceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that data is not retained beyond scheduled retention period.

    Raises RetentionComplianceRequiredError if data is being retained beyond
    schedule. Note: Returns success if under legal hold (retention allowed).

    Args:
        options: Retention options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, status, retention_end

    Raises:
        RetentionComplianceRequiredError: If retention is beyond schedule.

    Regulatory:
        - GDPR Art. 5(1)(e): Storage limitation
        - CCPA Section 1798.105: Right to deletion
        - SOX Section 802: Document retention
    """
    resource_id = options.resource_id

    row = await select_one(
        "data_retention_schedules",
        where={"resource_id": resource_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        return {
            "resource_id": resource_id,
            "status": RetentionStatus.EXEMPT,
            "retention_end": None,
        }

    # Legal hold overrides retention schedule
    if row.get("legal_hold_active"):
        return {
            "resource_id": resource_id,
            "status": RetentionStatus.UNDER_HOLD,
            "retention_end": row.get("retention_end_date"),
        }

    retention_end = row.get("retention_end_date")
    now = datetime.now(UTC)

    if retention_end and now > retention_end:
        days_beyond = (now - retention_end).days
        raise RetentionComplianceRequiredError(
            resource_id=resource_id,
            retention_end=retention_end,
            days_beyond=days_beyond,
        )

    return {
        "resource_id": resource_id,
        "status": RetentionStatus.WITHIN_SCHEDULE,
        "retention_end": retention_end,
    }


# Export auto-generated types from the Phrase object
RequireRetentionComplianceOptions = require_retention_compliance.options_type
RequireRetentionComplianceResult = require_retention_compliance.result_type
