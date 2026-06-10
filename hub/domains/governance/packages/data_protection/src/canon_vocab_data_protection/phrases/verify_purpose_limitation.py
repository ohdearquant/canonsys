"""Verify purpose limitation.

Verifies that requested use matches declared purpose for data.

Regulatory context:
    - GDPR Art. 5(1)(b): Purpose limitation
    - CCPA Section 1798.100(b): Collection limitation
    - HIPAA 164.502(a): Minimum necessary
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

__all__ = ["VerifyPurposeLimitationSpecs", "verify_purpose_limitation"]


class VerifyPurposeLimitationSpecs(BaseModel):
    """Specs for verify purpose limitation phrase."""

    # inputs
    resource_id: UUID
    requested_use: str
    # outputs
    verified: bool | None = None
    declared_purpose: str | None = None
    purposes_match: bool | None = None
    reason: str | None = None


verify_purpose_limitation_operable = Operable.from_structure(VerifyPurposeLimitationSpecs)


@canon_phrase(
    verify_purpose_limitation_operable,
    inputs={"resource_id", "requested_use"},
    outputs={
        "verified",
        "resource_id",
        "declared_purpose",
        "requested_use",
        "purposes_match",
        "reason",
    },
)
async def verify_purpose_limitation(
    options: VerifyPurposeLimitationSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that requested use matches declared purpose for data.

    Generic purpose limitation check for any privacy domain.
    Ensures data is only used for the purpose it was collected.

    Args:
        options: Verification options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with verified, resource_id, declared_purpose, requested_use, purposes_match, reason

    Regulatory:
        - GDPR Art. 5(1)(b): Purpose limitation
        - CCPA Section 1798.100(b): Collection limitation
        - HIPAA 164.502(a): Minimum necessary
    """
    resource_id = options.resource_id
    requested_use = options.requested_use

    row = await select_one(
        "data_purpose_declarations",
        where={"resource_id": resource_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        return {
            "verified": False,
            "resource_id": resource_id,
            "declared_purpose": "unknown",
            "requested_use": requested_use,
            "purposes_match": False,
            "reason": "No purpose declaration found for resource",
        }

    declared_purpose = row["declared_purpose"]
    allowed_uses = row.get("allowed_uses") or []

    # Check if requested use matches declared purpose or is in allowed uses
    purposes_match = requested_use == declared_purpose or requested_use in allowed_uses

    return {
        "verified": purposes_match,
        "resource_id": resource_id,
        "declared_purpose": declared_purpose,
        "requested_use": requested_use,
        "purposes_match": purposes_match,
        "reason": (
            None
            if purposes_match
            else f"Use '{requested_use}' not permitted for purpose '{declared_purpose}'"
        ),
    }


# Export auto-generated types from the Phrase object
VerifyPurposeLimitationOptions = verify_purpose_limitation.options_type
VerifyPurposeLimitationResult = verify_purpose_limitation.result_type
