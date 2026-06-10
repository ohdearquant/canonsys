"""Get certificate authority trust level.

Complete vertical slice:
- Queries certificate record by ID
- Returns CA trust level and chain information
- Used for certificate-based authentication gates

Regulatory context:
    - NIST SP 800-63C (Federation and Assertions)
    - FedRAMP (PKI requirements)
    - eIDAS (EU electronic identification)
    - WebTrust for CAs (CA audit requirements)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["GetCALevelSpecs", "get_ca_level"]


class GetCALevelSpecs(BaseModel):
    """Specs for get CA level phrase."""

    # inputs
    certificate_id: UUID
    # outputs
    ca_level: int | None = None
    ca_name: str | None = None
    trust_chain_depth: int | None = None
    is_internal: bool | None = None
    expiry: datetime | None = None


@canon_phrase(
    Operable.from_structure(GetCALevelSpecs),
    inputs={"certificate_id"},
    outputs={
        "certificate_id",
        "ca_level",
        "ca_name",
        "trust_chain_depth",
        "is_internal",
        "expiry",
    },
)
async def get_ca_level(
    options,
    ctx: RequestContext,
) -> dict:
    """Get certificate authority trust level for a certificate.

    Returns the CA trust level in the PKI hierarchy:
    - Level 1: Root CA (self-signed, highest trust)
    - Level 2: Intermediate CA (signed by root)
    - Level 3: Leaf/end-entity certificate

    Regulatory citations:
    - NIST SP 800-63C Section 6: Assertion presentation
    - FedRAMP: PKI requirements for federal systems
    - eIDAS Article 24: Trust service providers
    - WebTrust: CA operational requirements

    Args:
        options: Lookup options (certificate_id) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with certificate_id, ca_level, ca_name, trust_chain_depth, is_internal, expiry
    """
    certificate_id: UUID = options.certificate_id

    # Query certificate record
    row = await select_one(
        "certificates",
        where={
            "tenant_id": ctx.tenant_id,
            "id": certificate_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # Certificate not found - return unknown/untrusted
        return {
            "certificate_id": certificate_id,
            "ca_level": 0,  # Unknown/untrusted
            "ca_name": "unknown",
            "trust_chain_depth": 0,
            "is_internal": False,
            "expiry": None,
        }

    # Extract certificate attributes
    ca_level = row.get("ca_level", 3)  # Default to leaf
    ca_name = row.get("issuer_cn", row.get("subject_cn", "unknown"))
    trust_chain_depth = row.get("chain_depth", 0)
    is_internal = row.get("is_internal", False)
    expiry = row.get("not_after")

    # Validate CA level is in expected range
    ca_level = _normalize_ca_level(ca_level)

    return {
        "certificate_id": certificate_id,
        "ca_level": ca_level,
        "ca_name": ca_name,
        "trust_chain_depth": trust_chain_depth,
        "is_internal": is_internal,
        "expiry": expiry,
    }


def _normalize_ca_level(ca_level: int) -> int:
    """Normalize CA level to valid range."""
    if ca_level < 1:
        return 0  # Unknown
    elif ca_level > 3:
        return 3  # Treat as leaf
    return ca_level
