"""OFAC sanctions clearance verification.

Verifies that an entity/transaction is not blocked by OFAC sanctions.
Critical for CS-090 (Export Control Override) - CRIMINAL LIABILITY exposure.

Compliance Context:
    - OFAC (Office of Foreign Assets Control) administers US sanctions
    - Violations carry criminal penalties up to $1M and 20 years imprisonment
    - Must screen all parties (individuals, entities, vessels, aircraft)
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import OFACEntityType

# Safety flag - MUST be explicitly set to allow mock export control checks
# OFAC violations carry criminal penalties up to $1M and 20 years imprisonment
ALLOW_MOCK_EXPORT_CONTROL = os.environ.get("ALLOW_MOCK_EXPORT_CONTROL", "").lower() in (
    "true",
    "1",
    "yes",
)

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyOFACSpecs", "verify_ofac_clearance"]


class VerifyOFACSpecs(BaseModel):
    """Specs for OFAC clearance verification phrase."""

    # inputs
    entity_name: str
    entity_type: OFACEntityType | str = OFACEntityType.INDIVIDUAL
    country_code: str | None = None
    # outputs
    cleared: bool = False
    screening_timestamp: datetime | None = None
    sanctions_list_version: str = ""
    match_score: int | None = None
    matched_program: str | None = None
    matched_sdn_id: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyOFACSpecs),
    inputs={"entity_name", "entity_type", "country_code"},
    outputs={
        "cleared",
        "entity_name",
        "entity_type",
        "screening_timestamp",
        "sanctions_list_version",
        "match_score",
        "matched_program",
        "matched_sdn_id",
    },
)
async def verify_ofac_clearance(
    options: VerifyOFACSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify entity is not on OFAC sanctions lists.

    Screens against:
    - SDN (Specially Designated Nationals) list
    - Consolidated Sanctions List
    - Sectoral Sanctions Identifications List

    Args:
        options: Verification options (entity_name, entity_type, country_code)
        ctx: Request context

    Returns:
        Dict with clearance status and screening details

    Example:
        >>> result = await verify_ofac_clearance(options, ctx)
        >>> if not result["cleared"]:
        ...     raise OFACSanctionsMatchError(...)
    """
    # FAIL-SAFE: Export control checks MUST NOT silently pass
    # OFAC violations are federal crimes - $1M fine and 20 years imprisonment
    # verify_* must return structured result, never raise
    if not ALLOW_MOCK_EXPORT_CONTROL:
        entity_type = options.entity_type
        if isinstance(entity_type, str):
            entity_type = OFACEntityType(entity_type)
        return {
            "cleared": False,
            "_not_implemented": True,
            "entity_name": options.entity_name,
            "entity_type": entity_type,
            "screening_timestamp": None,
            "sanctions_list_version": "",
            "match_score": None,
            "matched_program": None,
            "matched_sdn_id": None,
            "_reason": (
                "OFAC clearance verification not implemented. "
                "Production MUST integrate with Treasury OFAC SDN API or commercial screening service."
            ),
        }

    now = now_utc()

    # Normalize entity_type
    entity_type = options.entity_type
    if isinstance(entity_type, str):
        entity_type = OFACEntityType(entity_type)

    # MOCK ONLY - returns cleared for development/testing
    # Production deployment MUST integrate with:
    # - Treasury OFAC SDN API
    # - Commercial screening services (Dow Jones, LexisNexis, etc.)

    return {
        "cleared": True,
        "_mock": True,  # Flag indicating this is mock data
        "entity_name": options.entity_name,
        "entity_type": entity_type,
        "screening_timestamp": now,
        "sanctions_list_version": "MOCK_SDN_LIST",
        "match_score": None,
        "matched_program": None,
        "matched_sdn_id": None,
    }
