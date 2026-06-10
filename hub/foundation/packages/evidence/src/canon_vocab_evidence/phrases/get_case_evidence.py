"""Get all evidence records for a case.

Foundation query for certification workflows - returns all
evidence linked to a case_id, sorted chronologically.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetCaseEvidenceSpecs", "get_case_evidence"]


class GetCaseEvidenceSpecs(BaseModel):
    """Specs for get case evidence phrase."""

    # inputs
    case_id: UUID
    tenant_id: UUID
    evidence_type: str | None = None
    # outputs
    evidence_ids: tuple[UUID, ...] = ()
    count: int = 0
    earliest: datetime | None = None
    latest: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetCaseEvidenceSpecs),
    inputs={"case_id", "tenant_id", "evidence_type"},
    outputs={"case_id", "tenant_id", "evidence_ids", "count", "earliest", "latest"},
)
async def get_case_evidence(
    options: GetCaseEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Get all evidence for a case.

    Queries evidence table where data.case_id matches.
    Sorted by collected_at ascending (chronological).

    Args:
        options: Get options containing case_id, tenant_id, evidence_type
        ctx: Request context

    Returns:
        Dict with case_id, tenant_id, evidence_ids, count, earliest, latest
    """
    case_id = options.case_id
    tenant_id = options.tenant_id
    evidence_type = options.evidence_type

    # Build query for evidences where data->>'case_id' = case_id
    # Use raw SQL for JSONB filtering efficiency
    if evidence_type is not None:
        sql = """
            SELECT id, collected_at
            FROM evidences
            WHERE tenant_id = $1
              AND data->>'case_id' = $2
              AND evidence_type = $3
              AND is_deleted = false
            ORDER BY collected_at ASC
        """
        args: tuple[Any, ...] = (tenant_id, str(case_id), evidence_type)
    else:
        sql = """
            SELECT id, collected_at
            FROM evidences
            WHERE tenant_id = $1
              AND data->>'case_id' = $2
              AND is_deleted = false
            ORDER BY collected_at ASC
        """
        args = (tenant_id, str(case_id))

    rows = await fetch(
        sql,
        *args,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Extract IDs and timestamps
    evidence_ids: list[UUID] = []
    timestamps: list[datetime] = []

    for row in rows:
        evidence_ids.append(row["id"])
        if row["collected_at"] is not None:
            timestamps.append(row["collected_at"])

    # Compute earliest/latest from sorted results
    earliest = timestamps[0] if timestamps else None
    latest = timestamps[-1] if timestamps else None

    return {
        "case_id": case_id,
        "tenant_id": tenant_id,
        "evidence_ids": tuple(evidence_ids),
        "count": len(evidence_ids),
        "earliest": earliest,
        "latest": latest,
    }
