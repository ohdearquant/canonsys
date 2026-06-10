"""Require limited audience gate for confidential content.

Raises LimitedAudienceRequiredError if confidential/restricted content
targets unlimited audience.

Regulatory context:
    - GDPR Art. 5(1)(f): Confidentiality
    - HIPAA 164.502: Minimum necessary
    - SOC 2 CC6.1: Access restrictions
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import LimitedAudienceRequiredError
from ..types import AudienceScope, ConfidentialityLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireLimitedAudienceSpecs", "require_limited_audience"]


class RequireLimitedAudienceSpecs(BaseModel):
    """Specs for require limited audience phrase."""

    # inputs
    resource_id: UUID
    target_audience: AudienceScope
    # outputs
    confidentiality: ConfidentialityLevel | None = None


require_limited_audience_operable = Operable.from_structure(RequireLimitedAudienceSpecs)


@canon_phrase(
    require_limited_audience_operable,
    inputs={"resource_id", "target_audience"},
    outputs={"resource_id", "confidentiality", "target_audience"},
)
async def require_limited_audience(
    options: RequireLimitedAudienceSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that confidential content targets a limited audience.

    Raises LimitedAudienceRequiredError if confidential/restricted content
    targets unlimited audience.

    Args:
        options: Audience options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, confidentiality, target_audience

    Raises:
        LimitedAudienceRequiredError: If confidential content targets unlimited audience.

    Regulatory:
        - GDPR Art. 5(1)(f): Confidentiality
        - HIPAA 164.502: Minimum necessary
        - SOC 2 CC6.1: Access restrictions
    """
    resource_id = options.resource_id
    target_audience = options.target_audience

    row = await select_one(
        "resource_classifications",
        where={"resource_id": resource_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        # Unknown classification, deny unlimited by default
        if target_audience == AudienceScope.UNLIMITED:
            raise LimitedAudienceRequiredError(
                resource_id=resource_id,
                confidentiality=ConfidentialityLevel.INTERNAL,
                target_audience=target_audience,
                context={"reason": "Unknown classification cannot target unlimited audience"},
            )
        return {
            "resource_id": resource_id,
            "confidentiality": ConfidentialityLevel.INTERNAL,
            "target_audience": target_audience,
        }

    level = ConfidentialityLevel(row["confidentiality_level"])

    # Confidential/restricted cannot go to unlimited audience
    if (
        level in (ConfidentialityLevel.CONFIDENTIAL, ConfidentialityLevel.RESTRICTED)
        and target_audience == AudienceScope.UNLIMITED
    ):
        raise LimitedAudienceRequiredError(
            resource_id=resource_id,
            confidentiality=level,
            target_audience=target_audience,
        )

    return {
        "resource_id": resource_id,
        "confidentiality": level,
        "target_audience": target_audience,
    }


# Export auto-generated types from the Phrase object
RequireLimitedAudienceOptions = require_limited_audience.options_type
RequireLimitedAudienceResult = require_limited_audience.result_type
