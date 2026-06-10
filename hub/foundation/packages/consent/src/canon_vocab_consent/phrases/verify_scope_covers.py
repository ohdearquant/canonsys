"""Verify consent scope covers requested action.

Complete vertical slice:
- Checks if existing consent scope includes requested action scope
- Supports scope hierarchy (broader scope covers narrower)
- Returns binary verification result

Regulatory basis: FCRA Section 1681b(b)(2)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import FK, TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ConsentScope, ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyConsentScopeCoversSpecs", "verify_consent_scope_covers"]


# Scope hierarchy: broader scopes cover narrower scopes
# CONSIDERATION_AUTHORIZATION is the primary scope that covers all others
# Per ConsentScope definition, revoking primary cascades to all dependents
SCOPE_HIERARCHY: dict[ConsentScope, frozenset[ConsentScope]] = {
    # Primary scope covers all scopes (it's required before any other)
    ConsentScope.CONSIDERATION_AUTHORIZATION: frozenset(
        {
            ConsentScope.CONSIDERATION_AUTHORIZATION,
            ConsentScope.AI_SCORING,
            ConsentScope.INTERVIEW_RECORDING,
            ConsentScope.BACKGROUND_CHECK,
            ConsentScope.DATA_PROCESSING,
            ConsentScope.COMMUNICATIONS,
            ConsentScope.THIRD_PARTY_SHARING,
        }
    ),
    # Interview-specific scopes
    ConsentScope.AI_SCORING: frozenset(
        {
            ConsentScope.AI_SCORING,
        }
    ),
    ConsentScope.INTERVIEW_RECORDING: frozenset(
        {
            ConsentScope.INTERVIEW_RECORDING,
        }
    ),
    # Standard scopes (each covers only itself)
    ConsentScope.BACKGROUND_CHECK: frozenset(
        {
            ConsentScope.BACKGROUND_CHECK,
        }
    ),
    ConsentScope.DATA_PROCESSING: frozenset(
        {
            ConsentScope.DATA_PROCESSING,
        }
    ),
    ConsentScope.COMMUNICATIONS: frozenset(
        {
            ConsentScope.COMMUNICATIONS,
        }
    ),
    ConsentScope.THIRD_PARTY_SHARING: frozenset(
        {
            ConsentScope.THIRD_PARTY_SHARING,
        }
    ),
}


def scope_covers(granted_scope: ConsentScope, required_scope: ConsentScope) -> bool:
    """Check if granted scope covers the required scope.

    Args:
        granted_scope: The scope that was granted in consent.
        required_scope: The scope required for the action.

    Returns:
        True if granted scope covers required scope.
    """
    covered = SCOPE_HIERARCHY.get(granted_scope, frozenset({granted_scope}))
    return required_scope in covered


class VerifyConsentScopeCoversSpecs(BaseModel):
    """Specs for verify consent scope covers phrase."""

    # inputs
    subject_id: FK[Person]
    granted_scope: ConsentScope
    required_scope: ConsentScope
    # outputs
    covers: bool = False
    token_id: FK[ConsentToken] | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyConsentScopeCoversSpecs),
    inputs={"subject_id", "granted_scope", "required_scope"},
    outputs={"covers", "token_id", "granted_scope", "required_scope", "reason"},
)
async def verify_consent_scope_covers(
    options: VerifyConsentScopeCoversSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify consent scope covers the required action scope.

    Checks if the granted consent scope includes the required scope
    for the intended action. Supports scope hierarchy where broader
    scopes (like BACKGROUND_CHECK) cover narrower scopes.

    Args:
        options: Options containing granted_scope and required_scope.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with covers=True if scope is sufficient.

    Regulatory basis: FCRA Section 1681b(b)(2)
    """
    subject_id = options.subject_id
    granted_scope = options.granted_scope
    required_scope = options.required_scope

    # First verify consent exists and is active
    row = await select_one(
        "consent_tokens",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "scope": granted_scope.value,
            "status": ConsentStatus.ACTIVE.value,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "covers": False,
            "token_id": None,
            "granted_scope": granted_scope,
            "required_scope": required_scope,
            "reason": f"No active consent found for scope '{granted_scope.value}'",
        }

    # Check expiration
    expires_at = row.get("expires_at")
    if expires_at and expires_at < now_utc():
        return {
            "covers": False,
            "token_id": row.get("id"),
            "granted_scope": granted_scope,
            "required_scope": required_scope,
            "reason": "Consent token has expired",
        }

    # Check scope hierarchy
    if not scope_covers(granted_scope, required_scope):
        return {
            "covers": False,
            "token_id": row.get("id"),
            "granted_scope": granted_scope,
            "required_scope": required_scope,
            "reason": f"Scope '{granted_scope.value}' does not cover '{required_scope.value}'",
        }

    return {
        "covers": True,
        "token_id": row.get("id"),
        "granted_scope": granted_scope,
        "required_scope": required_scope,
        "reason": None,
    }
