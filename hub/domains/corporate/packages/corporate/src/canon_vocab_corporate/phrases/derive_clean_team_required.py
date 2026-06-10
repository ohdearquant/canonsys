"""Derive whether clean team is required based on data categories.

ANTI-GAMING: This derivation examines the data categories PRESENT in the deal
and determines whether clean team access controls are required. Users cannot
assert "clean team not required" - the system derives this from evidence.

Regulatory Context:
    - Hart-Scott-Rodino Act (HSR) - antitrust filing/waiting
    - Sherman Act Section 1 - information sharing restrictions
    - FTC/DOJ Merger Guidelines - gun-jumping prevention

Complete vertical slice:
- Queries data categories in deal
- Checks cross-competitor status for employee compensation
- Derives clean team requirement from evidence
- Computes evidence hash for audit trail
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import CleanTeamReason

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveCleanTeamRequiredSpecs", "derive_clean_team_required"]


# Data categories that ALWAYS require clean team (HSR Act, Sherman Act)
_CLEAN_TEAM_TRIGGERS: set[str] = {
    "competitive_pricing",
    "customer_lists",
    "supplier_terms",
    "strategic_roadmap",
    "product_margins",
    "market_strategy",
    "cost_structures",
    "capacity_plans",
    "bidding_history",
}

# Employee compensation requires clean team when cross-competitor
_EMPLOYEE_SENSITIVE: set[str] = {"employee_compensation"}

# Map triggers to primary reason
_TRIGGER_TO_REASON: dict[str, CleanTeamReason] = {
    "competitive_pricing": CleanTeamReason.COMPETITIVE_PRICING,
    "customer_lists": CleanTeamReason.CUSTOMER_LISTS,
    "strategic_roadmap": CleanTeamReason.STRATEGIC_ROADMAP,
    "supplier_terms": CleanTeamReason.SUPPLIER_TERMS,
    "employee_compensation": CleanTeamReason.EMPLOYEE_COMPENSATION,
    "product_margins": CleanTeamReason.PRODUCT_MARGINS,
    "market_strategy": CleanTeamReason.MARKET_STRATEGY,
}


class DeriveCleanTeamRequiredSpecs(BaseModel):
    """Specs for clean team derivation phrase."""

    # inputs
    deal_id: UUID

    # outputs
    required: bool | None = None
    reason: CleanTeamReason | None = None
    data_categories: tuple[str, ...] | None = None
    sensitivity_triggers: tuple[str, ...] | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None


def _compute_evidence_hash(data: list[dict[str, Any]]) -> str:
    """Compute SHA-256 hash of evidence data for audit trail."""
    content = str(sorted([str(sorted(d.items())) for d in data]))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _derive_primary_reason(triggers: set[str]) -> CleanTeamReason:
    """Derive the primary reason for clean team requirement.

    Priority order reflects regulatory severity:
    1. Competitive pricing (most severe - direct price-fixing risk)
    2. Customer lists (significant - market allocation risk)
    3. Strategic roadmap (significant - coordination risk)
    4. Other categories
    """
    priority = [
        "competitive_pricing",
        "customer_lists",
        "strategic_roadmap",
        "supplier_terms",
        "product_margins",
        "market_strategy",
        "employee_compensation",
    ]
    for category in priority:
        if category in triggers:
            return _TRIGGER_TO_REASON.get(category, CleanTeamReason.COMPETITIVE_PRICING)
    return CleanTeamReason.NOT_REQUIRED


@canon_phrase(
    Operable.from_structure(DeriveCleanTeamRequiredSpecs),
    inputs={"deal_id"},
    outputs={
        "deal_id",
        "required",
        "reason",
        "data_categories",
        "sensitivity_triggers",
        "evidence_hash",
        "derived_at",
    },
)
async def derive_clean_team_required(
    options: DeriveCleanTeamRequiredSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Derive whether clean team is required based on data categories.

    Anti-gaming: This derivation examines the data categories PRESENT
    in the deal and determines whether clean team access controls are
    required. Users cannot assert "clean team not required" - the
    system derives this from evidence.

    Clean team is required when:
    - Competitive pricing data is present
    - Customer lists with sensitive attributes exist
    - Strategic roadmap information is shared
    - Supplier terms are disclosed
    - Product margins or cost structures are revealed
    - Market strategy documents are exchanged
    - Bidding history is accessible

    Regulatory:
        - Hart-Scott-Rodino Act: Prevents gun-jumping by requiring
          information barriers for competitively sensitive data
        - Sherman Act Section 1: Prohibits competitively sensitive
          information sharing between competitors
        - FTC/DOJ Merger Guidelines: Information barrier requirements

    Args:
        options: Options containing deal_id
        ctx: Request context (tenant, actor)
        conn: Optional existing database connection

    Returns:
        Dict with derivation outcome and evidence
    """
    now = now_utc()
    deal_id = options.deal_id

    # Query data categories present in deal's data room/documents
    rows = await fetch(
        """
        SELECT DISTINCT dc.category_name, dc.sensitivity_level, dc.document_id
        FROM deal_data_categories dc
        WHERE dc.deal_id = $1
          AND dc.is_active = true
        ORDER BY dc.category_name
        """,
        deal_id,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        # No data categories found - clean team not required
        return {
            "deal_id": deal_id,
            "required": False,
            "reason": CleanTeamReason.NOT_REQUIRED,
            "data_categories": (),
            "sensitivity_triggers": (),
            "evidence_hash": None,
            "derived_at": now,
        }

    # Extract categories found
    categories = tuple(sorted({row["category_name"] for row in rows}))
    categories_set = set(categories)

    # Determine which categories trigger clean team requirement
    triggers = categories_set & _CLEAN_TEAM_TRIGGERS

    # Check employee compensation with additional context
    if "employee_compensation" in categories_set:
        # Employee compensation triggers clean team in cross-competitor deals
        # Query to check if deal involves competitors
        comp_rows = await fetch(
            """
            SELECT is_cross_competitor
            FROM deals
            WHERE deal_id = $1
            """,
            deal_id,
            conn=conn,
            tenant_scope=TenantScope.REQUIRED,
        )
        if comp_rows and comp_rows[0].get("is_cross_competitor", False):
            triggers.add("employee_compensation")

    # Compute evidence hash for audit trail
    evidence_hash = _compute_evidence_hash(list(rows))

    if not triggers:
        return {
            "deal_id": deal_id,
            "required": False,
            "reason": CleanTeamReason.NOT_REQUIRED,
            "data_categories": categories,
            "sensitivity_triggers": (),
            "evidence_hash": evidence_hash,
            "derived_at": now,
        }

    # Clean team IS required
    primary_reason = _derive_primary_reason(triggers)
    sensitivity_triggers = tuple(sorted(triggers))

    return {
        "deal_id": deal_id,
        "required": True,
        "reason": primary_reason,
        "data_categories": categories,
        "sensitivity_triggers": sensitivity_triggers,
        "evidence_hash": evidence_hash,
        "derived_at": now,
    }
