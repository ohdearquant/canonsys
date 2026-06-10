"""Check military end-use license obtained.

Derived fact: verifies that military end-use controls (EAR Part 744)
have been satisfied with valid license documentation.

Compliance Context:
    - EAR Part 744.21: Military end-use controls
    - BIS license determination for military end-use
    - End-user verification requirements
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

__all__ = ["CheckMilitaryEndUseLicenseSpecs", "check_military_end_use_license_obtained"]

# Validity period for screening results (configurable per policy)
SCREENING_VALIDITY_DAYS = 30  # OFAC recommends 30-day refresh


class CheckMilitaryEndUseLicenseSpecs(BaseModel):
    """Specs for military end-use license check phrase."""

    # inputs
    transaction_id: UUID
    destination_country: str
    # outputs
    obtained: bool = False
    license_id: UUID | None = None
    license_type: str | None = None
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    end_user_verified: bool = False


@canon_phrase(
    Operable.from_structure(CheckMilitaryEndUseLicenseSpecs),
    inputs={"transaction_id", "destination_country"},
    outputs={
        "obtained",
        "license_id",
        "license_type",
        "issued_at",
        "expires_at",
        "end_user_verified",
        "destination_country",
    },
)
async def check_military_end_use_license_obtained(
    options: CheckMilitaryEndUseLicenseSpecs,
    ctx: RequestContext,
) -> dict:
    """Check if valid military end-use license has been obtained.

    Military end-use controls (EAR Part 744.21) require specific
    authorization for exports that may support military activities
    in certain countries (China, Russia, Venezuela, Burma).

    This is a derived fact - it checks existing evidence, not
    creates new state.

    Args:
        options: Options containing transaction_id, destination_country
        ctx: Request context

    Returns:
        Dict with license status and details

    Regulatory:
        - EAR Part 744.21: Military end-use controls
        - BIS license determination for military end-use
        - End-user verification requirements

    Example:
        >>> result = await check_military_end_use_license_obtained(options, ctx)
        >>> if not result["obtained"]:
        ...     raise MilitaryEndUseLicenseRequired()
    """
    now = now_utc()
    transaction_id = options.transaction_id
    destination_country = options.destination_country

    # Query for valid military end-use license
    license_row = await select_one(
        "export_licenses",
        where={
            "transaction_id": transaction_id,
            "license_category": "MILITARY_END_USE",
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not license_row:
        return {
            "obtained": False,
            "license_id": None,
            "license_type": None,
            "issued_at": None,
            "expires_at": None,
            "end_user_verified": False,
            "destination_country": destination_country,
        }

    # Check expiration
    expires_at = license_row.get("expires_at")
    if expires_at and expires_at < now:
        return {
            "obtained": False,  # Expired = not obtained
            "license_id": license_row["license_id"],
            "license_type": license_row.get("license_type"),
            "issued_at": license_row.get("issued_at"),
            "expires_at": expires_at,
            "end_user_verified": license_row.get("end_user_verified", False),
            "destination_country": destination_country,
        }

    return {
        "obtained": True,
        "license_id": license_row["license_id"],
        "license_type": license_row.get("license_type"),
        "issued_at": license_row.get("issued_at"),
        "expires_at": expires_at,
        "end_user_verified": license_row.get("end_user_verified", False),
        "destination_country": destination_country,
    }
