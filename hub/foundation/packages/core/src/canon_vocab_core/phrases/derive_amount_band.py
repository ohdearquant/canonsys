"""Derive amount band phrase.

Anti-gaming primitive for amount classification.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import AmountBandConfig

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveAmountBandSpecs", "derive_amount_band"]


class DeriveAmountBandSpecs(BaseModel):
    """Specs for derive amount band phrase.

    Compliance Context:
        - Finance surfaces (CS-009, CS-056-064): Amount classification determines approval chain
        - Anti-gaming: Amount band MUST be derived, never user-asserted
    """

    # inputs
    amount: Decimal
    # outputs
    band: str
    threshold: Decimal
    next_band_at: Decimal | None = None
    config_version: str


@canon_phrase(
    Operable.from_structure(DeriveAmountBandSpecs),
    inputs={"amount"},
    outputs={"band", "amount", "threshold", "next_band_at", "config_version"},
)
async def derive_amount_band(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Derive amount band from actual amount value.

    This is an anti-gaming primitive. Amount bands MUST be derived from
    the actual amount, never accepted as user input.

    Args:
        options: Derivation options (amount)
        ctx: Request context

    Returns:
        dict with classified band and metadata

    Raises:
        ValueError: If amount is negative.

    Example:
        >>> result = await derive_amount_band({"amount": Decimal("75000")}, ctx)
        >>> result["band"]
        'HIGH'
        >>> result["next_band_at"]
        Decimal('250000')
    """
    amount: Decimal = options.amount

    if amount < 0:
        raise ValueError(f"Amount cannot be negative: {amount}")

    config = AmountBandConfig.default()

    # Find the highest band where amount >= threshold
    selected_band = config.bands[0][0]
    selected_threshold = config.bands[0][1]
    next_band_at: Decimal | None = None

    for i, (band_name, threshold) in enumerate(config.bands):
        if amount >= threshold:
            selected_band = band_name
            selected_threshold = threshold
            # Check if there's a next band
            if i + 1 < len(config.bands):
                next_band_at = config.bands[i + 1][1]
            else:
                next_band_at = None

    # Generate config version hash for audit
    config_str = str(config.bands)
    config_version = hashlib.sha256(config_str.encode()).hexdigest()[:8]

    return {
        "band": selected_band,
        "amount": amount,
        "threshold": selected_threshold,
        "next_band_at": next_band_at,
        "config_version": config_version,
    }
