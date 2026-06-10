"""Renew consent token to extend validity.

Complete vertical slice:
- Finds active consent token
- Updates expires_at to new date
- Records renewal metadata
- Entity lifecycle: touch/rehash/version handled automatically

Regulatory basis: GDPR Art. 7, organizational consent validity policies
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import FK, TenantScope, select_one
from canon.db.entity_crud import update_entity
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ConsentScope, ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RenewConsentSpecs", "renew_consent_token"]


class RenewConsentSpecs(BaseModel):
    """Specs for renew consent phrase."""

    # inputs
    scope: ConsentScope
    new_expires_at: datetime | None = None
    extend_by: timedelta | None = None  # Alternative: extend by duration
    # outputs
    renewed: bool = False
    token_id: FK[ConsentToken] | None = None
    subject_id: FK[Person] | None = None
    previous_expires_at: datetime | None = None
    new_expires_at_out: datetime | None = None


def _resolve_new_expiration(
    current_expires_at: datetime | None,
    new_expires_at: datetime | None,
    extend_by: timedelta | None,
) -> datetime | None:
    """Resolve new expiration date from parameters.

    Args:
        current_expires_at: Current expiration (may be None).
        new_expires_at: Explicit new expiration date.
        extend_by: Duration to extend from current expiration.

    Returns:
        New expiration datetime, or None for perpetual.

    Raises:
        ValueError: If new expiration is in the past.
    """
    now = now_utc()

    if new_expires_at is not None:
        if new_expires_at <= now:
            raise ValueError("new_expires_at must be in the future")
        return new_expires_at

    if extend_by is not None:
        if extend_by <= timedelta(0):
            raise ValueError("extend_by must be a positive duration")
        # Extend from current expiration, or from now if perpetual
        base = current_expires_at or now
        return base + extend_by

    return None  # No change requested


@canon_phrase(
    Operable.from_structure(RenewConsentSpecs),
    inputs={"scope", "new_expires_at", "extend_by"},
    outputs={
        "renewed",
        "token_id",
        "subject_id",
        "scope",
        "previous_expires_at",
        "new_expires_at_out",
    },
)
async def renew_consent_token(
    options: RenewConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """Renew consent token by extending its validity period.

    Updates the expires_at field of an active consent token.
    Can specify either an absolute new_expires_at date or a
    relative extend_by duration.

    Args:
        options: Renew options containing scope and expiration parameters.
        ctx: Request context (tenant, actor, subject_id).

    Returns:
        Dict with renewal details.

    Raises:
        ValueError: If no active consent found or invalid expiration.
    """
    scope = options.scope
    subject_id = ctx.subject_id

    # Find active consent
    row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": scope.value,
            "status": ConsentStatus.ACTIVE.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "renewed": False,
            "token_id": None,
            "subject_id": subject_id,
            "scope": scope,
            "previous_expires_at": None,
            "new_expires_at_out": None,
        }

    previous_expires_at = row.get("expires_at")

    # Resolve new expiration
    new_expiration = _resolve_new_expiration(
        current_expires_at=previous_expires_at,
        new_expires_at=options.new_expires_at,
        extend_by=options.extend_by,
    )

    if new_expiration is None and previous_expires_at is None:
        # No change - already perpetual and no new expiration specified
        return {
            "renewed": False,
            "token_id": row["id"],
            "subject_id": subject_id,
            "scope": scope,
            "previous_expires_at": previous_expires_at,
            "new_expires_at_out": None,
        }

    # Reconstruct entity and update
    token = ConsentToken.from_dict(row, from_row=True)
    token.content.expires_at = new_expiration

    await update_entity(token, by=ctx.actor_id, conn=ctx.conn)

    return {
        "renewed": True,
        "token_id": token.id,
        "subject_id": subject_id,
        "scope": scope,
        "previous_expires_at": previous_expires_at,
        "new_expires_at_out": new_expiration,
    }
