"""Require that business justification is fully documented.

Complete vertical slice:
- Validates justification document has all required elements
- Wraps validate_business_justification with gate semantics
- Raises JustificationIncompleteError if elements are missing

Regulatory: SOX Section 404 - Documentation of business decisions
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import JustificationIncompleteError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "JustificationIncompleteError",
    "RequireJustificationDocumentedSpecs",
    "require_justification_documented",
]


class RequireJustificationDocumentedSpecs(BaseModel):
    """Specs for require justification documented phrase."""

    # inputs
    justification_doc_id: UUID
    # outputs
    satisfied: bool = False
    has_reason: bool | None = None
    has_impact: bool | None = None
    has_plan: bool | None = None
    has_owner: bool | None = None


@canon_phrase(
    Operable.from_structure(RequireJustificationDocumentedSpecs),
    inputs={"justification_doc_id"},
    outputs={
        "satisfied",
        "justification_doc_id",
        "has_reason",
        "has_impact",
        "has_plan",
        "has_owner",
    },
)
async def require_justification_documented(
    options: RequireJustificationDocumentedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that business justification is fully documented.

    Gate pattern that enforces justification completeness. Wraps
    validate_business_justification with raise-on-failure semantics.

    Args:
        options: Options containing justification_doc_id.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if justification is complete.

    Raises:
        JustificationIncompleteError: If required elements are missing.

    Regulatory citations:
        - SOX Section 404: Documentation of business decisions
        - COSO Framework: Risk assessment and response documentation
        - IIA Standards: Audit trail requirements
    """
    from .validate_business_justification import (
        ValidateBusinessJustificationSpecs,
        validate_business_justification,
    )

    validate_options = ValidateBusinessJustificationSpecs(
        justification_doc_id=options.justification_doc_id,
    )
    result = await validate_business_justification(validate_options, ctx)

    if not result["valid"]:
        raise JustificationIncompleteError(
            missing_elements=result["missing_elements"],
        )

    return {
        "satisfied": True,
        "justification_doc_id": options.justification_doc_id,
        "has_reason": result["has_reason"],
        "has_impact": result["has_impact"],
        "has_plan": result["has_plan"],
        "has_owner": result["has_owner"],
    }
