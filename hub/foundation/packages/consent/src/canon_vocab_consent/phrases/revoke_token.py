"""Revoke consent tokens.

Complete vertical slice:
- Validates active consent exists
- Fetches entity, updates status to REVOKED
- Records revocation reason and actor
- Entity lifecycle: touch/rehash/version handled automatically

Regulatory basis: GDPR Art. 7(3), FCRA 15 U.S.C. Section 1681b(b)(2)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.db.entity_crud import update_entity
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.types import FK
from kron.utils import now_utc

from ..types import ConsentScope, ConsentStatus, ConsentToken

__all__ = ["RevokeConsentSpecs", "revoke_consent_token"]


class RevokeConsentSpecs(BaseModel):
    """Specs for revoke consent phrase."""

    # inputs
    scope: ConsentScope
    reason: str | None = None
    # outputs
    revoked: bool = False
    token_id: FK[ConsentToken] | None = None
    subject_id: FK[Person] | None = None
    revoked_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(RevokeConsentSpecs),
    inputs={"scope", "reason"},
    outputs={"revoked", "token_id", "subject_id", "scope", "revoked_at", "reason"},
)
async def revoke_consent_token(
    options,
    ctx: RequestContext,
) -> dict:
    """Revoke consent for a subject and scope.

    Uses entity lifecycle: fetches ConsentToken entity, modifies content,
    then update_entity() handles touch/rehash/version automatically.
    """
    scope = options.scope
    reason = options.reason
    now = now_utc()

    # Find active consent
    row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": ctx.subject_id,
            "scope": scope.value,
            "status": ConsentStatus.ACTIVE.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "revoked": False,
            "token_id": None,
            "subject_id": ctx.subject_id,
            "scope": scope,
            "revoked_at": None,
            "reason": "No active consent found to revoke",
        }

    # Reconstruct entity, update status via entity lifecycle
    token = ConsentToken.from_dict(row, from_row=True)
    token.content.status = ConsentStatus.REVOKED
    token.content.revoked_at = now
    token.content.revoked_by_id = ctx.actor_id
    token.content.revocation_reason = reason

    await update_entity(token, by=ctx.actor_id, conn=ctx.conn)

    return {
        "revoked": True,
        "token_id": token.id,
        "subject_id": ctx.subject_id,
        "scope": scope,
        "revoked_at": now,
        "reason": reason,
    }
