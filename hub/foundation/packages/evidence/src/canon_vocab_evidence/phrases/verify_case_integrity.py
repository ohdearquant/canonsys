"""Verify content integrity for all case evidence.

Walks each evidence record and verifies content_hash matches
recomputed hash from data. Different from verify_chain which
checks chain linkage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyCaseIntegritySpecs", "verify_case_integrity"]


class VerifyCaseIntegritySpecs(BaseModel):
    """Specs for verify case integrity phrase."""

    # inputs
    case_id: UUID
    tenant_id: UUID
    # outputs
    valid: bool = False
    evidence_count: int = 0
    verified_count: int = 0
    integrity_score: float = 0.0  # 0-100
    issues: tuple[str, ...] = ()


@canon_phrase(
    Operable.from_structure(VerifyCaseIntegritySpecs),
    inputs={"case_id", "tenant_id"},
    outputs={
        "case_id",
        "valid",
        "evidence_count",
        "verified_count",
        "integrity_score",
        "issues",
    },
)
async def verify_case_integrity(
    options: VerifyCaseIntegritySpecs,
    ctx: RequestContext,
) -> dict:
    """Verify content integrity for case evidence.

    For each evidence record:
    1. Recompute hash from data using compute_hash()
    2. Compare to stored content_hash
    3. Track mismatches as issues

    Args:
        options: Verify options containing case_id, tenant_id
        ctx: Request context

    Returns:
        Dict with case_id, valid, evidence_count, verified_count, integrity_score, issues
    """
    case_id = options.case_id
    tenant_id = options.tenant_id

    # Query all evidence for case
    # Evidence stores case_id in the JSONB data column
    sql = """
        SELECT id, data, content_hash
        FROM "public"."evidences"
        WHERE tenant_id = $1
          AND data->>'case_id' = $2
        ORDER BY collected_at ASC NULLS LAST, created_at ASC
    """

    rows = await fetch(
        sql,
        tenant_id,
        str(case_id),
        conn=ctx.conn,
        tenant_scope=TenantScope.DISABLED,  # We're filtering by tenant_id explicitly
    )

    if not rows:
        return {
            "case_id": case_id,
            "valid": True,
            "evidence_count": 0,
            "verified_count": 0,
            "integrity_score": 100.0,
            "issues": ("No evidence found for case",),
        }

    issues: list[str] = []
    verified_count = 0

    for row in rows:
        evidence_id = row["id"]
        data = row.get("data")
        stored_hash = row.get("content_hash")

        # If no data, nothing to verify for content integrity
        if data is None:
            verified_count += 1
            continue

        # If no stored hash, cannot verify
        if stored_hash is None:
            issues.append(f"Evidence {evidence_id}: missing content_hash (cannot verify)")
            continue

        # Recompute hash from data
        try:
            expected_hash = compute_hash(data)
        except Exception as e:
            issues.append(f"Evidence {evidence_id}: failed to compute hash - {e!s}")
            continue

        # Compare hashes
        if stored_hash != expected_hash:
            issues.append(
                f"Evidence {evidence_id}: content_hash mismatch "
                f"(expected: {expected_hash[:16]}..., stored: {stored_hash[:16]}...)"
            )
        else:
            verified_count += 1

    evidence_count = len(rows)
    integrity_score = (verified_count / evidence_count) * 100 if evidence_count > 0 else 100.0
    valid = len(issues) == 0

    return {
        "case_id": case_id,
        "valid": valid,
        "evidence_count": evidence_count,
        "verified_count": verified_count,
        "integrity_score": integrity_score,
        "issues": tuple(issues),
    }
