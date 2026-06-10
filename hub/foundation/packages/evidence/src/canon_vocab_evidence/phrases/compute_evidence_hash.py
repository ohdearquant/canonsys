"""Compute evidence hash for signing or verification.

Complete vertical slice:
- Fetches evidence record
- Computes deterministic hash from content
- Returns hash suitable for digital signatures

Regulatory: FRE 901, ISO 27037, digital signature standards
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ComputeEvidenceHashSpecs", "compute_evidence_hash"]


class ComputeEvidenceHashSpecs(BaseModel):
    """Specs for compute evidence hash phrase."""

    # inputs
    evidence_id: UUID
    include_metadata: bool = False  # Include timestamps, version in hash
    # outputs
    content_hash: str | None = None
    integrity_hash: str | None = None  # Full hash including metadata
    algorithm: str = "sha256"


def _build_hashable_content(row: dict[str, Any], include_metadata: bool) -> dict[str, Any]:
    """Build deterministic content dict for hashing.

    Args:
        row: Database row for evidence.
        include_metadata: Whether to include metadata fields.

    Returns:
        Dict suitable for compute_hash().
    """
    # Core content fields (always included)
    content: dict[str, Any] = {
        "evidence_type": row.get("evidence_type"),
        "title": row.get("title"),
        "data": row.get("data"),
        "source": row.get("source"),
        "source_id": str(row["source_id"]) if row.get("source_id") else None,
        "file_hash": row.get("file_hash"),
        "collected_at": (row["collected_at"].isoformat() if row.get("collected_at") else None),
        "subject_id": str(row["subject_id"]) if row.get("subject_id") else None,
        "supersedes_id": (str(row["supersedes_id"]) if row.get("supersedes_id") else None),
    }

    if include_metadata:
        # Add metadata fields for integrity hash
        content["id"] = str(row["id"])
        content["tenant_id"] = str(row["tenant_id"])
        content["created_at"] = row["created_at"].isoformat() if row.get("created_at") else None
        content["updated_at"] = row["updated_at"].isoformat() if row.get("updated_at") else None
        content["version"] = row.get("version")
        content["is_deleted"] = row.get("is_deleted", False)

    return content


@canon_phrase(
    Operable.from_structure(ComputeEvidenceHashSpecs),
    inputs={"evidence_id", "include_metadata"},
    outputs={"evidence_id", "content_hash", "integrity_hash", "algorithm"},
)
async def compute_evidence_hash(
    options: ComputeEvidenceHashSpecs,
    ctx: RequestContext,
) -> dict:
    """Compute deterministic hash for evidence.

    Computes two hashes:
    1. content_hash: Hash of core content fields (stable across versions)
    2. integrity_hash: Hash including metadata (unique per record)

    The content_hash is suitable for:
    - Digital signatures
    - Deduplication
    - Content verification

    The integrity_hash is suitable for:
    - Audit trail verification
    - Tamper detection including metadata changes

    Args:
        options: Options containing evidence_id.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with computed hashes.

    Raises:
        ValueError: If evidence not found.

    Regulatory basis:
        - FRE 901: Authentication of evidence
        - ISO 27037: Digital evidence handling
        - RFC 6979: Digital signature standards
    """
    evidence_id = options.evidence_id
    include_metadata = options.include_metadata

    # Fetch evidence record
    row = await select_one(
        "evidences",
        where={"id": evidence_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise ValueError(f"Evidence {evidence_id} not found")

    if row.get("tenant_id") != ctx.tenant_id:
        raise ValueError("Evidence belongs to different tenant")

    # Compute content hash (core fields only)
    content = _build_hashable_content(row, include_metadata=False)
    content_hash = compute_hash(content)

    # Compute integrity hash (including metadata if requested)
    integrity_hash: str | None = None
    if include_metadata:
        full_content = _build_hashable_content(row, include_metadata=True)
        integrity_hash = compute_hash(full_content)

    return {
        "evidence_id": evidence_id,
        "content_hash": content_hash,
        "integrity_hash": integrity_hash,
        "algorithm": "sha256",
    }
