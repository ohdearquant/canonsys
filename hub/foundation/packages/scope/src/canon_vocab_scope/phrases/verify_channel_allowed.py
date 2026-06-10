"""Verify channel is on allowlist.

Validates communication channels against security allowlists.

Regulatory context:
    - SOC 2 CC6.7: Transmission restrictions
    - HIPAA 164.312(e)(1): Transmission security
    - PCI DSS 4.1: Secure transmission
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyChannelAllowedSpecs", "verify_channel_allowed"]


class VerifyChannelAllowedSpecs(BaseModel):
    """Specs for verify channel allowed phrase."""

    # inputs
    channel: str
    channel_type: str
    allowlist: list[str]
    allowlist_version: str = "v1"
    # outputs
    allowed: bool | None = None


@canon_phrase(
    Operable.from_structure(VerifyChannelAllowedSpecs),
    inputs={"channel", "channel_type", "allowlist", "allowlist_version"},
    outputs={"allowed", "channel", "channel_type", "allowlist_version"},
)
async def verify_channel_allowed(
    options: VerifyChannelAllowedSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that a communication channel is permitted for data transmission.

    Checks the channel against an allowlist, considering the channel type.
    Used to enforce transmission security policies and prevent data
    exfiltration via unauthorized channels.

    Regulatory Citations:
        - SOC 2 CC6.7: The entity restricts the transmission, movement, and
          removal of information to authorized internal and external users
          and processes, and devices.
        - HIPAA 164.312(e)(1): Technical security measures to guard against
          unauthorized access to EPHI transmitted over electronic network.
        - PCI DSS 4.1: Use strong cryptography and security protocols to
          safeguard sensitive cardholder data during transmission.

    Args:
        options: Channel verification options.
        ctx: Request context (tenant, actor).

    Returns:
        dict with allowed, channel, channel_type, allowlist_version.
    """
    channel_normalized = options.channel.strip().lower()
    allowlist_normalized = {c.strip().lower() for c in options.allowlist}

    allowed = channel_normalized in allowlist_normalized

    return {
        "allowed": allowed,
        "channel": options.channel,
        "channel_type": options.channel_type,
        "allowlist_version": options.allowlist_version,
    }
