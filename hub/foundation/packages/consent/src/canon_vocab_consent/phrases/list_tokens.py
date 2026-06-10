"""List consent tokens for subject with filters.

Unified feature that replaces _list_active_tokens and _list_tokens
from ConsentService. Supports filtering by status.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from canon.db import FK, TenantScope, select
from canon.enforcement.executor import canon_phrase
from canon.entities import Person
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ConsentScope, ConsentStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "ConsentStatusFilter",
    "ListConsentSpecs",
    "list_consent_tokens",
]


class ConsentStatusFilter(str, Enum):
    """Filter modes for listing consent tokens."""

    VALID = "valid"  # active + not expired (default)
    ACTIVE = "active"  # status == ACTIVE only (ignores expiry)
    ALL = "all"  # all statuses


class ListConsentSpecs(BaseModel):
    """Specs for list consent phrase."""

    # inputs
    scope: ConsentScope | None = None
    status_filter: ConsentStatusFilter | None = None
    as_of: datetime | None = None
    # outputs
    tokens: tuple = ()
    total: int = 0
    subject_id: FK[Person] | None = None
    filter_applied: ConsentStatusFilter = ConsentStatusFilter.VALID


@canon_phrase(
    Operable.from_structure(ListConsentSpecs),
    inputs={"scope", "status_filter", "as_of"},
    outputs={"tokens", "total", "subject_id", "filter_applied"},
)
async def list_consent_tokens(
    options: ListConsentSpecs,
    ctx: RequestContext,
) -> dict:
    """List consent tokens for subject with filters.

    Args:
        options: List options (scope, status_filter, as_of)
        ctx: Request context (provides subject_id, tenant_id, conn)

    Returns:
        Dict with tokens, total, subject_id, filter_applied
    """
    if ctx.subject_id is None:
        raise ValueError("subject_id required in context")

    subject_id = ctx.subject_id
    status_filter = options.status_filter or ConsentStatusFilter.VALID
    check_time = options.as_of or now_utc()

    # Build base where clause
    where: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "subject_id": subject_id,
    }

    # Add scope filter if specified
    scope = options.scope
    if scope is not None:
        where["scope"] = scope.value

    # Add status filter for ACTIVE and VALID modes
    if status_filter in (ConsentStatusFilter.VALID, ConsentStatusFilter.ACTIVE):
        where["status"] = ConsentStatus.ACTIVE.value

    # Query consent tokens
    rows = await select(
        "consent_tokens",
        where=where,
        order_by="granted_at DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Post-filter for VALID mode: exclude expired tokens
    tokens: list[dict[str, Any]] = []
    for row in rows:
        # For VALID filter, skip expired tokens
        if status_filter == ConsentStatusFilter.VALID:
            expires_at = row.get("expires_at")
            if expires_at is not None and expires_at < check_time:
                continue

        tokens.append(
            {
                "token_id": row["id"],
                "scope": ConsentScope(row["scope"]).value,
                "status": ConsentStatus(row["status"]).value,
                "version": row.get("version"),
                "granted_at": row["granted_at"],
                "expires_at": row.get("expires_at"),
            }
        )

    return {
        "tokens": tuple(tokens),
        "total": len(tokens),
        "subject_id": subject_id,
        "filter_applied": status_filter,
    }
