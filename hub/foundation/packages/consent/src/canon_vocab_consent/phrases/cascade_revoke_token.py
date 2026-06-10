"""Cascade revoke all dependent consent when primary is revoked.

When primary consent is revoked, all dependent scopes must also be
revoked. This feature handles that cascade logic atomically.
"""

from __future__ import annotations

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement import RequestContext
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.types import FK, ID

from ..types import ConsentScope, ConsentStatus, ConsentToken
from .revoke_token import revoke_consent_token

__all__ = ["CascadeRevokeSpecs", "cascade_revoke_consent_token"]


class CascadeRevokeSpecs(BaseModel):
    """Specs for cascade revoke consent phrase."""

    trigger_scope: ConsentScope
    trigger_reason: str | None = None
    triggered: bool
    subject_id: FK[Person]
    revoked_count: int
    revoked_scopes: tuple[ConsentScope, ...]
    revoked_token_ids: tuple[FK[ConsentToken], ...]
    cascade_reason: str


@canon_phrase(
    Operable.from_structure(CascadeRevokeSpecs),
    inputs={"trigger_scope", "trigger_reason"},
    outputs={
        "triggered",
        "trigger_scope",
        "subject_id",
        "revoked_count",
        "revoked_scopes",
        "revoked_token_ids",
        "cascade_reason",
    },
)
async def cascade_revoke_consent_token(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Cascade revoke all dependent consent tokens.

    When a primary scope (e.g., CONSIDERATION_AUTHORIZATION) is revoked, all scopes
    that depend on it must also be revoked atomically.

    Args:
        options: Cascade revocation options
        ctx: Request context

    Returns:
        CascadeRevocationResult with all revoked tokens
    """
    trigger_scope = options.get("trigger_scope")
    trigger_reason = options.get("trigger_reason")

    # Build cascade reason
    cascade_reason = f"Cascade from {trigger_scope.value} revocation"
    if trigger_reason:
        cascade_reason = f"{cascade_reason}: {trigger_reason}"

    # Check if trigger scope is primary (triggers cascade)
    primary_scopes = ConsentScope.primary()
    if trigger_scope not in primary_scopes:
        return {
            "triggered": False,
            "trigger_scope": trigger_scope,
            "subject_id": ctx.subject_id,
            "revoked_count": 0,
            "revoked_scopes": tuple(),
            "revoked_token_ids": tuple(),
            "cascade_reason": cascade_reason,
        }

    # Get dependent scopes for this primary
    scope_dependencies = ConsentScope.dependencies()
    dependent_scopes = scope_dependencies.get(trigger_scope, frozenset())
    if not dependent_scopes:
        return {
            "triggered": False,
            "trigger_scope": trigger_scope,
            "subject_id": ctx.subject_id,
            "revoked_count": 0,
            "revoked_scopes": tuple(),
            "revoked_token_ids": tuple(),
            "cascade_reason": cascade_reason,
        }

    # List all active tokens for subject
    rows = await select(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": ctx.subject_id,
            "status": ConsentStatus.ACTIVE.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Filter to dependent scopes only
    revoked_scopes: list[ConsentScope] = []
    revoked_token_ids: list[ID[ConsentToken]] = []

    for row in rows:
        scope_value = row["scope"]
        try:
            scope = ConsentScope(scope_value)
        except ValueError:
            # Unknown scope, skip
            continue

        if scope not in dependent_scopes:
            continue

        # Revoke this dependent token
        result = await revoke_consent_token(
            options={"scope": scope, "reason": cascade_reason},
            ctx=ctx,
        )

        if result.revoked and result.token_id:
            revoked_scopes.append(scope)
            revoked_token_ids.append(result.token_id)

    return {
        "triggered": len(revoked_scopes) > 0,
        "trigger_scope": trigger_scope,
        "subject_id": ctx.subject_id,
        "revoked_count": len(revoked_scopes),
        "revoked_scopes": tuple(revoked_scopes),
        "revoked_token_ids": tuple(revoked_token_ids),
        "cascade_reason": cascade_reason,
    }
