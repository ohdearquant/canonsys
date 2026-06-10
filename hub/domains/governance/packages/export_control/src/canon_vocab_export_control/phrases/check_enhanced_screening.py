"""Check enhanced government screening complete.

Derived fact: verifies that comprehensive party screening against
all required government lists has been completed and is current.

Compliance Context:
    - OFAC compliance (31 CFR Part 500)
    - BIS Entity List (15 CFR 744 Supplement No. 4)
    - Know Your Customer requirements
    - Enhanced due diligence for high-risk transactions
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ScreeningScope

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "CheckEnhancedScreeningSpecs",
    "check_enhanced_government_screening_complete",
]

# Validity period for screening results (configurable per policy)
SCREENING_VALIDITY_DAYS = 30  # OFAC recommends 30-day refresh


class CheckEnhancedScreeningSpecs(BaseModel):
    """Specs for enhanced government screening check phrase."""

    # inputs
    transaction_id: UUID
    screening_scope: ScreeningScope = ScreeningScope.DIRECT_PARTY
    # outputs
    complete: bool = False
    ofac_cleared: bool = False
    bis_entity_list_cleared: bool = False
    bis_denied_persons_cleared: bool = False
    bis_unverified_list_cleared: bool = False
    ddtc_debarred_cleared: bool = False
    screening_timestamp: datetime | None = None
    expires_at: datetime | None = None


@canon_phrase(
    Operable.from_structure(CheckEnhancedScreeningSpecs),
    inputs={"transaction_id", "screening_scope"},
    outputs={
        "complete",
        "screening_scope",
        "ofac_cleared",
        "bis_entity_list_cleared",
        "bis_denied_persons_cleared",
        "bis_unverified_list_cleared",
        "ddtc_debarred_cleared",
        "screening_timestamp",
        "expires_at",
    },
)
async def check_enhanced_government_screening_complete(
    options: CheckEnhancedScreeningSpecs,
    ctx: RequestContext,
) -> dict:
    """Check if enhanced government screening has been completed.

    Enhanced screening is required for:
    - High-risk destinations (EAR Country Groups D:1, E:1, E:2)
    - Controlled items (ECCN other than EAR99)
    - Military end-use concerns
    - Transactions involving government entities

    Screens against:
    - OFAC SDN (Specially Designated Nationals)
    - BIS Entity List (15 CFR 744 Supplement No. 4)
    - BIS Denied Persons List
    - BIS Unverified List
    - DDTC Debarred Parties

    This is a derived fact - it checks existing screening results,
    not performs new screening.

    Args:
        options: Options containing transaction_id, screening_scope
        ctx: Request context

    Returns:
        Dict with screening status and individual list clearances

    Regulatory:
        - OFAC compliance (31 CFR Part 500)
        - BIS Entity List (15 CFR 744 Supplement No. 4)
        - Know Your Customer requirements
        - Enhanced due diligence for high-risk transactions

    Example:
        >>> result = await check_enhanced_government_screening_complete(options, ctx)
        >>> if not result["complete"]:
        ...     raise EnhancedScreeningRequired()
    """
    now = now_utc()
    validity_cutoff = now - timedelta(days=SCREENING_VALIDITY_DAYS)
    transaction_id = options.transaction_id
    screening_scope = options.screening_scope

    # Query for screening results
    screening_row = await select_one(
        "export_screening_results",
        where={
            "transaction_id": transaction_id,
            "tenant_id": ctx.tenant_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not screening_row:
        return {
            "complete": False,
            "screening_scope": screening_scope,
            "ofac_cleared": False,
            "bis_entity_list_cleared": False,
            "bis_denied_persons_cleared": False,
            "bis_unverified_list_cleared": False,
            "ddtc_debarred_cleared": False,
            "screening_timestamp": None,
            "expires_at": None,
        }

    screening_timestamp = screening_row.get("screening_timestamp")

    # Check if screening is still valid (within 30 days)
    if screening_timestamp and screening_timestamp < validity_cutoff:
        return {
            "complete": False,  # Expired screening = incomplete
            "screening_scope": screening_scope,
            "ofac_cleared": screening_row.get("ofac_cleared", False),
            "bis_entity_list_cleared": screening_row.get("bis_entity_list_cleared", False),
            "bis_denied_persons_cleared": screening_row.get("bis_denied_persons_cleared", False),
            "bis_unverified_list_cleared": screening_row.get("bis_unverified_list_cleared", False),
            "ddtc_debarred_cleared": screening_row.get("ddtc_debarred_cleared", False),
            "screening_timestamp": screening_timestamp,
            "expires_at": (
                screening_timestamp + timedelta(days=SCREENING_VALIDITY_DAYS)
                if screening_timestamp
                else None
            ),
        }

    # Check scope coverage
    performed_scope = ScreeningScope(screening_row.get("screening_scope", "DIRECT_PARTY"))
    scope_adequate = (
        screening_scope == ScreeningScope.DIRECT_PARTY
        or performed_scope == ScreeningScope.FULL_CHAIN
    )

    # All individual screenings must be cleared
    all_cleared = (
        screening_row.get("ofac_cleared", False)
        and screening_row.get("bis_entity_list_cleared", False)
        and screening_row.get("bis_denied_persons_cleared", False)
        and screening_row.get("bis_unverified_list_cleared", False)
        and screening_row.get("ddtc_debarred_cleared", False)
    )

    return {
        "complete": all_cleared and scope_adequate,
        "screening_scope": performed_scope,
        "ofac_cleared": screening_row.get("ofac_cleared", False),
        "bis_entity_list_cleared": screening_row.get("bis_entity_list_cleared", False),
        "bis_denied_persons_cleared": screening_row.get("bis_denied_persons_cleared", False),
        "bis_unverified_list_cleared": screening_row.get("bis_unverified_list_cleared", False),
        "ddtc_debarred_cleared": screening_row.get("ddtc_debarred_cleared", False),
        "screening_timestamp": screening_timestamp,
        "expires_at": (
            screening_timestamp + timedelta(days=SCREENING_VALIDITY_DAYS)
            if screening_timestamp
            else None
        ),
    }
