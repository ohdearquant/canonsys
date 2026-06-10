"""Get case audit timeline for legal/auditor view.

Returns all evidence as timeline entries - the read-only
view for litigation and audit purposes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetCaseHistorySpecs", "TimelineEntry", "get_case_history"]


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Single entry in case timeline."""

    evidence_id: UUID
    collected_at: datetime | None
    evidence_type: str
    title: str | None
    operation: str | None
    content_hash: str | None
    chain_hash: str | None


class GetCaseHistorySpecs(BaseModel):
    """Specs for get case history phrase."""

    # inputs
    case_id: UUID
    tenant_id: UUID
    workflow_type: str | None = None
    # outputs
    evidence_count: int = 0
    timeline: tuple[Any, ...] = ()  # tuple[TimelineEntry, ...]
    earliest: datetime | None = None
    latest: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetCaseHistorySpecs),
    inputs={"case_id", "tenant_id", "workflow_type"},
    outputs={
        "case_id",
        "workflow_type",
        "evidence_count",
        "timeline",
        "earliest",
        "latest",
    },
)
async def get_case_history(
    options: GetCaseHistorySpecs,
    ctx: RequestContext,
) -> dict:
    """Get complete audit timeline for a case.

    Queries evidence and chain entries to build a chronological
    timeline suitable for legal/audit review. Each entry includes
    integrity hashes for verification.

    Args:
        options: Get options containing case_id, tenant_id, workflow_type
        ctx: Request context

    Returns:
        Dict with case_id, workflow_type, evidence_count, timeline, earliest, latest
    """
    case_id = options.case_id
    tenant_id = options.tenant_id
    workflow_type = options.workflow_type

    # Query evidence with chain entries joined
    # LEFT JOIN since genesis evidence may not have chain entry yet
    sql = """
        SELECT
            e.id AS evidence_id,
            e.collected_at,
            e.evidence_type,
            e.title,
            e.data->>'operation' AS operation,
            e.content_hash,
            c.chain_hash
        FROM evidences e
        LEFT JOIN chain_entrys c
            ON c.resource_id = e.id
            AND c.resource_type = 'evidence'
        WHERE e.tenant_id = $1
          AND e.data->>'case_id' = $2
          AND e.is_deleted = false
        ORDER BY e.collected_at ASC, e.created_at ASC
    """
    args: tuple[Any, ...] = (tenant_id, str(case_id))

    rows = await fetch(
        sql,
        *args,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Transform rows to TimelineEntry
    timeline: list[TimelineEntry] = []
    timestamps: list[datetime] = []

    for row in rows:
        entry = TimelineEntry(
            evidence_id=row["evidence_id"],
            collected_at=row["collected_at"],
            evidence_type=row["evidence_type"],
            title=row["title"],
            operation=row["operation"],
            content_hash=row["content_hash"],
            chain_hash=row["chain_hash"],
        )
        timeline.append(entry)

        if row["collected_at"] is not None:
            timestamps.append(row["collected_at"])

    # Compute earliest/latest from sorted results
    earliest = timestamps[0] if timestamps else None
    latest = timestamps[-1] if timestamps else None

    return {
        "case_id": case_id,
        "workflow_type": workflow_type,
        "evidence_count": len(timeline),
        "timeline": tuple(timeline),
        "earliest": earliest,
        "latest": latest,
    }
