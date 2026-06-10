"""Require that evidence has not been superseded.

Complete vertical slice:
- Checks if evidence has a superseding record
- Gates on supersession status
- Raises CEPSupersededError if superseded

Regulatory: SOX Section 802, audit requirements
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireEvidenceNotSupersededSpecs", "require_evidence_not_superseded"]


class EvidenceSupersededError(Exception):
    """Evidence has been superseded by a newer version.

    Regulatory:
        - SOX Section 802: Use current, valid documents
        - Audit requirements: Reference authoritative versions
    """

    def __init__(
        self,
        evidence_id: UUID,
        superseded_by_id: UUID,
    ):
        self.evidence_id = evidence_id
        self.superseded_by_id = superseded_by_id
        super().__init__(f"Evidence {evidence_id} has been superseded by {superseded_by_id}")


class RequireEvidenceNotSupersededSpecs(BaseModel):
    """Specs for require evidence not superseded phrase."""

    # inputs
    evidence_id: UUID
    # outputs
    satisfied: bool = False
    is_current: bool = False
    superseded_by_id: UUID | None = None


@canon_phrase(
    Operable.from_structure(RequireEvidenceNotSupersededSpecs),
    inputs={"evidence_id"},
    outputs={"evidence_id", "satisfied", "is_current", "superseded_by_id"},
)
async def require_evidence_not_superseded(
    options: RequireEvidenceNotSupersededSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that evidence has not been superseded.

    Gate pattern that validates evidence is the current version.
    Checks if any other evidence record has this evidence_id as
    its supersedes_id.

    Per SOX Section 802, operations should use current, valid documents.
    Superseded evidence remains in the audit trail but should not be
    used for new decisions.

    Fail-closed: If evidence has been superseded, raises error.

    Args:
        options: Options containing evidence_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if evidence is current.

    Raises:
        EvidenceSupersededError: If evidence has been superseded.
    """
    evidence_id = options.evidence_id

    # First verify evidence exists and is accessible
    evidence_row = await select_one(
        "evidences",
        where={"id": evidence_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not evidence_row:
        raise ValueError(f"Evidence {evidence_id} not found")

    if evidence_row.get("tenant_id") != ctx.tenant_id:
        raise ValueError("Evidence belongs to different tenant")

    # Check if any evidence supersedes this one
    superseding_row = await select_one(
        "evidences",
        where={
            "supersedes_id": evidence_id,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if superseding_row:
        superseded_by_id = superseding_row["id"]
        raise EvidenceSupersededError(
            evidence_id=evidence_id,
            superseded_by_id=superseded_by_id,
        )

    return {
        "evidence_id": evidence_id,
        "satisfied": True,
        "is_current": True,
        "superseded_by_id": None,
    }


# Re-export for backwards compatibility
__all__.append("EvidenceSupersededError")
