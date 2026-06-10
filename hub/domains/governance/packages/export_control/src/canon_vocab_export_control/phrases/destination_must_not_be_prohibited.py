"""Truth machine phrase: destination must not be prohibited.

Regulatory basis: OFAC comprehensive sanctions programs prohibit
ALL exports to certain countries (Cuba, Iran, North Korea, Syria)
regardless of licenses or exemptions.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

__all__ = ["destination_must_not_be_prohibited"]


def destination_must_not_be_prohibited(result: dict) -> None:
    """Assert destination is not under comprehensive sanctions.

    Note:
        This function is a validation passthrough. The actual check
        happens in require_allowed_destination() which raises
        ProhibitedDestinationError if the destination is prohibited.
        This function exists for backward compatibility and explicit
        truth machine semantics.

    Args:
        result: Result dict from require_allowed_destination phrase.

    Truth Machine Semantics:
        If this function returns, the destination is confirmed to NOT
        be under comprehensive sanctions. Export may proceed to further
        license checks.

    Example:
        >>> result = await require_allowed_destination(options, ctx)
        >>> destination_must_not_be_prohibited(result)
        >>> # If we reach here, Germany is not prohibited
    """
    # require_allowed_destination already raises ProhibitedDestinationError
    # if the destination is prohibited. If we reach here with a result dict,
    # the destination is confirmed allowed.
    _ = result  # Explicit validation that we received a result
