"""Verify destination is on allowlist.

Validates data transfer destinations against regulatory allowlists.

Regulatory context:
    - GDPR Art. 44-49: Cross-border transfer restrictions
    - SOC 2 CC6.7: Transmission restrictions
    - ITAR/EAR: Export control restrictions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyDestinationAllowedSpecs", "verify_destination_allowed"]


class VerifyDestinationAllowedSpecs(BaseModel):
    """Specs for verify destination allowed phrase."""

    # inputs
    destination: str
    allowlist: list[str]
    allowlist_version: str = "v1"
    # outputs
    allowed: bool | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(VerifyDestinationAllowedSpecs),
    inputs={"destination", "allowlist", "allowlist_version"},
    outputs={"allowed", "destination", "allowlist_version", "reason"},
)
async def verify_destination_allowed(
    options: VerifyDestinationAllowedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a destination is permitted for data transfer.

    Checks the destination against an allowlist to ensure data transfers
    comply with regulatory restrictions. Used for:

    - Cross-border data transfers (GDPR adequacy)
    - Export control compliance (ITAR/EAR)
    - Vendor/partner data sharing restrictions

    Regulatory Citations:
        - GDPR Art. 44-49: Transfers of personal data to third countries or
          international organisations may only take place if specific
          conditions are met (adequacy decision, safeguards, etc.).
        - SOC 2 CC6.7: The entity restricts the transmission of information
          to authorized users and processes.
        - ITAR 22 CFR 120.17: "Export" means the sending or taking of a
          defense article out of the United States.
        - EAR 15 CFR 734.13: Export includes transmission to foreign persons.

    Args:
        options: Destination verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with allowed, destination, allowlist_version, reason.
    """
    destination_normalized = options.destination.strip().lower()
    allowlist_normalized = {d.strip().lower() for d in options.allowlist}

    allowed = destination_normalized in allowlist_normalized

    reason: str | None = None
    if not allowed:
        reason = (
            f"Destination '{options.destination}' not on allowlist "
            f"(version: {options.allowlist_version})"
        )

    return {
        "allowed": allowed,
        "destination": options.destination,
        "allowlist_version": options.allowlist_version,
        "reason": reason,
    }
