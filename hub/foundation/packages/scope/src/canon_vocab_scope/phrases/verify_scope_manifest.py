"""Verify scope manifest integrity.

Verifies that current scope matches the original manifest hash.

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization - scope must remain bounded
    - SOC 2 CC6.1: Logical access controls
    - ISO 27001 A.9.1.1: Access control policy
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyScopeManifestSpecs", "verify_scope_manifest"]


class VerifyScopeManifestSpecs(BaseModel):
    """Specs for verify scope manifest phrase."""

    # inputs
    manifest_id: UUID
    current_targets: list[str]
    expected_hash: str | None = None
    # outputs
    verified: bool | None = None
    actual_hash: str | None = None
    drift_detected: bool | None = None


def _compute_targets_hash(targets: list[str]) -> str:
    """Compute SHA256 hash of sorted targets."""
    sorted_targets = sorted(targets)
    content = f"targets:{','.join(sorted_targets)}|exclusions:"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@canon_phrase(
    Operable.from_structure(VerifyScopeManifestSpecs),
    inputs={"manifest_id", "current_targets", "expected_hash"},
    outputs={
        "verified",
        "manifest_id",
        "expected_hash",
        "actual_hash",
        "drift_detected",
    },
)
async def verify_scope_manifest(
    options: VerifyScopeManifestSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that current scope matches the original manifest.

    Computes hash of current targets and compares against the expected hash
    from the original manifest. Detects scope drift - when the actual scope
    differs from what was originally defined and approved.

    Regulatory Citations:
        - GDPR Art. 5(1)(c): Data minimization requires scope to remain bounded.
          Drift detection ensures scope hasn't expanded without authorization.
        - SOC 2 CC6.1: Logical access controls must be maintained. Drift
          indicates control failures requiring investigation.
        - ISO 27001 A.9.1.1: Access control policy compliance requires
          detecting unauthorized scope changes.

    Args:
        options: Verification options (manifest_id, current_targets, expected_hash).
        ctx: Request context (tenant, actor).

    Returns:
        dict with verified, manifest_id, expected_hash, actual_hash, drift_detected.
    """
    if options.expected_hash is None:
        return {
            "verified": False,
            "manifest_id": options.manifest_id,
            "expected_hash": "",
            "actual_hash": None,
            "drift_detected": True,
        }

    actual_hash = _compute_targets_hash(options.current_targets)
    verified = actual_hash == options.expected_hash

    return {
        "verified": verified,
        "manifest_id": options.manifest_id,
        "expected_hash": options.expected_hash,
        "actual_hash": actual_hash,
        "drift_detected": not verified,
    }
