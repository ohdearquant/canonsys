"""Find valid consent token for subject and scope.

Unlike verify_consent (binary check), this returns full token data
for further operations (e.g., cascade revocation needs token list).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person, User
from kron.specs import Operable
from kron.types import FK
from kron.utils import now_utc

from ..types import ConsentScope, ConsentStatus, ConsentToken

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["FindConsentSpecs", "find_consent_token"]


class FindConsentSpecs(BaseModel):
    """Specs for find consent phrase."""

    # inputs
    scope: ConsentScope
    as_of: datetime | None = None
    # outputs
    found: bool = False
    token_id: FK[ConsentToken] | None = None
    subject_id: FK[Person] | None = None
    status: ConsentStatus | None = None
    version: str | None = None
    granted_at: datetime | None = None
    granted_by_id: FK[User] | None = None
    expires_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(FindConsentSpecs),
    inputs={"scope", "as_of"},
    outputs={
        "found",
        "token_id",
        "subject_id",
        "scope",
        "status",
        "version",
        "granted_at",
        "granted_by_id",
        "expires_at",
    },
)
async def find_consent_token(
    options: FindConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """Find valid consent token for subject and scope.

    Args:
        options: Find options (scope, as_of)
        ctx: Request context (provides subject_id, tenant_id, conn)

    Returns:
        dict with found=True and token data if found, found=False otherwise
    """
    scope = options.scope
    as_of = options.as_of
    check_time = as_of if as_of is not None else now_utc()

    # Query for active consent token
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
            "found": False,
            "token_id": None,
            "subject_id": ctx.subject_id,
            "scope": scope,
            "status": None,
            "version": None,
            "granted_at": None,
            "granted_by_id": None,
            "expires_at": None,
        }

    # Check expiration against check_time
    expires_at = row.get("expires_at")
    if expires_at and expires_at < check_time:
        return {
            "found": False,
            "token_id": None,
            "subject_id": ctx.subject_id,
            "scope": scope,
            "status": None,
            "version": None,
            "granted_at": None,
            "granted_by_id": None,
            "expires_at": None,
        }

    return {
        "found": True,
        "token_id": row["id"],
        "subject_id": row["subject_id"],
        "scope": ConsentScope(row["scope"]),
        "status": ConsentStatus(row["status"]),
        "version": row.get("version"),
        "granted_at": row["granted_at"],
        "granted_by_id": row.get("granted_by"),
        "expires_at": expires_at,
    }
