"""Verify data minimization.

Verifies that only necessary fields are requested for workflow.

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization
    - HIPAA 164.502(b): Minimum necessary
    - CCPA Section 1798.100(c): Collection limitation
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyDataMinimizationSpecs", "verify_data_minimization"]


class VerifyDataMinimizationSpecs(BaseModel):
    """Specs for verify data minimization phrase."""

    # inputs
    workflow_id: UUID
    requested_fields: list[str]
    # outputs
    verified: bool | None = None
    allowed_fields: tuple[str, ...] | None = None
    excess_fields: tuple[str, ...] | None = None
    reason: str | None = None


verify_data_minimization_operable = Operable.from_structure(VerifyDataMinimizationSpecs)


@canon_phrase(
    verify_data_minimization_operable,
    inputs={"workflow_id", "requested_fields"},
    outputs={
        "verified",
        "workflow_id",
        "requested_fields",
        "allowed_fields",
        "excess_fields",
        "reason",
    },
)
async def verify_data_minimization(
    options: VerifyDataMinimizationSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that only necessary fields are requested for workflow.

    Generic data minimization check for any privacy domain.
    Ensures workflows only access fields they're allowed to use.

    Args:
        options: Verification options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with verified, workflow_id, requested_fields, allowed_fields, excess_fields, reason

    Regulatory:
        - GDPR Art. 5(1)(c): Data minimization
        - HIPAA 164.502(b): Minimum necessary
        - CCPA Section 1798.100(c): Collection limitation
    """
    workflow_id = options.workflow_id
    requested_fields = options.requested_fields

    row = await select_one(
        "workflow_field_allowlists",
        where={"workflow_id": workflow_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        # No allowlist = all fields allowed (legacy compatibility)
        return {
            "verified": True,
            "workflow_id": workflow_id,
            "requested_fields": tuple(requested_fields),
            "allowed_fields": (),
            "excess_fields": (),
            "reason": "No field allowlist defined (all permitted)",
        }

    allowed_fields = set(row.get("allowed_fields") or [])
    requested_set = set(requested_fields)
    excess = requested_set - allowed_fields

    return {
        "verified": len(excess) == 0,
        "workflow_id": workflow_id,
        "requested_fields": tuple(sorted(requested_fields)),
        "allowed_fields": tuple(sorted(allowed_fields)),
        "excess_fields": tuple(sorted(excess)),
        "reason": (
            None if len(excess) == 0 else f"Excess fields requested: {', '.join(sorted(excess))}"
        ),
    }


# Export auto-generated types from the Phrase object
VerifyDataMinimizationOptions = verify_data_minimization.options_type
VerifyDataMinimizationResult = verify_data_minimization.result_type
