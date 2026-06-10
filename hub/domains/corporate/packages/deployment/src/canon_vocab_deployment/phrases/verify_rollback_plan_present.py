"""Verify that a rollback plan exists for deployment.

Precondition check ensuring rollback plans are documented
before allowing deployments.

Regulatory:
    - SOC 2 CC8.1 (Change management)
    - ISO 27001 A.12.1.2 (Change management)
    - NIST SP 800-53 CM-3 (Configuration change control)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyRollbackPlanPresentSpecs", "verify_rollback_plan_present"]


class VerifyRollbackPlanPresentSpecs(BaseModel):
    """Specs for verify rollback plan present phrase."""

    # inputs
    deployment_id: UUID
    require_tested: bool = Field(default=False)
    # outputs
    verified: bool = False
    plan_id: UUID | None = None
    created_at: datetime | None = None
    tested: bool = False
    reason: str | None = None


verify_rollback_plan_present_operable = Operable.from_structure(VerifyRollbackPlanPresentSpecs)


@canon_phrase(
    verify_rollback_plan_present_operable,
    inputs={"deployment_id", "require_tested"},
    outputs={"verified", "deployment_id", "plan_id", "created_at", "tested", "reason"},
)
async def verify_rollback_plan_present(
    options: VerifyRollbackPlanPresentSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a rollback plan exists for deployment.

    Returns verified=True if rollback plan is documented.
    Optionally requires the plan to be tested.

    Regulatory:
        - SOC 2 CC8.1 (Change management)
        - ISO 27001 A.12.1.2 (Change management)
        - NIST SP 800-53 CM-3 (Configuration change control)

    Args:
        options: Options containing deployment_id and require_tested flag
        ctx: Request context (tenant, actor)

    Returns:
        Dict indicating plan status.
    """
    deployment_id = options.deployment_id
    require_tested = options.require_tested

    rows = await select(
        "deployment_rollback_plans",
        where={
            "tenant_id": ctx.tenant_id,
            "deployment_id": deployment_id,
        },
        order_by="created_at DESC",
        limit=1,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    row = rows[0] if rows else None

    if not row:
        return {
            "verified": False,
            "deployment_id": deployment_id,
            "reason": "No rollback plan found",
        }

    tested = row.get("tested", False)

    if require_tested and not tested:
        return {
            "verified": False,
            "deployment_id": deployment_id,
            "plan_id": row.get("plan_id"),
            "created_at": row.get("created_at"),
            "tested": False,
            "reason": "Rollback plan exists but has not been tested",
        }

    return {
        "verified": True,
        "deployment_id": deployment_id,
        "plan_id": row.get("plan_id"),
        "created_at": row.get("created_at"),
        "tested": tested,
    }


# Export auto-generated types from the Phrase object
VerifyRollbackPlanPresentOptions = verify_rollback_plan_present.options_type
VerifyRollbackPlanPresentResult = verify_rollback_plan_present.result_type
