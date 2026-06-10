"""Require provenance documented phrase.

Requires provenance documentation for an artifact.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireProvenanceDocumentedSpecs", "require_provenance_documented"]


class RequireProvenanceDocumentedSpecs(BaseModel):
    """Specs for require provenance documented phrase.

    Regulatory:
        - EU AI Act Art. 12 (Record-keeping)
        - FDA 21 CFR Part 11 (Electronic records)
        - ISO 27001 A.12.4 (Logging and monitoring)
    """

    # inputs
    artifact_id: UUID
    require_source: bool = True
    require_transformation: bool = False
    # outputs
    satisfied: bool
    provenance_id: UUID | None = None
    source_documented: bool = False
    transformation_documented: bool = False
    documented_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireProvenanceDocumentedSpecs),
    inputs={"artifact_id", "require_source", "require_transformation"},
    outputs={
        "satisfied",
        "artifact_id",
        "provenance_id",
        "source_documented",
        "transformation_documented",
        "documented_at",
        "reason",
    },
)
async def require_provenance_documented(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Require provenance documentation for an artifact.

    Args:
        options: Requirement options (artifact_id, require_source, require_transformation)
        ctx: Request context

    Returns:
        dict with satisfaction status and provenance details

    Raises:
        RequirementNotMetError: If required provenance is missing.
    """
    artifact_id = options.get("artifact_id")
    require_source = options.get("require_source", True)
    require_transformation = options.get("require_transformation", False)

    query = """
        SELECT provenance_id, source_documented, transformation_documented, documented_at
        FROM artifact_provenance
        WHERE artifact_id = $1 AND tenant_id = $2
    """
    rows = await fetch(
        query,
        artifact_id,
        ctx.tenant_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # Already filtered in query
    )

    if not rows:
        raise RequirementNotMetError(
            requirement="provenance_documented",
            reason=f"Provenance required for artifact {artifact_id}",
        )

    row = rows[0]
    source_ok = not require_source or row["source_documented"]
    transform_ok = not require_transformation or row["transformation_documented"]

    if not (source_ok and transform_ok):
        missing = []
        if not source_ok:
            missing.append("source")
        if not transform_ok:
            missing.append("transformation")
        raise RequirementNotMetError(
            requirement="provenance_documented",
            reason=f"Missing provenance: {', '.join(missing)}",
        )

    return {
        "satisfied": True,
        "artifact_id": artifact_id,
        "provenance_id": row["provenance_id"],
        "source_documented": row["source_documented"],
        "transformation_documented": row["transformation_documented"],
        "documented_at": row["documented_at"],
        "reason": None,
    }
