"""Derive exfiltration risk band based on query row count.

Classifies data access volume to identify potential data exfiltration.

Regulatory Context:
    - SOC 2 CC6.7: Transmission restriction
    - ISO 27001 A.13.2.1: Information transfer policies
    - PCI DSS 7.1: Access limitation
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import RiskBand
from .constants import THRESHOLD_HIGH, THRESHOLD_LOW, THRESHOLD_MEDIUM

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveRowsReadBandSpecs", "derive_rows_read_band"]


class DeriveRowsReadBandSpecs(BaseModel):
    """Specs for rows read band derivation phrase."""

    # inputs
    query_id: UUID
    rows_read: int
    # outputs
    band: RiskBand | None = None
    threshold_low: int | None = None
    threshold_high: int | None = None
    is_bulk_query: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveRowsReadBandSpecs),
    inputs={"query_id", "rows_read"},
    outputs={"band", "rows_read", "threshold_low", "threshold_high", "is_bulk_query"},
)
async def derive_rows_read_band(
    options: DeriveRowsReadBandSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive exfiltration risk band based on query row count.

    Classifies the data access volume to identify potential data exfiltration.
    High-volume queries may require additional approval or rate limiting.

    Regulatory Citations:
        - SOC 2 CC6.7: "The entity restricts the transmission, movement,
          and removal of information to authorized internal and external users."
        - ISO 27001 A.13.2.1: "Formal transfer policies, procedures and
          controls shall be in place to protect information transfer."
        - PCI DSS 7.1: "Limit access to system components and cardholder
          data to only those individuals whose job requires such access."

    Args:
        options: Derivation options (query_id, rows_read)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with band, rows_read, threshold_low, threshold_high, is_bulk_query

    Thresholds:
        - low: < 1,000 rows (normal operational access)
        - medium: 1,000 - 10,000 rows (elevated monitoring)
        - high: 10,000 - 100,000 rows (requires justification)
        - critical: >= 100,000 rows (bulk access, requires approval)
    """
    query_id = options.query_id
    rows_read = options.rows_read
    _ = query_id  # For audit logging

    # Classify based on thresholds
    if rows_read < THRESHOLD_LOW:
        band: RiskBand = "low"
    elif rows_read < THRESHOLD_MEDIUM:
        band = "medium"
    elif rows_read < THRESHOLD_HIGH:
        band = "high"
    else:
        band = "critical"

    is_bulk_query = rows_read >= THRESHOLD_MEDIUM

    return {
        "band": band,
        "rows_read": rows_read,
        "threshold_low": THRESHOLD_LOW,
        "threshold_high": THRESHOLD_HIGH,
        "is_bulk_query": is_bulk_query,
    }
