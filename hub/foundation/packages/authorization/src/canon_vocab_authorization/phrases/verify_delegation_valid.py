"""Verify that a delegation chain is valid.

Complete vertical slice:
- Checks delegation chain from delegatee to original authority
- Validates each link in the chain
- Returns verification result (does not raise)

Regulatory:
    - SOX Section 404 (Authority and delegation controls)
    - SOC 2 CC6.1 (Logical access controls)
    - ISO 27001 A.9.2.3 (Management of privileged access rights)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyDelegationValidSpecs", "verify_delegation_valid"]


class VerifyDelegationValidSpecs(BaseModel):
    """Specs for verify delegation valid phrase."""

    # inputs
    delegatee_id: UUID
    delegated_role: str
    max_depth: int = 3  # Maximum chain depth to traverse
    # outputs (defaults required for instantiation with inputs only)
    valid: bool = False
    delegation_chain: tuple[UUID, ...] | None = None
    chain_depth: int = 0
    original_authority: UUID | None = None
    expires_at: datetime | None = None
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyDelegationValidSpecs),
    inputs={"delegatee_id", "delegated_role", "max_depth"},
    outputs={
        "valid",
        "delegatee_id",
        "delegated_role",
        "delegation_chain",
        "chain_depth",
        "original_authority",
        "expires_at",
        "checked_at",
        "reason",
    },
)
async def verify_delegation_valid(
    options: VerifyDelegationValidSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a delegation chain is valid.

    Traverses the delegation chain from the delegatee back to the original
    authority, validating each link. A delegation is valid if:
    - All links in the chain are active
    - No link has expired
    - The chain doesn't exceed max_depth
    - The original authority has the delegated role

    Args:
        options: Options containing delegatee_id, delegated_role, max_depth
        ctx: Request context with connection

    Returns:
        Dict with validation status and chain metadata.
    """
    now = now_utc()
    delegatee_id: UUID = options.delegatee_id
    delegated_role = options.delegated_role.upper()
    max_depth = options.max_depth

    # Recursive CTE to traverse delegation chain
    query = """
        WITH RECURSIVE delegation_chain AS (
            -- Base case: direct delegation to the delegatee
            SELECT
                delegator_id,
                delegatee_id,
                delegated_role,
                expires_at,
                1 as depth
            FROM approval_delegations
            WHERE delegatee_id = $1
              AND delegated_role = $2
              AND is_active = true
              AND (expires_at IS NULL OR expires_at > $3)

            UNION ALL

            -- Recursive case: follow the chain
            SELECT
                ad.delegator_id,
                ad.delegatee_id,
                ad.delegated_role,
                LEAST(dc.expires_at, ad.expires_at) as expires_at,
                dc.depth + 1
            FROM approval_delegations ad
            INNER JOIN delegation_chain dc ON dc.delegator_id = ad.delegatee_id
            WHERE ad.delegated_role = $2
              AND ad.is_active = true
              AND (ad.expires_at IS NULL OR ad.expires_at > $3)
              AND dc.depth < $4
        )
        SELECT delegator_id, delegatee_id, expires_at, depth
        FROM delegation_chain
        ORDER BY depth
    """

    rows = await ctx.conn.fetch(query, delegatee_id, delegated_role, now, max_depth)

    if not rows:
        return {
            "valid": False,
            "delegatee_id": delegatee_id,
            "delegated_role": delegated_role,
            "delegation_chain": None,
            "chain_depth": 0,
            "original_authority": None,
            "expires_at": None,
            "checked_at": now,
            "reason": f"No active delegation found for role '{delegated_role}'",
        }

    # Build chain and find original authority
    chain: list[UUID] = [delegatee_id]
    earliest_expiry: datetime | None = None

    for row in rows:
        chain.append(row["delegator_id"])
        if row["expires_at"]:
            if earliest_expiry is None or row["expires_at"] < earliest_expiry:
                earliest_expiry = row["expires_at"]

    original_authority = chain[-1]
    chain_depth = len(rows)

    # Verify original authority actually has the role
    authority_query = """
        SELECT 1 FROM actor_roles
        WHERE actor_id = $1
          AND role = $2
          AND is_active = true
          AND (expires_at IS NULL OR expires_at > $3)
        LIMIT 1
    """
    authority_row = await ctx.conn.fetchrow(
        authority_query, original_authority, delegated_role, now
    )

    if not authority_row:
        return {
            "valid": False,
            "delegatee_id": delegatee_id,
            "delegated_role": delegated_role,
            "delegation_chain": tuple(chain),
            "chain_depth": chain_depth,
            "original_authority": original_authority,
            "expires_at": earliest_expiry,
            "checked_at": now,
            "reason": f"Original authority {original_authority} no longer has role '{delegated_role}'",
        }

    return {
        "valid": True,
        "delegatee_id": delegatee_id,
        "delegated_role": delegated_role,
        "delegation_chain": tuple(chain),
        "chain_depth": chain_depth,
        "original_authority": original_authority,
        "expires_at": earliest_expiry,
        "checked_at": now,
        "reason": None,
    }
