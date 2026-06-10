"""Verify AAL equivalence mapping.

Complete vertical slice:
- Compares source and target assurance levels
- Returns whether source meets or exceeds target
- Provides gap analysis and recommendations

Regulatory context:
    - NIST SP 800-63 (Authenticator Assurance Levels)
    - FedRAMP (AAL requirements by impact level)
    - eIDAS (Level of Assurance mapping)
    - ISO 29115 (Entity authentication assurance)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import AALLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyAssuranceEquivalentSpecs", "verify_assurance_equivalent"]


# AAL level hierarchy
_AAL_LEVELS: dict[AALLevel, int] = {
    "aal1": 1,
    "aal2": 2,
    "aal3": 3,
}

# Recommendations for each gap scenario
_GAP_RECOMMENDATIONS: dict[int, str | None] = {
    0: None,
    1: "Add second authentication factor (TOTP, SMS, push notification)",
    2: "Upgrade to hardware-bound authenticator (FIDO2, PIV, hardware key)",
}


class VerifyAssuranceEquivalentSpecs(BaseModel):
    """Specs for verify assurance equivalent phrase."""

    # inputs
    source_level: AALLevel
    target_level: AALLevel
    # outputs
    equivalent: bool | None = None
    gap: int | None = None
    recommendation: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyAssuranceEquivalentSpecs),
    inputs={"source_level", "target_level"},
    outputs={"source_level", "target_level", "equivalent", "gap", "recommendation"},
)
async def verify_assurance_equivalent(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify source AAL is equivalent to or higher than target.

    Compares authenticator assurance levels per NIST SP 800-63B:
    - AAL3 > AAL2 > AAL1
    - Source is equivalent if source_level >= target_level

    Regulatory citations:
    - NIST SP 800-63B Section 4: Authenticator assurance levels
    - FedRAMP: AAL2 minimum for Moderate, AAL3 for High
    - eIDAS: Substantial (AAL2) and High (AAL3) LoA
    - ISO 29115: Entity authentication assurance framework

    Args:
        options: Verification options (source_level, target_level) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with source_level, target_level, equivalent, gap, recommendation
    """
    source_level: AALLevel = options.source_level
    target_level: AALLevel = options.target_level

    # Get numeric levels
    source_value = _AAL_LEVELS[source_level]
    target_value = _AAL_LEVELS[target_level]

    # Calculate gap (positive = source is lower)
    gap = max(0, target_value - source_value)

    # Determine equivalence
    equivalent = source_value >= target_value

    # Get recommendation if there's a gap
    recommendation = _get_gap_recommendation(gap)

    return {
        "source_level": source_level,
        "target_level": target_level,
        "equivalent": equivalent,
        "gap": gap,
        "recommendation": recommendation,
    }


def _get_gap_recommendation(gap: int) -> str | None:
    """Get recommendation for closing the AAL gap."""
    if gap <= 0:
        return None
    return _GAP_RECOMMENDATIONS.get(gap)
