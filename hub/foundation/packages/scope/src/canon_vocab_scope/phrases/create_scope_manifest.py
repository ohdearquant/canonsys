"""Create scope manifest with cryptographic hash.

Creates manifests with hashes for integrity verification and drift detection.

Regulatory context:
    - GDPR Art. 5(1)(c) (Data minimization)
    - SOC 2 CC6.1 (Logical access controls)
    - ISO 27001 A.9.1.1 (Access control policy)
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CreateScopeManifestSpecs", "create_scope_manifest"]


class CreateScopeManifestSpecs(BaseModel):
    """Specs for create scope manifest phrase."""

    # inputs
    targets: list[str] = Field(
        ...,
        description="List of target identifiers (e.g., user IDs, resource paths)",
    )
    exclusions: list[str] | None = Field(
        default=None,
        description="Optional list of exclusions from scope",
    )
    # outputs
    manifest_id: UUID | None = None
    manifest_hash: str | None = None
    target_count: int | None = None
    exclusions_count: int | None = None
    created_at: datetime | None = None


def _compute_manifest_hash(targets: list[str], exclusions: list[str] | None) -> str:
    """Compute SHA256 hash of manifest contents.

    Hash is computed over:
    - Sorted targets (for deterministic ordering)
    - Sorted exclusions (if any)

    This enables integrity verification: if targets change, hash changes.
    """
    sorted_targets = sorted(targets)
    sorted_exclusions = sorted(exclusions) if exclusions else []
    content = f"targets:{','.join(sorted_targets)}|exclusions:{','.join(sorted_exclusions)}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@canon_phrase(
    Operable.from_structure(CreateScopeManifestSpecs),
    inputs={"targets", "exclusions"},
    outputs={
        "manifest_id",
        "manifest_hash",
        "target_count",
        "exclusions_count",
        "created_at",
    },
)
async def create_scope_manifest(
    options: CreateScopeManifestSpecs,
    ctx: RequestContext,
) -> dict:
    """Create a scope manifest with cryptographic hash for integrity.

    Creates a manifest document capturing the defined scope (targets and exclusions)
    with a SHA256 hash enabling future integrity verification. Use this to:

    1. Document what entities/resources are in scope for an operation
    2. Enable drift detection when scope is re-verified later
    3. Provide audit evidence of scope definition at a point in time

    Regulatory Citations:
        - GDPR Art. 5(1)(c): Personal data shall be adequate, relevant, and limited
          to what is necessary (data minimization). Manifests document scope bounds.
        - SOC 2 CC6.1: The entity implements logical access security software,
          infrastructure, and architectures. Manifests define access scope.
        - ISO 27001 A.9.1.1: An access control policy shall be established,
          documented, and reviewed. Manifests are the documentation artifact.

    Args:
        options: Manifest creation options (targets, exclusions).
        ctx: Request context (tenant, actor).

    Returns:
        dict with manifest_id, manifest_hash, target_count, exclusions_count, created_at.

    Examples:
        >>> options = CreateScopeManifestSpecs(
        ...     targets=["user:123", "user:456", "user:789"],
        ...     exclusions=["user:999"],
        ... )
        >>> result = await create_scope_manifest(options, ctx)
        >>> # Store manifest_id and manifest_hash for later verification
    """
    exclusions = options.exclusions or []
    manifest_hash = _compute_manifest_hash(options.targets, exclusions)

    return {
        "manifest_id": uuid4(),
        "manifest_hash": manifest_hash,
        "target_count": len(options.targets),
        "exclusions_count": len(exclusions),
        "created_at": now_utc(),
    }
