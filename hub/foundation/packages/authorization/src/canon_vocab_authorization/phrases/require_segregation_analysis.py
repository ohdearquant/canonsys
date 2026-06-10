"""Require segregation of duties analysis before access grant.

Complete vertical slice:
- Queries for segregation analysis record
- Checks analysis is complete
- Checks no conflicts found
- Raises RequirementNotMetError if incomplete or conflicts

Regulatory:
    - SOX Section 404 (Internal controls)
    - SOC 2 CC5.1 (Control activities)
    - COSO Framework (Segregation of duties)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import SegregationStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireSegregationAnalysisSpecs", "require_segregation_analysis"]


class RequireSegregationAnalysisSpecs(BaseModel):
    """Specs for require segregation analysis phrase."""

    # inputs
    resource_id: UUID
    # outputs (defaults required for instantiation with inputs only)
    satisfied: bool = False
    status: SegregationStatus | None = None
    analysis_id: UUID | None = None
    completed_at: datetime | None = None
    conflicts_found: int = 0
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireSegregationAnalysisSpecs),
    inputs={"resource_id"},
    outputs={
        "satisfied",
        "resource_id",
        "status",
        "analysis_id",
        "completed_at",
        "conflicts_found",
        "reason",
    },
)
async def require_segregation_analysis(
    options: RequireSegregationAnalysisSpecs,
    ctx: RequestContext,
) -> dict:
    """Require segregation of duties analysis before access grant.

    Verifies that a segregation analysis has been completed for the resource
    and that no conflicts were found.

    Args:
        options: Options containing resource_id
        ctx: Request context with connection

    Returns:
        Dict with analysis status and metadata.

    Raises:
        RequirementNotMetError: If analysis incomplete or conflicts found
    """
    resource_id: UUID = options.resource_id

    query = """
        SELECT analysis_id, status, completed_at, conflicts_found
        FROM segregation_analyses
        WHERE resource_id = $1
        ORDER BY completed_at DESC NULLS LAST
        LIMIT 1
    """
    row = await ctx.conn.fetchrow(query, resource_id)

    if not row:
        raise RequirementNotMetError(
            requirement="segregation_analysis",
            reason=f"Segregation analysis required for resource {resource_id}",
        )

    status = SegregationStatus(row["status"])

    if status != SegregationStatus.COMPLETE:
        raise RequirementNotMetError(
            requirement="segregation_analysis",
            reason=f"Segregation analysis status: {status.value}",
        )

    if row["conflicts_found"] > 0:
        raise RequirementNotMetError(
            requirement="segregation_analysis",
            reason=f"Segregation conflicts found: {row['conflicts_found']}",
        )

    return {
        "satisfied": True,
        "resource_id": resource_id,
        "status": status,
        "analysis_id": row["analysis_id"],
        "completed_at": row["completed_at"],
        "conflicts_found": 0,
        "reason": None,
    }
