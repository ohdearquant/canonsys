"""Require that export destination is allowed.

Hard requirement for exports - raises exception for comprehensively sanctioned countries.

Compliance Context:
    - Certain countries are comprehensively sanctioned (Cuba, Iran, North Korea, Syria)
    - NO exports permitted regardless of license
    - Automatic hard gate
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ProhibitedDestinationError
from ..types import PROHIBITED_DESTINATIONS, PROHIBITION_INFO

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireAllowedDestinationSpecs", "require_allowed_destination"]


class RequireAllowedDestinationSpecs(BaseModel):
    """Specs for require allowed destination phrase."""

    # inputs
    country_code: str
    # outputs (minimal - this is a gate that either passes or raises)


@canon_phrase(
    Operable.from_structure(RequireAllowedDestinationSpecs),
    inputs={"country_code"},
    outputs={"country_code"},
)
async def require_allowed_destination(
    options: RequireAllowedDestinationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that destination is allowed for export.

    Raises ProhibitedDestinationError if destination is comprehensively
    sanctioned (Cuba, Iran, North Korea, Syria).

    Args:
        options: Options containing country_code
        ctx: Request context

    Returns:
        Dict with country_code if destination is allowed.

    Raises:
        ProhibitedDestinationError: If destination is prohibited.

    Example:
        >>> result = await require_allowed_destination(options, ctx)  # Allowed
        >>> result["country_code"]
        'DE'
        >>> await require_allowed_destination({"country_code": "IR"}, ctx)  # Raises
        ProhibitedDestinationError: Export to Iran prohibited under OFAC...
    """
    country_upper = options.country_code.upper().strip()

    if country_upper in PROHIBITED_DESTINATIONS:
        name, basis = PROHIBITION_INFO.get(country_upper, (None, "Comprehensive Sanctions"))
        raise ProhibitedDestinationError(
            country_code=country_upper,
            country_name=name,
            prohibition_basis=basis,
        )

    return {"country_code": country_upper}
