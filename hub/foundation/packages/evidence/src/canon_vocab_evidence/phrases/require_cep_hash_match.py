"""Require CEP hash matches expected value.

Complete vertical slice:
- Fetches CEP and its content hash
- Compares against expected hash
- Raises CEPHashMismatchError if mismatch

Regulatory: SPEC-003 - Hash mismatch = BLOCK (tampering indicator)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import CEPNotFoundError, CEPTenantMismatchError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CEPHashMismatchError", "RequireCEPHashMatchSpecs", "require_cep_hash_match"]


class CEPHashMismatchError(Exception):
    """CEP content hash does not match expected value.

    This indicates potential tampering with the CEP.

    Regulatory:
        - SPEC-003: Hash mismatch = BLOCK
        - SOX Section 802: Document integrity
        - FRE 901: Authentication of evidence
    """

    def __init__(
        self,
        cep_id: UUID,
        expected_hash: str,
        actual_hash: str,
    ):
        self.cep_id = cep_id
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        super().__init__(
            f"CEP {cep_id} hash mismatch: expected {expected_hash[:12]}..., "
            f"got {actual_hash[:12]}... (possible tampering)"
        )


class RequireCEPHashMatchSpecs(BaseModel):
    """Specs for require CEP hash match phrase."""

    # inputs
    cep_id: UUID
    expected_hash: str
    # outputs
    satisfied: bool = False
    actual_hash: str | None = None
    mismatch_details: str | None = None


@canon_phrase(
    Operable.from_structure(RequireCEPHashMatchSpecs),
    inputs={"cep_id", "expected_hash"},
    outputs={"satisfied", "cep_id", "actual_hash", "mismatch_details"},
)
async def require_cep_hash_match(
    options: RequireCEPHashMatchSpecs,
    ctx: RequestContext,
) -> dict:
    """Require CEP content hash matches expected value.

    Gate pattern that validates CEP integrity by comparing hashes.
    Hash mismatch indicates potential tampering.

    Args:
        options: Options containing cep_id and expected_hash.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if hashes match.

    Raises:
        CEPNotFoundError: If CEP does not exist.
        CEPTenantMismatchError: If CEP belongs to different tenant.
        CEPHashMismatchError: If hashes do not match.
    """
    cep_id = options.cep_id
    expected_hash = options.expected_hash

    # Fetch CEP
    row = await select_one(
        "certified_evidence_packets",
        where={"id": cep_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise CEPNotFoundError(cep_id=cep_id)

    # Check tenant isolation
    if row["tenant_id"] != ctx.tenant_id:
        raise CEPTenantMismatchError(
            cep_id=cep_id,
            cep_tenant_id=row["tenant_id"],
            request_tenant_id=ctx.tenant_id,
        )

    # Compare hashes
    actual_hash = row.get("content_hash", "")

    if actual_hash != expected_hash:
        raise CEPHashMismatchError(
            cep_id=cep_id,
            expected_hash=expected_hash,
            actual_hash=actual_hash,
        )

    return {
        "satisfied": True,
        "cep_id": cep_id,
        "actual_hash": actual_hash,
        "mismatch_details": None,
    }
