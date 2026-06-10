"""Require that consent has not expired.

Complete vertical slice:
- Queries consent tokens for subject and scope
- Checks if consent expires_at is in the past
- Raises ConsentExpiredError if expired

Regulatory: GDPR Art. 7(1) - consent must be freely given and can be time-limited
           FCRA 15 U.S.C. Section 1681b(b)(2)(A)(ii) - authorization for consumer
           report procurement may specify time limits
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

from ..exceptions import ConsentExpiredError
from ..types import ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireValidConsentSpecs", "require_valid_consent"]


class RequireValidConsentSpecs(BaseModel):
    """Specs for require valid consent phrase."""

    # inputs
    scope: str
    # outputs
    subject_id: FK[Person] | None = None
    consent_id: FK[ConsentToken] | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None


require_valid_consent_operable = Operable.from_structure(RequireValidConsentSpecs)


@canon_phrase(
    require_valid_consent_operable,
    inputs={"scope"},
    outputs={"subject_id", "scope", "consent_id", "granted_at", "expires_at"},
)
async def require_valid_consent(
    options: RequireValidConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that consent has not expired.

    Per GDPR Art. 7(1), consent validity may be time-limited.
    Per FCRA 15 U.S.C. Section 1681b(b)(2)(A)(ii), consumer authorization
    for procurement of consumer report may include temporal limits.

    Fail-closed: If consent has expired, raises ConsentExpiredError.

    Args:
        options: Options containing scope to check
        ctx: Request context (tenant, actor, subject_id)

    Returns:
        Dict with consent details if consent is valid.

    Raises:
        ConsentExpiredError: If consent has expired.
    """
    scope = options.scope
    subject_id = ctx.subject_id
    now = now_utc()

    # Query for active consent (we'll check expiration ourselves)
    row = await select_one(
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

    if not row:
        # Also check for explicitly expired status
        expired_row = await select_one(
            "consent_tokens",
            where={
                "tenant_id": ctx.tenant_id,
                "subject_id": subject_id,
                "scope": scope,
                "status": ConsentStatus.EXPIRED.value,
            },
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )

        if expired_row:
            # Consent marked as expired
            expired_at = expired_row.get("expires_at") or now
            raise ConsentExpiredError(
                subject_id=subject_id,
                scope=scope,
                expired_at=expired_at,
            )

        # No consent record at all
        raise ConsentExpiredError(
            subject_id=subject_id,
            scope=scope,
            expired_at=now,
            context={"reason": "No consent record found for scope"},
        )

    # Check if active consent has expired
    expires_at = row.get("expires_at")
    if expires_at and expires_at < now:
        # Consent has expired - raise error
        raise ConsentExpiredError(
            subject_id=subject_id,
            scope=scope,
            expired_at=expires_at,
        )

    # Consent is active and not expired
    return {
        "subject_id": subject_id,
        "scope": scope,
        "consent_id": row["id"],
        "granted_at": row.get("granted_at"),
        "expires_at": expires_at,
    }


# Export auto-generated types from the Phrase object
RequireValidConsentOptions = require_valid_consent.options_type
ValidConsentResult = require_valid_consent.result_type
