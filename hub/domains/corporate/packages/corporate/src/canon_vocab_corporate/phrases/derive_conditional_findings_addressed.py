"""Derive whether all conditional findings are properly addressed.

ANTI-GAMING: This derivation examines the actual status of ALL conditional
findings from due diligence. Users cannot assert "findings addressed" -
the system derives this from evidence.

Regulatory Context:
    - SEC M&A disclosure rules: Material findings must be disclosed
    - Fiduciary duty: Proper due diligence required
    - Best practices: Complete resolution before closing

Complete vertical slice:
- Queries all conditional findings for deal
- Counts by status (open, remediated, waived, etc.)
- Identifies blocking findings
- Computes evidence hash for audit trail
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import FindingStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "DeriveConditionalFindingsAddressedSpecs",
    "derive_conditional_findings_addressed",
]


class DeriveConditionalFindingsAddressedSpecs(BaseModel):
    """Specs for conditional findings addressed derivation phrase."""

    # inputs
    deal_id: UUID

    # outputs
    addressed: bool | None = None
    total_findings: int | None = None
    open_count: int | None = None
    in_progress_count: int | None = None
    remediated_count: int | None = None
    waived_count: int | None = None
    blocked_count: int | None = None
    deferred_count: int | None = None
    blocking_findings: tuple[UUID, ...] | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None


def _compute_evidence_hash(data: list[dict[str, Any]]) -> str:
    """Compute SHA-256 hash of evidence data for audit trail."""
    content = str(sorted([str(sorted(d.items())) for d in data]))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@canon_phrase(
    Operable.from_structure(DeriveConditionalFindingsAddressedSpecs),
    inputs={"deal_id"},
    outputs={
        "deal_id",
        "addressed",
        "total_findings",
        "open_count",
        "in_progress_count",
        "remediated_count",
        "waived_count",
        "blocked_count",
        "deferred_count",
        "blocking_findings",
        "evidence_hash",
        "derived_at",
    },
)
async def derive_conditional_findings_addressed(
    options: DeriveConditionalFindingsAddressedSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Derive whether all conditional findings are properly addressed.

    Anti-gaming: This derivation examines the actual status of ALL
    conditional findings from due diligence. Users cannot assert
    "findings addressed" - the system derives this from evidence.

    Findings are considered addressed when:
    - Remediated: Issue has been fixed with evidence
    - Waived: Buyer has formally waived the finding
    - Deferred to closing: Explicitly deferred with approval

    Findings that BLOCK progress:
    - Open: Not yet addressed
    - In progress: Being worked but not complete
    - Blocked: Cannot be resolved

    Regulatory:
        - SEC M&A disclosure rules: Material findings must be disclosed
        - Fiduciary duty: Proper due diligence required
        - Best practices: Complete resolution before closing

    Args:
        options: Options containing deal_id
        ctx: Request context (tenant, actor)
        conn: Optional existing database connection

    Returns:
        Dict with derivation outcome
    """
    now = now_utc()
    deal_id = options.deal_id

    # Query all conditional findings for the deal
    rows = await fetch(
        """
        SELECT
            cf.finding_id,
            cf.status,
            cf.severity,
            cf.is_blocking,
            cf.updated_at
        FROM conditional_findings cf
        WHERE cf.deal_id = $1
        ORDER BY cf.severity DESC, cf.created_at
        """,
        deal_id,
        conn=conn or ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        # No findings - all addressed (vacuously true)
        return {
            "deal_id": deal_id,
            "addressed": True,
            "total_findings": 0,
            "open_count": 0,
            "in_progress_count": 0,
            "remediated_count": 0,
            "waived_count": 0,
            "blocked_count": 0,
            "deferred_count": 0,
            "blocking_findings": (),
            "evidence_hash": None,
            "derived_at": now,
        }

    # Count by status
    status_counts = {
        FindingStatus.OPEN: 0,
        FindingStatus.IN_PROGRESS: 0,
        FindingStatus.REMEDIATED: 0,
        FindingStatus.WAIVED: 0,
        FindingStatus.BLOCKED: 0,
        FindingStatus.DEFERRED_TO_CLOSING: 0,
    }

    blocking_findings: list[UUID] = []

    for row in rows:
        status = FindingStatus(row["status"])
        status_counts[status] = status_counts.get(status, 0) + 1

        # Track findings that block progress
        if status in (
            FindingStatus.OPEN,
            FindingStatus.IN_PROGRESS,
            FindingStatus.BLOCKED,
        ):
            blocking_findings.append(row["finding_id"])

    # Evidence hash for audit trail
    evidence_hash = _compute_evidence_hash(list(rows))

    # Addressed if no blocking findings
    addressed = len(blocking_findings) == 0

    return {
        "deal_id": deal_id,
        "addressed": addressed,
        "total_findings": len(rows),
        "open_count": status_counts[FindingStatus.OPEN],
        "in_progress_count": status_counts[FindingStatus.IN_PROGRESS],
        "remediated_count": status_counts[FindingStatus.REMEDIATED],
        "waived_count": status_counts[FindingStatus.WAIVED],
        "blocked_count": status_counts[FindingStatus.BLOCKED],
        "deferred_count": status_counts[FindingStatus.DEFERRED_TO_CLOSING],
        "blocking_findings": tuple(blocking_findings),
        "evidence_hash": evidence_hash,
        "derived_at": now,
    }
