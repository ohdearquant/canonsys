"""Require that consent has not been withdrawn.

Complete vertical slice:
- Queries consent tokens for subject and scope
- Gates on withdrawal (REVOKED) status
- Raises ConsentWithdrawnError if withdrawn

Regulatory: GDPR Art. 7(3), CCPA Section 1798.120
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import FK, TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.utils import now_utc

from ..exceptions import ConsentWithdrawnError
from ..types import ConsentScope, ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireConsentNotWithdrawnSpecs", "require_consent_not_withdrawn"]


class RequireConsentNotWithdrawnSpecs(BaseModel):
    """Specs for require consent not withdrawn phrase."""

    # inputs
    scope: ConsentScope
    # outputs
    subject_id: FK[Person] | None = None
    consent_id: FK[ConsentToken] | None = None
    granted_at: datetime | None = None
    status: str | None = None


@canon_phrase(
    Operable.from_structure(RequireConsentNotWithdrawnSpecs),
    inputs={"scope"},
    outputs={"subject_id", "scope", "consent_id", "granted_at", "status"},
)
async def require_consent_not_withdrawn(
    options: RequireConsentNotWithdrawnSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that consent has not been explicitly withdrawn.

    Gate pattern that validates consent has not been revoked.
    Per GDPR Art. 7(3), withdrawal must be as easy as granting.
    Once withdrawn (status REVOKED), consent cannot be relied upon.

    Fail-closed: If consent has been withdrawn, raises ConsentWithdrawnError.

    Args:
        options: Options containing scope to check.
        ctx: Request context (tenant, actor, subject_id).

    Returns:
        Dict with consent details if consent is not withdrawn.

    Raises:
        ConsentWithdrawnError: If consent has been withdrawn.
    """
    scope = options.scope
    subject_id = ctx.subject_id

    # Check for withdrawn (REVOKED) consent
    revoked_row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope.value,
            "status": ConsentStatus.REVOKED.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if revoked_row:
        withdrawn_at = revoked_row.get("revoked_at") or now_utc()
        raise ConsentWithdrawnError(
            subject_id=subject_id,
            scope=scope.value,
            withdrawn_at=withdrawn_at,
            context={
                "token_id": str(revoked_row["id"]),
                "revocation_reason": revoked_row.get("revocation_reason"),
            },
        )

    # Query for any consent record (to return info if exists)
    row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # No consent record at all - not withdrawn, but also doesn't exist
        # This is OK for this gate - we're only checking withdrawal status
        return {
            "subject_id": subject_id,
            "scope": scope,
            "consent_id": None,
            "granted_at": None,
            "status": None,
        }

    return {
        "subject_id": subject_id,
        "scope": scope,
        "consent_id": row["id"],
        "granted_at": row.get("granted_at"),
        "status": row.get("status"),
    }
