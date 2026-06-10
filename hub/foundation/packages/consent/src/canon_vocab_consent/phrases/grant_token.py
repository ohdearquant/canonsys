"""Grant consent for data processing.

Complete vertical slice:
- Creates consent token for subject + scope
- Records consent evidence with timestamp
- Supports GDPR/FCRA consent requirements
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import cast

from pydantic import BaseModel

from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.types import FK
from kron.utils import now_utc

from ..types import ConsentScope, ConsentToken, ConsentTokenContent

__all__ = ["GrantConsentSpecs", "grant_consent_token"]


class GrantConsentSpecs(BaseModel):
    """Specs for grant consent phrase."""

    # inputs
    scope: ConsentScope
    expires_in: timedelta | None = None
    expires_at: datetime | None = None
    # outputs
    token_id: FK[ConsentToken] | None = None
    subject_id: FK[Person] | None = None
    granted_at: datetime | None = None


def _expiration_date_must_be_future(
    expires_at: datetime | None, expires_in: timedelta | None
) -> None:
    """Validate that expiration is in the future."""
    if expires_at is not None and expires_at - now_utc() <= timedelta(0):
        raise ValueError("expires_at must be in the future.")
    if expires_in is not None and expires_in <= timedelta(0):
        raise ValueError("expires_in must be a positive duration.")


def _resolve_expiration(
    expires_at: datetime | None, expires_in: timedelta | None
) -> datetime | None:
    """Resolve expiration from either expires_at or expires_in."""
    _expiration_date_must_be_future(expires_at, expires_in)

    if expires_at is not None:
        return expires_at
    if expires_in is not None:
        return now_utc() + expires_in
    return None


@canon_phrase(
    Operable.from_structure(GrantConsentSpecs),
    inputs={"scope", "expires_in", "expires_at"},
    outputs={"token_id", "subject_id", "scope", "granted_at", "expires_at"},
)
async def grant_consent_token(
    options: GrantConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """Grant consent for a subject and scope.

    Args:
        options: Grant options containing scope, expires_in, expires_at
        ctx: Request context (tenant, actor, subject)

    Returns:
        Dict with token_id, subject_id, scope, granted_at, expires_at
    """
    # Validation: ensure only one of expires_in or expires_at is provided
    if options.expires_in is not None and options.expires_at is not None:
        raise ValueError("Only one of expires_in or expires_at may be provided.")

    if ctx.subject_id is None:
        raise ValueError("subject_id is required to grant consent")

    expires_at = _resolve_expiration(options.expires_at, options.expires_in)
    scope = options.scope

    # Cast subject_id to FK[Person] - both are UUID at runtime, but FK carries
    # foreign key metadata for ORM/DDL generation
    subject_fk = cast("FK[Person]", ctx.subject_id)
    content = ConsentTokenContent(
        scope=scope,
        granted_by_id=ctx.actor_id,
        tenant_id=ctx.tenant_id,
        subject_id=subject_fk,
        expires_at=expires_at,
    )
    token = ConsentToken(content=content)

    from canon.db import insert_entity

    await insert_entity(token, conn=ctx.conn)

    return {
        "token_id": token.id,
        "subject_id": ctx.subject_id,
        "scope": token.content.scope,
        "granted_at": token.content.granted_at,
        "expires_at": expires_at,
    }
