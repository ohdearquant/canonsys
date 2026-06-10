"""Derive appropriate write acceptance mode for a system.

Evaluates system health indicators to determine write validation level.

Regulatory Context:
    - SOC 2 CC7.4: Incident response
    - ISO 27001 A.17.2.1: Redundancy requirements
    - PCI DSS 10.7: Audit trail retention
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import WriteMode

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveWriteAcceptanceModeSpecs", "derive_write_acceptance_mode"]


class DeriveWriteAcceptanceModeSpecs(BaseModel):
    """Specs for write acceptance mode derivation phrase."""

    # inputs
    system_id: UUID
    # outputs
    mode: WriteMode | None = None
    reason: str | None = None
    degradation_detected: bool | None = None
    fallback_available: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveWriteAcceptanceModeSpecs),
    inputs={"system_id"},
    outputs={"mode", "reason", "degradation_detected", "fallback_available"},
)
async def derive_write_acceptance_mode(
    options: DeriveWriteAcceptanceModeSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive appropriate write acceptance mode for a system.

    Evaluates system health indicators to determine whether writes should
    proceed under strict validation (normal), relaxed validation (degraded),
    or emergency mode (critical failure with manual override).

    Regulatory Citations:
        - SOC 2 CC7.4: "The entity responds to identified security incidents
          by executing a defined incident response program."
        - ISO 27001 A.17.2.1: "Information processing facilities shall be
          implemented with redundancy sufficient to meet availability requirements."
        - PCI DSS 10.7: "Retain audit trail history for at least one year."

    Args:
        options: Derivation options (system_id)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with mode, reason, degradation_detected, fallback_available

    Mode Selection:
        - strict: All systems nominal, full validation required
        - relaxed: Degradation detected but fallback available
        - emergency: Critical failure, manual approval required
    """
    system_id = options.system_id
    _ = system_id, now_utc()  # Will query system_health, degradation_events

    # Placeholder - would query actual system health metrics
    degradation_detected = False
    fallback_available = True

    # Derive mode based on system state
    if not degradation_detected:
        mode: WriteMode = "strict"
        reason = "All systems nominal - full validation enforced"
    elif degradation_detected and fallback_available:
        mode = "relaxed"
        reason = "Degradation detected but fallback path available - reduced validation"
    else:
        mode = "emergency"
        reason = "Critical degradation without fallback - emergency mode requires manual approval"

    return {
        "mode": mode,
        "reason": reason,
        "degradation_detected": degradation_detected,
        "fallback_available": fallback_available,
    }
