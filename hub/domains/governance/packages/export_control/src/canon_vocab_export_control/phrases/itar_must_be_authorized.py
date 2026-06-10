"""Truth machine phrase: ITAR must be authorized.

Regulatory basis: ITAR (22 CFR Parts 120-130) requires State Department
authorization for export of defense articles, defense services, and
technical data. Unauthorized exports carry criminal penalties.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

from ..exceptions import ITARAuthorizationRequiredError

__all__ = ["itar_must_be_authorized"]


def itar_must_be_authorized(result: dict) -> None:
    """Assert ITAR authorization exists for defense export.

    Args:
        result: Result dict from verify_itar_authorization phrase.

    Raises:
        ITARAuthorizationRequiredError: If authorization required but not present.

    Truth Machine Semantics:
        If this function returns, the export is confirmed to have valid
        ITAR authorization (DSP-5, TAA, MLA, or exemption).

    Example:
        >>> result = await verify_itar_authorization(options, ctx)
        >>> itar_must_be_authorized(result)
        >>> # If we reach here, ITAR requirements are satisfied
    """
    if not result.get("authorized", False):
        raise ITARAuthorizationRequiredError(
            usml_category=result.get("usml_category", "UNKNOWN"),
            destination_country=result.get("destination_country", "UNKNOWN"),
        )
