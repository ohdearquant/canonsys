"""Require that evidence exists for derived facts.

Complete vertical slice:
- Validates all evidence references exist
- Checks evidence is accessible to tenant
- Raises EvidenceMissingError if any reference invalid

Regulatory: PRD-001 - Evidence must be bound before decisions emit
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

__all__ = [
    "EvidenceMissingError",
    "RequireEvidencePresentSpecs",
    "require_evidence_present",
]


class EvidenceMissingError(Exception):
    """Required evidence is missing.

    Regulatory:
        - PRD-001: Evidence must be bound before decisions emit
        - FCRA Section 1681m: Adverse actions require supporting evidence
        - Employment law: Termination decisions require documentation
    """

    def __init__(
        self,
        missing_refs: list[UUID],
        total_refs: int,
    ):
        self.missing_refs = missing_refs
        self.total_refs = total_refs
        super().__init__(
            f"{len(missing_refs)} of {total_refs} evidence references not found: "
            f"{[str(ref) for ref in missing_refs[:3]]}..."
        )


class RequireEvidencePresentSpecs(BaseModel):
    """Specs for require evidence present phrase."""

    # inputs
    evidence_refs: list[UUID]
    check_ceps: bool = True  # Also check CEP table
    # outputs
    satisfied: bool = False
    found_count: int = 0
    missing_refs: list[UUID] | None = None


@canon_phrase(
    Operable.from_structure(RequireEvidencePresentSpecs),
    inputs={"evidence_refs", "check_ceps"},
    outputs={"satisfied", "found_count", "missing_refs"},
)
async def require_evidence_present(
    options: RequireEvidencePresentSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that all evidence references exist.

    Gate pattern that validates evidence availability. Checks both
    the evidence table and optionally the CEP table.

    Args:
        options: Options containing evidence_refs list.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if all evidence found.

    Raises:
        EvidenceMissingError: If any evidence references not found.
    """
    evidence_refs = options.evidence_refs or []
    check_ceps = options.check_ceps

    if not evidence_refs:
        return {
            "satisfied": True,
            "found_count": 0,
            "missing_refs": None,
        }

    found_refs: set[UUID] = set()
    missing_refs: list[UUID] = []

    for ref_id in evidence_refs:
        # Check evidence table
        row = await select_one(
            "evidences",
            where={"id": ref_id},
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )

        if row and row.get("tenant_id") == ctx.tenant_id:
            found_refs.add(ref_id)
            continue

        # Optionally check CEP table
        if check_ceps:
            cep_row = await select_one(
                "certified_evidence_packets",
                where={"id": ref_id},
                conn=ctx.conn,
                tenant_scope=TenantScope.REQUIRED,
            )

            if cep_row and cep_row.get("tenant_id") == ctx.tenant_id:
                found_refs.add(ref_id)
                continue

        # Not found in either table
        missing_refs.append(ref_id)

    if missing_refs:
        raise EvidenceMissingError(
            missing_refs=missing_refs,
            total_refs=len(evidence_refs),
        )

    return {
        "satisfied": True,
        "found_count": len(found_refs),
        "missing_refs": None,
    }
