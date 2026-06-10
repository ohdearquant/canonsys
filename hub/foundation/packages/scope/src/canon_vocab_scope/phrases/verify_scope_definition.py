"""Verify scope definition is properly bounded.

Checks that scope definitions have explicit bounds and are not vague.

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization
    - SOC 2 CC6.1: Logical access controls
    - ISO 27001 A.9.1.1: Access control policy
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyScopeDefinitionSpecs", "verify_scope_definition"]


class VerifyScopeDefinitionSpecs(BaseModel):
    """Specs for verify scope definition phrase."""

    # inputs
    scope_doc_id: UUID
    scope_type: str = "unknown"
    targets: list[str] | None = None
    exclusions: list[str] | None = None
    # outputs
    defined: bool | None = None
    has_targets: bool | None = None
    has_exclusions: bool | None = None
    is_explicit: bool | None = None


@canon_phrase(
    Operable.from_structure(VerifyScopeDefinitionSpecs),
    inputs={"scope_doc_id", "scope_type", "targets", "exclusions"},
    outputs={"defined", "scope_type", "has_targets", "has_exclusions", "is_explicit"},
)
async def verify_scope_definition(
    options: VerifyScopeDefinitionSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a scope is properly defined with explicit bounds.

    Checks that the scope document contains required elements for compliance:
    - Has explicit targets (not just "ALL" or empty)
    - Has a defined type (users, resources, data, etc.)
    - Indicates whether exclusions are defined

    This prevents scope definitions that are too vague to be enforceable,
    such as "access to all company data" or "broad user base."

    Regulatory Citations:
        - GDPR Art. 5(1)(c): Personal data shall be limited to what is necessary.
          Vague scope definitions cannot demonstrate necessity.
        - SOC 2 CC6.1: Logical access controls require explicit scope definitions
          that can be verified and audited.
        - ISO 27001 A.9.1.1: Access control policies must clearly define scope
          to enable consistent enforcement.

    Args:
        options: Definition verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with defined, scope_type, has_targets, has_exclusions, is_explicit.
    """
    targets = options.targets or []
    exclusions = options.exclusions or []

    vague_indicators = {"all", "broad", "*", "any", "everything"}
    is_explicit = True

    if not targets:
        is_explicit = False
    else:
        for target in targets:
            if target.lower().strip() in vague_indicators:
                is_explicit = False
                break

    has_targets = len(targets) > 0
    has_exclusions = len(exclusions) > 0
    defined = has_targets and is_explicit

    return {
        "defined": defined,
        "scope_type": options.scope_type,
        "has_targets": has_targets,
        "has_exclusions": has_exclusions,
        "is_explicit": is_explicit,
    }
