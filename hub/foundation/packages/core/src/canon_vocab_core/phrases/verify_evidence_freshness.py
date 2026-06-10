"""Verify evidence freshness phrase.

Checks that evidence is within acceptable age limit.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyEvidenceFreshnessSpecs", "verify_evidence_freshness"]


class VerifyEvidenceFreshnessSpecs(BaseModel):
    """Specs for verify evidence freshness phrase.

    Regulatory context:
        - PCI DSS 11.3: Quarterly vulnerability scans
        - SOC 2 CC7.1: Timely response to security events
        - ISO 27001 A.12.6: Technical vulnerability management
    """

    # inputs
    evidence_id: UUID
    max_age_seconds: int  # timedelta as seconds for BaseModel compatibility
    # outputs
    fresh: bool
    evidence_age_seconds: int
    found: bool
    collected_at: datetime | None = None
    expires_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyEvidenceFreshnessSpecs),
    inputs={"evidence_id", "max_age_seconds"},
    outputs={
        "evidence_id",
        "fresh",
        "evidence_age_seconds",
        "max_age_seconds",
        "collected_at",
        "expires_at",
        "found",
        "reason",
    },
)
async def verify_evidence_freshness(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify that evidence is within acceptable age limit.

    Checks if the evidence artifact was collected within the specified
    maximum age threshold.

    Args:
        options: Verification options (evidence_id, max_age_seconds)
        ctx: Request context

    Returns:
        dict with freshness status and timing details
    """
    evidence_id: UUID = options.evidence_id
    max_age_seconds: int = options.max_age_seconds
    max_age = timedelta(seconds=max_age_seconds)

    # Query evidence by ID
    row = await select_one(
        "evidences",
        where={"id": evidence_id, "tenant_id": ctx.tenant_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    now = datetime.now(UTC)

    # Handle not found
    if row is None:
        return {
            "evidence_id": evidence_id,
            "fresh": False,
            "evidence_age_seconds": 0,
            "max_age_seconds": max_age_seconds,
            "found": False,
            "collected_at": None,
            "expires_at": None,
            "reason": f"Evidence not found: {evidence_id}",
        }

    # Handle deleted evidence
    if row.get("is_deleted", False):
        return {
            "evidence_id": evidence_id,
            "fresh": False,
            "evidence_age_seconds": 0,
            "max_age_seconds": max_age_seconds,
            "found": False,
            "collected_at": None,
            "expires_at": None,
            "reason": f"Evidence has been deleted: {evidence_id}",
        }

    # Get collected_at timestamp (fall back to created_at if not set)
    collected_at = row.get("collected_at") or row.get("created_at")

    if collected_at is None:
        return {
            "evidence_id": evidence_id,
            "fresh": False,
            "evidence_age_seconds": 0,
            "max_age_seconds": max_age_seconds,
            "found": True,
            "collected_at": None,
            "expires_at": None,
            "reason": "Evidence has no collection timestamp",
        }

    # Ensure timezone-aware comparison
    if collected_at.tzinfo is None:
        collected_at = collected_at.replace(tzinfo=UTC)

    # Calculate age
    evidence_age = now - collected_at
    expires_at = collected_at + max_age

    # Check freshness
    is_fresh = evidence_age <= max_age

    reason = None
    if not is_fresh:
        # Format age for human-readable message
        age_hours = evidence_age.total_seconds() / 3600
        max_hours = max_age.total_seconds() / 3600

        if age_hours >= 24:
            age_str = f"{evidence_age.days} days"
        else:
            age_str = f"{age_hours:.1f} hours"

        if max_hours >= 24:
            max_str = f"{max_age.days} days"
        else:
            max_str = f"{max_hours:.1f} hours"

        reason = f"Evidence is stale ({age_str} old, max {max_str})"

    return {
        "evidence_id": evidence_id,
        "fresh": is_fresh,
        "evidence_age_seconds": int(evidence_age.total_seconds()),
        "max_age_seconds": max_age_seconds,
        "collected_at": collected_at,
        "expires_at": expires_at,
        "found": True,
        "reason": reason,
    }
