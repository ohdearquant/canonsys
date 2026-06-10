"""Require that two identities are distinct for Segregation of Duties.

Complete vertical slice:
- Compares two identity IDs
- Raises RequirementNotMetError if same person
- Hard gate for SoD compliance

Regulatory:
    - SOX Section 404: Segregation of duties in financial controls
    - COSO Framework: Control environment and control activities
    - SOC 2 CC5.1: Control activities - segregation of duties
    - PCI DSS 6.4.2: Separation of duties between dev and prod
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireDistinctIdentitiesSpecs", "require_distinct_identities"]


class RequireDistinctIdentitiesSpecs(BaseModel):
    """Specs for require distinct identities phrase."""

    # inputs
    identity_a: UUID
    identity_b: UUID
    role_a: str
    role_b: str
    # outputs (defaults required for instantiation with inputs only)
    distinct: bool = False
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireDistinctIdentitiesSpecs),
    inputs={"identity_a", "identity_b", "role_a", "role_b"},
    outputs={"distinct", "identity_a", "identity_b", "role_a", "role_b", "reason"},
)
async def require_distinct_identities(
    options: RequireDistinctIdentitiesSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that two identities are distinct for Segregation of Duties.

    Verifies that two actions requiring segregation were performed by
    different people. This is a hard gate - if the same person performed
    both actions, the operation cannot proceed.

    Common use cases:
        - Preparer != Approver (financial transactions)
        - Requestor != Authorizer (access grants)
        - Developer != Deployer (change management)
        - Maker != Checker (dual control)

    Args:
        options: Options containing identity_a, identity_b, role_a, role_b
        ctx: Request context (unused, for API consistency)

    Returns:
        Dict with distinct=True and identity details if compliant.

    Raises:
        RequirementNotMetError: If identities are the same (SoD violation)
    """
    identity_a: UUID = options.identity_a
    identity_b: UUID = options.identity_b
    role_a = options.role_a
    role_b = options.role_b

    # SoD check: identities must be different
    if identity_a == identity_b:
        raise RequirementNotMetError(
            requirement="distinct_identities",
            reason=(
                f"Segregation of Duties violation: {role_a} and {role_b} "
                f"must be different people (both are identity {identity_a})"
            ),
        )

    return {
        "distinct": True,
        "identity_a": identity_a,
        "identity_b": identity_b,
        "role_a": role_a,
        "role_b": role_b,
        "reason": f"Segregation of Duties verified: {role_a} != {role_b}",
    }
