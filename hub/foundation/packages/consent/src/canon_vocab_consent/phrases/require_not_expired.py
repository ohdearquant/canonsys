"""Require that consent has not expired.

Complete vertical slice:
- Queries consent tokens for subject and scope
- Gates on expiration timestamp
- Raises ConsentExpiredError if expired

Regulatory: GDPR Art. 7(1), FCRA 15 U.S.C. Section 1681b(b)(2)(A)(ii)
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
from ..types import ConsentScope, ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireConsentNotExpiredSpecs", "require_consent_not_expired"]


class RequireConsentNotExpiredSpecs(BaseModel):
    """Specs for require consent not expired phrase."""

    # inputs
    scope: ConsentScope
    as_of: datetime | None = None  # Optional reference time for check
    # outputs
    subject_id: FK[Person] | None = None
    consent_id: FK[ConsentToken] | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(RequireConsentNotExpiredSpecs),
    inputs={"scope", "as_of"},
    outputs={"subject_id", "scope", "consent_id", "granted_at", "expires_at"},
)
async def require_consent_not_expired(
    options: RequireConsentNotExpiredSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that consent has not expired.

    Gate pattern that validates consent is temporally valid.
    Checks the expires_at timestamp against current time (or as_of time).

    Per GDPR Art. 7(1), consent validity may be time-limited.
    Per FCRA 15 U.S.C. Section 1681b(b)(2)(A)(ii), consumer authorization
    for procurement of consumer report may include temporal limits.

    Fail-closed: If consent has expired, raises ConsentExpiredError.

    Args:
        options: Options containing scope and optional as_of time.
        ctx: Request context (tenant, actor, subject_id).

    Returns:
        Dict with consent details if consent is not expired.

    Raises:
        ConsentExpiredError: If consent has expired.
    """
    scope = options.scope
    subject_id = ctx.subject_id
    check_time = options.as_of or now_utc()

    # Query for consent token (any status that could have expiration)
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
        raise ConsentExpiredError(
            subject_id=subject_id,
            scope=scope.value,
            expired_at=check_time,
            context={"reason": "No consent record found for scope"},
        )

    # Check if status is already EXPIRED
    if row.get("status") == ConsentStatus.EXPIRED.value:
        expired_at = row.get("expires_at") or check_time
        raise ConsentExpiredError(
            subject_id=subject_id,
            scope=scope.value,
            expired_at=expired_at,
            context={"token_id": str(row["id"]), "status": "EXPIRED"},
        )

    # Check temporal expiration for ACTIVE tokens
    expires_at = row.get("expires_at")
    if expires_at and expires_at < check_time:
        raise ConsentExpiredError(
            subject_id=subject_id,
            scope=scope.value,
            expired_at=expires_at,
            context={"token_id": str(row["id"])},
        )

    return {
        "subject_id": subject_id,
        "scope": scope,
        "consent_id": row["id"],
        "granted_at": row.get("granted_at"),
        "expires_at": expires_at,
    }
