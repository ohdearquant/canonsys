"""Truth machine phrase: OFAC must be cleared.

Regulatory basis: OFAC sanctions (50 U.S.C. 1702) prohibit transactions
with Specially Designated Nationals (SDN) and blocked persons/entities.
Criminal penalties: Up to $1M fine and 20 years imprisonment.

WARNING: Export control violations carry CRIMINAL penalties.
"""

from __future__ import annotations

from ..exceptions import OFACSanctionsMatchError
from ..types import OFACEntityType

__all__ = ["ofac_must_be_cleared"]


def ofac_must_be_cleared(result: dict) -> None:
    """Assert entity is not on OFAC sanctions lists.

    Args:
        result: Result dict from verify_ofac_clearance phrase.

    Raises:
        OFACSanctionsMatchError: If entity matches sanctions list.

    Truth Machine Semantics:
        If this function returns, the entity is confirmed to NOT be
        on OFAC sanctions lists. Transaction may proceed.

    Example:
        >>> result = await verify_ofac_clearance(options, ctx)
        >>> ofac_must_be_cleared(result)
        >>> # If we reach here, entity passed OFAC screening
    """
    if not result.get("cleared", False):
        entity_type = result.get("entity_type", OFACEntityType.INDIVIDUAL)
        if isinstance(entity_type, OFACEntityType):
            entity_type_value = entity_type.value
        else:
            entity_type_value = str(entity_type)

        raise OFACSanctionsMatchError(
            entity_name=result.get("entity_name", "UNKNOWN"),
            entity_type=entity_type_value,
            matched_program=result.get("matched_program"),
            matched_sdn_id=result.get("matched_sdn_id"),
            match_score=result.get("match_score"),
        )
