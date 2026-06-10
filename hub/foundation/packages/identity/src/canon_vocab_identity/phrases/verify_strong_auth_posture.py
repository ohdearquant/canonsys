"""Verify strong authentication posture.

Complete vertical slice:
- Queries authentication factors for a subject
- Checks if posture meets required level
- Returns binary gate result with factor details

Regulatory context:
    - NIST SP 800-63B (Authenticator and Verifier Requirements)
    - SOC 2 CC6.1 (Logical access controls)
    - GDPR Art. 32 (Security of processing - appropriate authentication)
    - FedRAMP (Government authentication requirements)
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

from ..types import AuthPosture

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyStrongAuthPostureSpecs", "verify_strong_auth_posture"]


# Posture hierarchy: higher index = stronger
_POSTURE_LEVELS: dict[AuthPosture, int] = {
    "none": 0,
    "basic": 1,
    "strong": 2,
    "hardware": 3,
}


class VerifyStrongAuthPostureSpecs(BaseModel):
    """Specs for verify strong auth posture phrase."""

    # inputs
    subject_id: UUID
    required_posture: AuthPosture = "strong"
    # outputs
    posture: AuthPosture | None = None
    factors: tuple[str, ...] | None = None
    last_verified: datetime | None = None
    meets_requirement: bool | None = None


@canon_phrase(
    Operable.from_structure(VerifyStrongAuthPostureSpecs),
    inputs={"subject_id", "required_posture"},
    outputs={
        "subject_id",
        "required_posture",
        "posture",
        "factors",
        "last_verified",
        "meets_requirement",
    },
)
async def verify_strong_auth_posture(
    options,
    ctx: RequestContext,
) -> dict:
    """Verify subject has required authentication posture.

    Checks if the subject's current authentication state meets the required
    posture level. Used as a gate before sensitive operations.

    Regulatory citations:
    - NIST SP 800-63B Section 4: Authenticator assurance levels
    - SOC 2 CC6.1: Logical and physical access controls
    - GDPR Art. 32: Appropriate technical measures for data security

    Args:
        options: Verification options (subject_id, required_posture) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with subject_id, required_posture, posture, factors, last_verified, meets_requirement
    """
    subject_id: UUID = options.subject_id
    required_posture: AuthPosture = options.required_posture
    now = now_utc()

    # Query authentication session for subject
    row = await select_one(
        "auth_sessions",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "status": "active",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # No active session - no authentication
        return {
            "subject_id": subject_id,
            "required_posture": required_posture,
            "posture": "none",
            "factors": (),
            "last_verified": now,
            "meets_requirement": False,
        }

    # Extract factors from session
    factors_raw = row.get("factors", [])
    factors = tuple(factors_raw) if factors_raw else ()

    # Determine posture from factors
    posture = _determine_posture_from_factors(factors)

    # Check if current posture meets requirement
    meets_requirement = _posture_meets_requirement(posture, required_posture)

    return {
        "subject_id": subject_id,
        "required_posture": required_posture,
        "posture": posture,
        "factors": factors,
        "last_verified": row.get("verified_at", now),
        "meets_requirement": meets_requirement,
    }


def _determine_posture_from_factors(factors: tuple[str, ...]) -> AuthPosture:
    """Determine authentication posture from factors present."""
    if not factors:
        return "none"

    # Hardware factors indicate highest posture
    hardware_factors = {"fido2", "piv", "hardware_key"}
    if any(f in hardware_factors for f in factors):
        return "hardware"

    # Multiple factors indicate strong posture
    if len(factors) >= 2:
        return "strong"

    # Single factor is basic
    return "basic"


def _posture_meets_requirement(current: AuthPosture, required: AuthPosture) -> bool:
    """Check if current posture meets or exceeds required level."""
    current_level = _POSTURE_LEVELS[current]
    required_level = _POSTURE_LEVELS[required]
    return current_level >= required_level
