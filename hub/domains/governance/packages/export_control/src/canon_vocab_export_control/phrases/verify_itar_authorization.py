"""ITAR authorization verification.

Verifies State Department authorization for defense articles/services.
Required for USML-controlled items.

Compliance Context:
    - ITAR (International Traffic in Arms Regulations) controls defense items
    - Administered by DDTC (Directorate of Defense Trade Controls)
    - Criminal penalties for unauthorized exports
"""

from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ITARAuthorizationType

# Safety flag - MUST be explicitly set to allow mock export control checks
# ITAR violations carry criminal penalties
ALLOW_MOCK_EXPORT_CONTROL = os.environ.get("ALLOW_MOCK_EXPORT_CONTROL", "").lower() in (
    "true",
    "1",
    "yes",
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyITARSpecs", "verify_itar_authorization"]


class VerifyITARSpecs(BaseModel):
    """Specs for ITAR authorization verification phrase."""

    # inputs
    usml_category: str
    destination_country: str
    defense_service: bool = False
    technical_data: bool = False
    # outputs
    authorized: bool = False
    authorization_type: ITARAuthorizationType | None = None
    ddtc_reference: str | None = None
    expiry_date: date | None = None
    provisos: tuple[str, ...] = ()


@canon_phrase(
    Operable.from_structure(VerifyITARSpecs),
    inputs={
        "usml_category",
        "destination_country",
        "defense_service",
        "technical_data",
    },
    outputs={
        "authorized",
        "authorization_type",
        "ddtc_reference",
        "usml_category",
        "destination_country",
        "expiry_date",
        "provisos",
    },
)
async def verify_itar_authorization(
    options: VerifyITARSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify ITAR authorization for defense article/service export.

    Args:
        options: Verification options (usml_category, destination, flags)
        ctx: Request context

    Returns:
        Dict with authorization status and details

    Example:
        >>> result = await verify_itar_authorization(options, ctx)
        >>> if not result["authorized"]:
        ...     raise ITARAuthorizationRequiredError(
        ...         result["usml_category"], result["destination_country"]
        ...     )
    """
    # FAIL-SAFE: Export control checks MUST NOT silently pass
    # ITAR violations are federal crimes
    # verify_* must return structured result, never raise
    if not ALLOW_MOCK_EXPORT_CONTROL:
        return {
            "authorized": False,
            "_not_implemented": True,
            "authorization_type": None,
            "ddtc_reference": None,
            "usml_category": options.usml_category.upper(),
            "destination_country": options.destination_country.upper(),
            "expiry_date": None,
            "provisos": (),
            "_reason": (
                "ITAR authorization verification not implemented. "
                "Production MUST integrate with DDTC or internal authorization registry."
            ),
        }

    # MOCK ONLY - returns authorized for development/testing
    # Production deployment MUST:
    # - Query internal ITAR license database
    # - Verify license covers specific USML items
    # - Check license conditions/provisos
    # - Validate against destination restrictions

    return {
        "authorized": True,
        "_mock": True,  # Flag indicating this is mock data
        "authorization_type": None,
        "ddtc_reference": None,
        "usml_category": options.usml_category.upper(),
        "destination_country": options.destination_country.upper(),
        "expiry_date": None,
        "provisos": (),
    }
