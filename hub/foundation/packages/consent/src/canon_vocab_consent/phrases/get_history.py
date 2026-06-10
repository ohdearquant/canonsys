"""Get consent history for audit trail.

Complete vertical slice:
- Queries all consent tokens for subject (all statuses)
- Returns chronological history of consent changes
- Includes grants, revocations, expirations

Regulatory basis: GDPR Art. 7(1) - demonstrate consent
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import FK, TenantScope, select
from canon.enforcement.executor import canon_phrase
from canon.entities.shared import Person
from kron.specs import Operable

from ..types import ConsentScope

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ConsentHistoryEntry", "GetConsentHistorySpecs", "get_consent_history"]


@dataclass(frozen=True, slots=True)
class ConsentHistoryEntry:
    """Single entry in consent history."""

    token_id: UUID
    scope: str
    status: str
    granted_at: datetime | None
    granted_by_id: UUID | None
    expires_at: datetime | None
    revoked_at: datetime | None
    revoked_by_id: UUID | None
    revocation_reason: str | None
    created_at: datetime
    version: int


class GetConsentHistorySpecs(BaseModel):
    """Specs for get consent history phrase."""

    # inputs
    scope: ConsentScope | None = None  # Optional: filter by scope
    include_expired: bool = True
    include_revoked: bool = True
    # outputs
    subject_id: FK[Person] | None = None
    entries: tuple[Any, ...] = ()  # tuple[ConsentHistoryEntry, ...]
    total: int = 0
    earliest_grant: datetime | None = None
    latest_activity: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetConsentHistorySpecs),
    inputs={"scope", "include_expired", "include_revoked"},
    outputs={"subject_id", "entries", "total", "earliest_grant", "latest_activity"},
)
async def get_consent_history(
    options: GetConsentHistorySpecs,
    ctx: RequestContext,
) -> dict:
    """Get complete consent history for a subject.

    Returns all consent tokens (all statuses) for audit purposes.
    Per GDPR Art. 7(1), controllers must be able to demonstrate
    that consent was given.

    Args:
        options: Options for filtering history.
        ctx: Request context (tenant, actor, subject_id).

    Returns:
        Dict with entries list and summary statistics.
    """
    subject_id = ctx.subject_id

    # Build where clause
    where: dict[str, Any] = {
        "tenant_id": ctx.tenant_id,
        "subject_id": subject_id,
    }

    # Optional scope filter
    if options.scope is not None:
        where["scope"] = options.scope.value

    # Query all matching tokens
    rows = await select(
        "consent_tokens",
        where=where,
        order_by="created_at ASC",
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Filter by status if requested
    entries: list[ConsentHistoryEntry] = []
    grant_times: list[datetime] = []
    activity_times: list[datetime] = []

    for row in rows:
        status = row.get("status", "")

        # Apply status filters
        if status == "expired" and not options.include_expired:
            continue
        if status == "revoked" and not options.include_revoked:
            continue

        entry = ConsentHistoryEntry(
            token_id=row["id"],
            scope=row["scope"],
            status=status,
            granted_at=row.get("granted_at"),
            granted_by_id=row.get("granted_by_id"),
            expires_at=row.get("expires_at"),
            revoked_at=row.get("revoked_at"),
            revoked_by_id=row.get("revoked_by_id"),
            revocation_reason=row.get("revocation_reason"),
            created_at=row["created_at"],
            version=row.get("version", 1),
        )
        entries.append(entry)

        # Track timestamps for summary
        if entry.granted_at:
            grant_times.append(entry.granted_at)
            activity_times.append(entry.granted_at)
        if entry.revoked_at:
            activity_times.append(entry.revoked_at)
        activity_times.append(entry.created_at)

    # Compute summary
    earliest_grant = min(grant_times) if grant_times else None
    latest_activity = max(activity_times) if activity_times else None

    return {
        "subject_id": subject_id,
        "entries": tuple(entries),
        "total": len(entries),
        "earliest_grant": earliest_grant,
        "latest_activity": latest_activity,
    }
