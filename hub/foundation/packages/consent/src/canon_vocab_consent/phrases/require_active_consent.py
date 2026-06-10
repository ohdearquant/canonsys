"""Require that consent has not been withdrawn.

Complete vertical slice:
- Queries consent tokens for subject and scope
- Checks if consent status is REVOKED (withdrawn)
- Raises ConsentWithdrawnError if withdrawn

Regulatory: GDPR Art. 7(3), FCRA 15 U.S.C. Section 1681b(b)(2)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.types import FK
from kron.utils import now_utc

from ..exceptions import ConsentWithdrawnError
from ..types import ConsentStatus, ConsentToken

__all__ = ["RequireActiveConsentSpecs", "require_active_consent"]


class RequireActiveConsentSpecs(BaseModel):
    """Specs for require active consent phrase."""

    # inputs
    scope: str
    # outputs
    subject_id: FK[Person] | None = None
    consent_id: FK[ConsentToken] | None = None
    granted_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(RequireActiveConsentSpecs),
    inputs={"scope"},
    outputs={"subject_id", "scope", "consent_id", "granted_at"},
)
async def require_active_consent(
    options: RequireActiveConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that consent has not been withdrawn.

    Per GDPR Art. 7(3), data subject has right to withdraw consent at any time.
    Per FCRA 15 U.S.C. Section 1681b(b)(2), consent required before procuring
    consumer report - withdrawn consent invalidates authorization.

    Fail-closed: If consent was withdrawn, raises ConsentWithdrawnError.

    Args:
        options: Options containing scope
        ctx: Request context (tenant, actor, subject_id, conn)

    Returns:
        Dict with subject_id, scope, consent_id, granted_at if consent is active.

    Raises:
        ConsentWithdrawnError: If consent has been withdrawn.
    """
    scope = options.scope
    subject_id = ctx.subject_id

    # Query for revoked (withdrawn) consent
    row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": ConsentStatus.REVOKED.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if row:
        # Consent was withdrawn - raise error
        withdrawn_at = row.get("revoked_at") or now_utc()
        raise ConsentWithdrawnError(
            subject_id=subject_id,
            scope=scope,
            withdrawn_at=withdrawn_at,
        )

    # Check if active consent exists
    active_row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope,
            "status": ConsentStatus.ACTIVE.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not active_row:
        # No consent record at all - this is OK for this check
        # (require_valid_consent handles the "no consent" case)
        # Return a result indicating no withdrawn consent was found
        # but also no active consent exists
        raise ConsentWithdrawnError(
            subject_id=subject_id,
            scope=scope,
            withdrawn_at=now_utc(),
            context={"reason": "No consent record found for scope"},
        )

    # Active consent exists and not withdrawn
    return {
        "subject_id": subject_id,
        "scope": scope,
        "consent_id": active_row["id"],
        "granted_at": active_row.get("granted_at"),
    }


# Backwards compatibility alias for the auto-generated result type
# Access via require_active_consent.result_type at runtime
ActiveConsentResult = require_active_consent.result_type
