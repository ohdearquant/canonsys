"""Require scope boundaries within authorized limits.

Complete vertical slice:
- Validates scope definition is properly bounded and explicit
- Wraps verify_scope_definition with gate semantics
- Raises VagueScopeError if scope is not properly defined

Regulatory: GDPR Art. 5(1)(c) - Data minimization
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import VagueScopeError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireScopeValidSpecs",
    "VagueScopeError",
    "require_scope_valid",
]


class RequireScopeValidSpecs(BaseModel):
    """Specs for require scope valid phrase."""

    # inputs
    scope_doc_id: UUID
    scope_type: str = "unknown"
    targets: list[str] | None = None
    exclusions: list[str] | None = None
    # outputs
    satisfied: bool = False
    has_targets: bool | None = None
    has_exclusions: bool | None = None
    is_explicit: bool | None = None


@canon_phrase(
    Operable.from_structure(RequireScopeValidSpecs),
    inputs={"scope_doc_id", "scope_type", "targets", "exclusions"},
    outputs={
        "satisfied",
        "scope_doc_id",
        "scope_type",
        "has_targets",
        "has_exclusions",
        "is_explicit",
    },
)
async def require_scope_valid(
    options: RequireScopeValidSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that scope boundaries are within authorized limits.

    Gate pattern that enforces scope definition requirements.
    Wraps verify_scope_definition with raise-on-failure semantics.

    Args:
        options: Options containing scope_doc_id, scope_type, targets, exclusions.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if scope is properly defined.

    Raises:
        VagueScopeError: If scope definition is too vague or missing targets.

    Regulatory citations:
        - GDPR Art. 5(1)(c): Data minimization - scope must be explicit
        - SOC 2 CC6.1: Logical access controls require explicit scope
        - ISO 27001 A.9.1.1: Access control policy must define scope
        - HIPAA 164.502(b): Minimum necessary standard
    """
    from .verify_scope_definition import (
        VerifyScopeDefinitionSpecs,
        verify_scope_definition,
    )

    verify_options = VerifyScopeDefinitionSpecs(
        scope_doc_id=options.scope_doc_id,
        scope_type=options.scope_type,
        targets=options.targets,
        exclusions=options.exclusions,
    )
    result = await verify_scope_definition(verify_options, ctx)

    if not result["defined"]:
        raise VagueScopeError(
            scope_doc_id=options.scope_doc_id,
            scope_type=options.scope_type,
        )

    return {
        "satisfied": True,
        "scope_doc_id": options.scope_doc_id,
        "scope_type": result["scope_type"],
        "has_targets": result["has_targets"],
        "has_exclusions": result["has_exclusions"],
        "is_explicit": result["is_explicit"],
    }
