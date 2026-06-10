"""BIS export license verification.

Verifies Bureau of Industry and Security (Commerce Dept) export approval.
Required for EAR-controlled items.

Compliance Context:
    - EAR (Export Administration Regulations) control dual-use items
    - Requires export license for controlled ECCN items to certain destinations
    - License exceptions may apply (e.g., TMP, BAG, GBS)
"""

from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import BISLicenseType

# Safety flag - MUST be explicitly set to allow mock export control checks
# BIS/EAR violations carry criminal penalties
ALLOW_MOCK_EXPORT_CONTROL = os.environ.get("ALLOW_MOCK_EXPORT_CONTROL", "").lower() in (
    "true",
    "1",
    "yes",
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyBISSpecs", "verify_bis_approval"]


class VerifyBISSpecs(BaseModel):
    """Specs for BIS approval verification phrase."""

    # inputs
    eccn: str
    destination_country: str
    end_use: str | None = None
    end_user: str | None = None
    # outputs
    approved: bool = False
    license_number: str | None = None
    license_type: BISLicenseType = BISLicenseType.NO_LICENSE_REQUIRED
    expiry_date: date | None = None
    exception_code: str | None = None
    end_user_verified: bool = False


@canon_phrase(
    Operable.from_structure(VerifyBISSpecs),
    inputs={"eccn", "destination_country", "end_use", "end_user"},
    outputs={
        "approved",
        "license_number",
        "license_type",
        "eccn",
        "destination_country",
        "expiry_date",
        "exception_code",
        "end_user_verified",
    },
)
async def verify_bis_approval(
    options: VerifyBISSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify BIS/EAR export approval for controlled item.

    Checks if export requires license and if valid license exists.

    Args:
        options: Verification options (eccn, destination, end_use, end_user)
        ctx: Request context

    Returns:
        Dict with approval status and license details

    Example:
        >>> result = await verify_bis_approval(options, ctx)
        >>> if not result["approved"]:
        ...     raise BISLicenseRequiredError(result["eccn"], result["destination_country"])
    """
    # FAIL-SAFE: Export control checks MUST NOT silently pass
    # BIS/EAR violations are federal crimes
    # verify_* must return structured result, never raise
    if not ALLOW_MOCK_EXPORT_CONTROL:
        return {
            "approved": False,
            "_not_implemented": True,
            "license_number": None,
            "license_type": BISLicenseType.NO_LICENSE_REQUIRED,
            "eccn": options.eccn,
            "destination_country": options.destination_country.upper(),
            "expiry_date": None,
            "exception_code": None,
            "end_user_verified": False,
            "_reason": (
                "BIS approval verification not implemented. "
                "Production MUST integrate with BIS SNAP-R or internal license registry."
            ),
        }

    # MOCK ONLY - returns approved for development/testing
    # Production deployment MUST:
    # - Query internal license database
    # - Check ECCN against Commerce Control List
    # - Evaluate license exceptions (Part 740)
    # - Consider destination country controls

    return {
        "approved": True,
        "_mock": True,  # Flag indicating this is mock data
        "license_number": None,
        "license_type": BISLicenseType.NO_LICENSE_REQUIRED,
        "eccn": options.eccn,
        "destination_country": options.destination_country.upper(),
        "expiry_date": None,
        "exception_code": None,
        "end_user_verified": options.end_user is not None,
    }
