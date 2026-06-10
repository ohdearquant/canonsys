"""Truth machine phrase: BIS license must be valid.

Regulatory basis: Export Administration Regulations (15 CFR Parts 730-774)
require valid license for controlled ECCN items exported to certain
destinations, unless a license exception applies.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

from ..exceptions import BISLicenseRequiredError

__all__ = ["bis_license_must_be_valid"]


def bis_license_must_be_valid(result: dict) -> None:
    """Assert BIS export license is valid for controlled item.

    Args:
        result: Result dict from verify_bis_approval phrase.

    Raises:
        BISLicenseRequiredError: If license required but not valid.

    Truth Machine Semantics:
        If this function returns, the export is confirmed to have valid
        BIS authorization (license, exception, or no license required).

    Example:
        >>> result = await verify_bis_approval(options, ctx)
        >>> bis_license_must_be_valid(result)
        >>> # If we reach here, BIS requirements are satisfied
    """
    if not result.get("approved", False):
        raise BISLicenseRequiredError(
            eccn=result.get("eccn") or "UNKNOWN",
            destination_country=result.get("destination_country", "UNKNOWN"),
        )
