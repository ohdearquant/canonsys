"""Require deployment to have proper approval.

Gate check ensuring deployments have proper approval chain
before proceeding to production.

Regulatory:
    - SOX Section 404 (Internal controls)
    - SOC 2 CC8.1 (Change management)
    - ISO 27001 A.12.1.2 (Change management)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import DeploymentApprovalRequiredError
from ..types import ApprovalStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireDeploymentApprovalSpecs", "require_deployment_approval"]


class RequireDeploymentApprovalSpecs(BaseModel):
    """Specs for require deployment approval phrase."""

    # inputs
    deployment_id: UUID
    # outputs
    approval_status: ApprovalStatus | None = None
    approver_id: UUID | None = None
    approved_at: datetime | None = None


require_deployment_approval_operable = Operable.from_structure(RequireDeploymentApprovalSpecs)


@canon_phrase(
    require_deployment_approval_operable,
    inputs={"deployment_id"},
    outputs={"deployment_id", "approval_status", "approver_id", "approved_at"},
)
async def require_deployment_approval(
    options: RequireDeploymentApprovalSpecs,
    ctx: RequestContext,
) -> dict:
    """Require deployment to have proper approval.

    Raises DeploymentApprovalRequiredError if deployment lacks approved status.

    Regulatory:
        - SOX Section 404 (Internal controls)
        - SOC 2 CC8.1 (Change management)
        - ISO 27001 A.12.1.2 (Change management)

    Args:
        options: Options containing deployment_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with approval details if deployment is approved.

    Raises:
        DeploymentApprovalRequiredError: If deployment lacks approval.
    """
    deployment_id = options.deployment_id

    rows = await select(
        "deployment_approvals",
        where={
            "tenant_id": ctx.tenant_id,
            "deployment_id": deployment_id,
        },
        order_by="approved_at DESC",
        limit=1,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    row = rows[0] if rows else None

    if not row:
        raise DeploymentApprovalRequiredError(
            deployment_id=deployment_id,
            approval_status=ApprovalStatus.PENDING,
            context={"reason": "No approval record found"},
        )

    status = ApprovalStatus(row["approval_status"])

    if status != ApprovalStatus.APPROVED:
        raise DeploymentApprovalRequiredError(
            deployment_id=deployment_id,
            approval_status=status,
        )

    return {
        "deployment_id": deployment_id,
        "approval_status": status,
        "approver_id": row.get("approver_id"),
        "approved_at": row.get("approved_at"),
    }


# Export auto-generated types from the Phrase object
RequireDeploymentApprovalOptions = require_deployment_approval.options_type
RequireDeploymentApprovalResult = require_deployment_approval.result_type
