"""Require value within limit phrase.

Verifies a numeric value is within a threshold limit.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ValueExceedsLimitError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireValueWithinLimitSpecs", "require_value_within_limit"]


class RequireValueWithinLimitSpecs(BaseModel):
    """Specs for require value within limit phrase.

    Regulatory:
        - BSA/AML (Bank Secrecy Act) - CTR thresholds
        - SOX Section 404 - Internal controls
        - COSO Framework - Authorization limits
    """

    # inputs
    value: Decimal
    limit: Decimal
    description: str | None = None
    # outputs
    headroom: Decimal


@canon_phrase(
    Operable.from_structure(RequireValueWithinLimitSpecs),
    inputs={"value", "limit", "description"},
    outputs={"value", "limit", "headroom", "description"},
)
async def require_value_within_limit(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Require that a numeric value is within a threshold limit.

    Raises ValueExceedsLimitError if value > limit, requiring
    escalation/approval before proceeding.

    Use cases:
        - Wire transfer > $10,000 requires approval (BSA/AML)
        - Expense > policy limit requires manager sign-off
        - Discount > X% requires pricing committee review
        - Headcount change > N requires exec approval

    Args:
        options: Check options (value, limit, description)
        ctx: Request context

    Returns:
        dict with value, limit, headroom, description

    Raises:
        ValueExceedsLimitError: If value > limit.
    """
    value = options.get("value")
    limit = options.get("limit")
    description = options.get("description")

    # Convert to Decimal for precision (money values)
    value_dec = Decimal(str(value))
    limit_dec = Decimal(str(limit))

    # Check if value exceeds limit
    if value_dec > limit_dec:
        raise ValueExceedsLimitError(
            value=value_dec,
            limit=limit_dec,
            description=description,
        )

    # Calculate headroom (remaining before limit)
    headroom = limit_dec - value_dec

    return {
        "value": value_dec,
        "limit": limit_dec,
        "headroom": headroom,
        "description": description,
    }
