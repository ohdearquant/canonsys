"""Derive scope minimization analysis.

Analyzes whether requested scope is minimal for the operation.

Regulatory context:
    - GDPR Art. 5(1)(c): Data minimization
    - HIPAA 164.502(b): Minimum necessary standard
    - CCPA 1798.100(c): Collection limitation
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveScopeMinimizationSpecs", "derive_scope_minimization"]


class DeriveScopeMinimizationSpecs(BaseModel):
    """Specs for derive scope minimization phrase."""

    # inputs
    requested_scope: list[str] = Field(
        ...,
        description="Scope items being requested",
    )
    minimum_scope: list[str] = Field(
        ...,
        description="Minimum scope required for the operation",
    )
    # outputs
    is_minimal: bool | None = None
    scope_size: int | None = None
    minimum_required: int | None = None
    excess_count: int | None = None
    recommendation: str | None = None


@canon_phrase(
    Operable.from_structure(DeriveScopeMinimizationSpecs),
    inputs={"requested_scope", "minimum_scope"},
    outputs={
        "is_minimal",
        "scope_size",
        "minimum_required",
        "excess_count",
        "recommendation",
    },
)
async def derive_scope_minimization(
    options: DeriveScopeMinimizationSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive whether requested scope is minimal for the operation.

    Compares the requested scope against the minimum scope required for the
    operation. Returns analysis of any excess scope that violates data
    minimization principles.

    Regulatory Citations:
        - GDPR Art. 5(1)(c): Personal data shall be adequate, relevant, and
          limited to what is necessary in relation to the purposes for which
          they are processed (data minimisation).
        - HIPAA 164.502(b): When using or disclosing PHI, covered entities
          must make reasonable efforts to limit PHI to the minimum necessary.
        - CCPA 1798.100(c): A business shall not collect additional categories
          of personal information without providing the consumer notice.

    Args:
        options: Scope minimization options (requested_scope, minimum_scope).
        ctx: Request context (tenant, actor).

    Returns:
        dict with is_minimal, scope_size, minimum_required, excess_count, recommendation.

    Examples:
        >>> options = DeriveScopeMinimizationSpecs(
        ...     requested_scope=["name", "email", "phone", "ssn", "dob"],
        ...     minimum_scope=["name", "email"],
        ... )
        >>> result = await derive_scope_minimization(options, ctx)
        >>> if not result["is_minimal"]:
        ...     raise ExcessiveScopeError(result["recommendation"])
    """
    requested_set = set(options.requested_scope)
    minimum_set = set(options.minimum_scope)

    # Items in requested but not in minimum = excess
    excess = requested_set - minimum_set

    # Check if minimum is actually a subset of requested
    missing_required = minimum_set - requested_set

    excess_count = len(excess)
    is_minimal = excess_count == 0 and len(missing_required) == 0

    # Build recommendation
    recommendation: str | None = None
    if excess_count > 0:
        excess_str = ", ".join(sorted(excess)[:5])
        if excess_count > 5:
            excess_str += f" and {excess_count - 5} more"
        recommendation = f"Remove excess scope items: {excess_str}"
    elif len(missing_required) > 0:
        missing_str = ", ".join(sorted(missing_required)[:5])
        recommendation = f"Scope missing required items: {missing_str}"

    return {
        "is_minimal": is_minimal,
        "scope_size": len(options.requested_scope),
        "minimum_required": len(options.minimum_scope),
        "excess_count": excess_count,
        "recommendation": recommendation,
    }
