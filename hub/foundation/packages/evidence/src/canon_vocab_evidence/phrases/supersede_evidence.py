"""Supersede evidence for corrections.

Complete vertical slice:
- Creates new evidence that supersedes old evidence
- Links supersession in chain
- Old evidence remains immutable (backward pointer only)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, insert, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["SupersedeEvidenceSpecs", "supersede_evidence"]


class SupersedeEvidenceSpecs(BaseModel):
    """Specs for supersede evidence phrase."""

    # inputs
    original_id: UUID
    correction: Any  # EvidenceContent
    reason: str | None = None
    # outputs
    new_evidence_id: UUID | None = None
    content_hash: str | None = None


@canon_phrase(
    Operable.from_structure(SupersedeEvidenceSpecs),
    inputs={"original_id", "correction", "reason"},
    outputs={"new_evidence_id", "content_hash"},
)
async def supersede_evidence(
    options: SupersedeEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Create new evidence that supersedes existing evidence.

    Immutability pattern: Original evidence is never modified.
    New evidence has supersedes_id pointing back to original.

    Args:
        options: Supersede options containing original_id, correction, reason
        ctx: Request context (tenant, actor)

    Returns:
        Dict with new_evidence_id, content_hash

    Raises:
        ValueError: If original not found or tenant mismatch
    """
    original_id = options.original_id
    correction: EvidenceContent = options.correction

    # Fetch original evidence
    original_row = await select_one(
        "evidences",
        where={"id": original_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not original_row:
        raise ValueError(f"Evidence {original_id} not found")

    if original_row["tenant_id"] != ctx.tenant_id:
        raise ValueError("Evidence tenant doesn't match context")

    # Build original Evidence for chain linking
    original = _row_to_evidence(original_row)

    # Ensure correction has supersedes_id set
    correction.supersedes_id = original_id

    # Validate tenant match
    if correction.tenant_id != ctx.tenant_id:
        raise ValueError("Correction tenant_id doesn't match context")

    # Compute content hash
    correction.touch(by=ctx.actor_id)

    new_evidence = Evidence(content=correction)
    row_data = _evidence_to_row(new_evidence)

    result = await insert(
        "evidences",
        row_data,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not result:
        raise RuntimeError("Evidence insert returned no result")

    saved_evidence = _row_to_evidence(result)

    # Import chain_evidence locally to avoid circular import
    from .chain_evidence import ChainEvidenceSpecs, chain_evidence

    # Chain to original with supersession event type
    await chain_evidence(
        ChainEvidenceSpecs(
            parent=original,
            child=saved_evidence,
            event_type="evidence_superseded",
        ),
        ctx,
    )

    return {
        "new_evidence_id": saved_evidence.id,
        "content_hash": saved_evidence.content_hash,
    }


def _evidence_to_row(evidence: Evidence) -> dict[str, Any]:
    """Convert Evidence entity to database row dict."""
    content = evidence.content

    return {
        "id": evidence.id,
        "created_at": evidence.created_at,
        "tenant_id": content.tenant_id,
        "subject_id": content.subject_id,
        "evidence_type": content.evidence_type,
        "title": content.title,
        "data": content.data,
        "source": content.source,
        "source_id": content.source_id,
        "file_hash": content.file_hash,
        "collected_at": content.collected_at,
        "collected_by_id": content.collected_by_id,
        "expires_at": content.expires_at,
        "supersedes_id": content.supersedes_id,
        "updated_at": evidence.updated_at,
        "updated_by": evidence.updated_by,
        "is_deleted": evidence.is_deleted,
        "is_active": evidence.is_active,
        "version": evidence.version,
        "content_hash": evidence.content_hash,
        "integrity_hash": evidence.integrity_hash,
    }


def _row_to_evidence(row: dict[str, Any]) -> Evidence:
    """Convert database row to Evidence entity."""
    content = EvidenceContent(
        tenant_id=row["tenant_id"],
        subject_id=row.get("subject_id"),
        evidence_type=row["evidence_type"],
        title=row.get("title"),
        data=row.get("data"),
        source=row.get("source"),
        source_id=row.get("source_id"),
        file_hash=row.get("file_hash"),
        collected_at=row.get("collected_at"),
        collected_by_id=row.get("collected_by_id"),
        expires_at=row.get("expires_at"),
        supersedes_id=row.get("supersedes_id"),
    )

    return Evidence(
        id=row["id"],
        created_at=row["created_at"],
        content=content,
        updated_at=row.get("updated_at"),
        updated_by=row.get("updated_by"),
        is_deleted=row.get("is_deleted", False),
        is_active=row.get("is_active", True),
        version=row.get("version", 1),
        content_hash=row.get("content_hash"),
        integrity_hash=row.get("integrity_hash"),
    )
