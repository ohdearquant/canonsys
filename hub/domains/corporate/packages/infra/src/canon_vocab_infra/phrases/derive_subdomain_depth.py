"""Derive subdomain depth and assess DNS hierarchy risk.

Analyzes domain name structure to identify deeply-nested subdomains
that may indicate DNS tunneling or data exfiltration.

Regulatory Context:
    - SOC 2 CC6.6: Logical access security
    - ISO 27001 A.13.1.1: Network management
    - NIST 800-53 SC-7: Boundary protection
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .constants import DEFAULT_MAX_SAFE_DEPTH

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveSubdomainDepthSpecs", "derive_subdomain_depth"]


class DeriveSubdomainDepthSpecs(BaseModel):
    """Specs for subdomain depth derivation phrase."""

    # inputs
    domain: str
    max_safe_depth: int = DEFAULT_MAX_SAFE_DEPTH
    # outputs
    depth: int | None = None
    is_suspicious: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveSubdomainDepthSpecs),
    inputs={"domain", "max_safe_depth"},
    outputs={"depth", "domain", "is_suspicious", "max_safe_depth"},
)
async def derive_subdomain_depth(
    options: DeriveSubdomainDepthSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive subdomain depth and assess DNS hierarchy risk.

    Analyzes domain name structure to identify deeply-nested subdomains
    that may indicate DNS tunneling, data exfiltration attempts, or
    suspicious infrastructure configurations.

    Regulatory Citations:
        - SOC 2 CC6.6: "The entity implements logical access security
          measures to protect against threats from sources outside its
          system boundaries."
        - ISO 27001 A.13.1.1: "Networks shall be managed and controlled
          to protect information in systems and applications."
        - NIST 800-53 SC-7: "The information system monitors and controls
          communications at the external boundary of the system."

    Args:
        options: Derivation options (domain, max_safe_depth)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with depth, domain, is_suspicious, max_safe_depth

    Examples:
        - "example.com" -> depth=0
        - "api.example.com" -> depth=1
        - "a.b.c.d.e.example.com" -> depth=5, is_suspicious=True
    """
    domain = options.domain
    max_safe_depth = options.max_safe_depth

    # Remove trailing dot if present (FQDN format)
    domain = domain.rstrip(".")

    # Split and count subdomain levels
    parts = domain.split(".")

    # Standard TLD patterns: domain.tld or domain.co.tld
    # Depth is subdomains before the registrable domain
    if len(parts) <= 2:
        depth = 0
    elif len(parts) == 3 and parts[-2] in ("co", "com", "org", "net", "gov", "edu"):
        # Handle cases like domain.co.uk
        depth = 0
    else:
        # Subtract base domain (domain + tld) from total
        depth = len(parts) - 2

    is_suspicious = depth > max_safe_depth

    return {
        "depth": depth,
        "domain": domain,
        "is_suspicious": is_suspicious,
        "max_safe_depth": max_safe_depth,
    }
