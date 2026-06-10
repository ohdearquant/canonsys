"""Require that rollback procedure has been tested.

Gate check ensuring rollback procedures have been tested
before allowing deployment to proceed.

Regulatory:
    - SOC 2 CC8.1 (Change management)
    - ISO 27001 A.12.1.2 (Change management)
    - NIST SP 800-53 CP-4 (Contingency plan testing)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field

from canon.db import TenantScope, select
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import RollbackTestStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireRollbackTestedSpecs", "require_rollback_tested"]


class RequireRollbackTestedSpecs(BaseModel):
    """Specs for require rollback tested phrase."""

    # inputs
    deployment_id: UUID
    max_test_age_days: int = Field(default=30)
    # outputs
    satisfied: bool = False
    test_status: RollbackTestStatus | None = None
    tested_at: datetime | None = None
    tester_id: UUID | None = None


require_rollback_tested_operable = Operable.from_structure(RequireRollbackTestedSpecs)


@canon_phrase(
    require_rollback_tested_operable,
    inputs={"deployment_id", "max_test_age_days"},
    outputs={"satisfied", "deployment_id", "test_status", "tested_at", "tester_id"},
)
async def require_rollback_tested(
    options: RequireRollbackTestedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that rollback procedure has been tested.

    Raises RequirementNotMetError if rollback not tested or test expired.

    Regulatory:
        - SOC 2 CC8.1 (Change management)
        - ISO 27001 A.12.1.2 (Change management)
        - NIST SP 800-53 CP-4 (Contingency plan testing)

    Args:
        options: Options containing deployment_id and max_test_age_days
        ctx: Request context (tenant, actor)

    Returns:
        Dict indicating test status.

    Raises:
        RequirementNotMetError: If rollback not tested or test expired.
    """
    deployment_id = options.deployment_id
    max_test_age_days = options.max_test_age_days
    now = now_utc()

    rows = await select(
        "deployment_rollback_tests",
        where={
            "tenant_id": ctx.tenant_id,
            "deployment_id": deployment_id,
        },
        order_by="tested_at DESC",
        limit=1,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    row = rows[0] if rows else None

    if not row:
        raise RequirementNotMetError(
            requirement="rollback_tested",
            reason=f"Rollback must be tested for deployment {deployment_id}",
        )

    status = RollbackTestStatus(row["test_status"])
    tested_at = row.get("tested_at")

    if status == RollbackTestStatus.FAILED:
        raise RequirementNotMetError(
            requirement="rollback_tested",
            reason="Rollback test failed",
        )

    if status != RollbackTestStatus.PASSED:
        raise RequirementNotMetError(
            requirement="rollback_tested",
            reason=f"Rollback test status: {status.value}",
        )

    # Check test freshness
    if tested_at and (now - tested_at) > timedelta(days=max_test_age_days):
        raise RequirementNotMetError(
            requirement="rollback_tested",
            reason=f"Rollback test expired (>{max_test_age_days} days old)",
        )

    return {
        "satisfied": True,
        "deployment_id": deployment_id,
        "test_status": status,
        "tested_at": tested_at,
        "tester_id": row.get("tester_id"),
    }


# Export auto-generated types from the Phrase object
RequireRollbackTestedOptions = require_rollback_tested.options_type
RequireRollbackTestedResult = require_rollback_tested.result_type
