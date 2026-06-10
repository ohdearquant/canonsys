"""Verify identity provider posture attestation.

Complete vertical slice:
- Queries IdP attestation records
- Verifies attestation is valid and not expired
- Returns attestation status with details

Regulatory context:
    - NIST SP 800-63C (Federation Assurance Levels)
    - SOC 2 Type II (Third-party assurance)
    - FedRAMP (Identity provider requirements)
    - ISO 27001 A.15 (Supplier relationships)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyIdPPostureAttestationSpecs", "verify_idp_posture_attestation"]


# Posture level hierarchy
_POSTURE_LEVELS: dict[str, int] = {
    "basic": 1,
    "standard": 2,
    "enhanced": 3,
    "high": 4,
}


class VerifyIdPPostureAttestationSpecs(BaseModel):
    """Specs for verify IdP posture attestation phrase."""

    # inputs
    idp_id: UUID
    required_posture: str
    # outputs
    attested: bool | None = None
    attestation_date: datetime | None = None
    posture_level: str | None = None
    expires_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(VerifyIdPPostureAttestationSpecs),
    inputs={"idp_id", "required_posture"},
    outputs={
        "idp_id",
        "required_posture",
        "attested",
        "attestation_date",
        "posture_level",
        "expires_at",
    },
)
async def verify_idp_posture_attestation(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify identity provider has valid security posture attestation.

    Checks if the IdP has a current, valid attestation that meets
    the required security posture level. Used to validate federated
    identity assertions.

    Posture levels (ascending):
    - basic: Self-assessment, minimal controls
    - standard: Independent review, standard controls
    - enhanced: SOC 2 Type II or equivalent
    - high: FedRAMP Moderate or equivalent

    Regulatory citations:
    - NIST SP 800-63C Section 5: Federation assurance
    - SOC 2 CC9.2: Third-party risk management
    - FedRAMP: Identity provider authorization requirements
    - ISO 27001 A.15.2: Supplier service delivery management

    Args:
        options: Verification options (idp_id, required_posture) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with idp_id, required_posture, attested, attestation_date, posture_level, expires_at
    """
    idp_id: UUID = options.idp_id
    required_posture: str = options.required_posture
    now = now_utc()

    # Query IdP attestation record
    row = await select_one(
        "idp_attestations",
        where={
            "tenant_id": ctx.tenant_id,
            "idp_id": idp_id,
            "status": "active",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # No attestation found
        return {
            "idp_id": idp_id,
            "required_posture": required_posture,
            "attested": False,
            "attestation_date": None,
            "posture_level": "none",
            "expires_at": None,
        }

    # Extract attestation details
    posture_level = row.get("posture_level", "basic")
    attestation_date = row.get("attested_at")
    expires_at = row.get("expires_at")

    # Check if attestation is expired
    if expires_at and expires_at < now:
        return {
            "idp_id": idp_id,
            "required_posture": required_posture,
            "attested": False,
            "attestation_date": attestation_date,
            "posture_level": posture_level,
            "expires_at": expires_at,
        }

    # Check if posture level meets requirement
    attested = _posture_meets_requirement(posture_level, required_posture)

    return {
        "idp_id": idp_id,
        "required_posture": required_posture,
        "attested": attested,
        "attestation_date": attestation_date,
        "posture_level": posture_level,
        "expires_at": expires_at,
    }


def _posture_meets_requirement(current: str, required: str) -> bool:
    """Check if current posture meets or exceeds required level."""
    current_level = _POSTURE_LEVELS.get(current.lower(), 0)
    required_level = _POSTURE_LEVELS.get(required.lower(), 0)
    return current_level >= required_level
