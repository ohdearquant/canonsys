"""Require processor terms verified gate.

Raises ProcessorTermsNotVerifiedError if processor terms are not verified.

Regulatory context:
    - GDPR Art. 28: Processor requirements
    - CCPA Section 1798.140(w): Service provider contracts
    - HIPAA 164.308(b): Business associate contracts
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ProcessorTermsNotVerifiedError
from ..types import ProcessorTermsStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireProcessorTermsVerifiedSpecs", "require_processor_terms_verified"]


class RequireProcessorTermsVerifiedSpecs(BaseModel):
    """Specs for require processor terms verified phrase."""

    # inputs
    processor_id: UUID
    # outputs
    satisfied: bool | None = None
    status: ProcessorTermsStatus | None = None
    agreement_id: UUID | None = None
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    reason: str | None = None


require_processor_terms_verified_operable = Operable.from_structure(
    RequireProcessorTermsVerifiedSpecs
)


@canon_phrase(
    require_processor_terms_verified_operable,
    inputs={"processor_id"},
    outputs={
        "satisfied",
        "processor_id",
        "status",
        "agreement_id",
        "verified_at",
        "expires_at",
        "reason",
    },
)
async def require_processor_terms_verified(
    options: RequireProcessorTermsVerifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require verified processor/DPA terms before data sharing.

    Generic processor terms gate for any privacy domain.
    Ensures data processing agreements are in place.

    Raises ProcessorTermsNotVerifiedError if terms are not verified.

    Args:
        options: Processor terms options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with satisfied, processor_id, status, agreement_id, verified_at, expires_at, reason

    Raises:
        ProcessorTermsNotVerifiedError: If processor terms are not verified.

    Regulatory:
        - GDPR Art. 28: Processor requirements
        - CCPA Section 1798.140(w): Service provider contracts
        - HIPAA 164.308(b): Business associate contracts
    """
    processor_id = options.processor_id

    row = await select_one(
        "processor_agreements",
        where={"processor_id": processor_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        raise ProcessorTermsNotVerifiedError(
            processor_id=processor_id,
            status=ProcessorTermsStatus.NOT_FOUND,
        )

    status = ProcessorTermsStatus(row["status"])

    # Check expiration
    expires_at = row.get("expires_at")
    if expires_at:
        now = datetime.now(UTC)
        if now > expires_at:
            status = ProcessorTermsStatus.EXPIRED

    if status != ProcessorTermsStatus.VERIFIED:
        raise ProcessorTermsNotVerifiedError(
            processor_id=processor_id,
            status=status,
        )

    return {
        "satisfied": True,
        "processor_id": processor_id,
        "status": status,
        "agreement_id": row.get("agreement_id"),
        "verified_at": row.get("verified_at"),
        "expires_at": expires_at,
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireProcessorTermsVerifiedOptions = require_processor_terms_verified.options_type
RequireProcessorTermsVerifiedResult = require_processor_terms_verified.result_type
