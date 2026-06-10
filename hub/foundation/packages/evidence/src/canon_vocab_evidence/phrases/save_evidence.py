"""Save evidence to database.

Complete vertical slice:
- Persists Evidence entity to database
- Evidence is immutable (insert-only, no updates)
- Returns saved Evidence with id populated

Regulatory context:
    - FRE 901 (Authentication of evidence)
    - ISO 27037 (Digital evidence handling)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, insert_entity
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext
    from canon.entities import Evidence

__all__ = ["SaveEvidenceSpecs", "save_evidence"]


class SaveEvidenceSpecs(BaseModel):
    """Specs for save evidence phrase."""

    # inputs
    evidence: Any  # Evidence entity - Any to avoid pydantic validation issues
    # outputs
    saved_id: UUID | None = None
    content_hash: str | None = None


@canon_phrase(
    Operable.from_structure(SaveEvidenceSpecs),
    inputs={"evidence"},
    outputs={"saved_id", "content_hash"},
)
async def save_evidence(
    options: SaveEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Save evidence to database.

    Evidence is immutable - this performs an insert only.
    For corrections, use supersede_evidence instead.

    Args:
        options: Save options containing evidence entity
        ctx: Request context with tenant info

    Returns:
        Dict with saved_id and content_hash

    Raises:
        ValueError: If evidence tenant doesn't match context

    Regulatory context:
        - FRE 901 (Authentication of evidence)
        - ISO 27037 (Digital evidence handling)
    """
    evidence: Evidence = options.evidence

    # Validate tenant match
    if evidence.content.tenant_id != ctx.tenant_id:
        raise ValueError("Evidence tenant_id doesn't match context")

    # Insert using entity_crud (handles content_hash computation)
    saved = await insert_entity(
        evidence,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    return {
        "saved_id": saved.id,
        "content_hash": saved.content_hash,
    }
