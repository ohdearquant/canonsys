"""Derive whether regulatory carve-out is ready for closing.

ANTI-GAMING: This derivation examines the actual preparation status of
carve-out components. Users cannot assert "carve-out ready" - the system
derives this from evidence.

Regulatory Context:
    - FTC/DOJ: Divestiture must be complete and viable
    - Competition law: Carve-out must be operationally independent
    - Regulatory approvals: Often conditional on carve-out readiness

Complete vertical slice:
- Queries carve-out status and components
- Checks against standard required components
- Identifies missing and blocking components
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

from ..types import CarveOutStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveCarveOutReadinessSpecs", "derive_carve_out_readiness"]


# Standard carve-out components required for regulatory compliance
_STANDARD_CARVE_OUT_COMPONENTS: set[str] = {
    "standalone_financials",
    "it_systems_separation",
    "employee_transition_plan",
    "customer_contract_assignment",
    "supplier_contract_assignment",
    "intellectual_property_allocation",
    "regulatory_licenses_transfer",
    "real_estate_allocation",
}


class DeriveCarveOutReadinessSpecs(BaseModel):
    """Specs for carve-out readiness derivation phrase."""

    # inputs
    deal_id: UUID

    # outputs
    ready: bool | None = None
    status: CarveOutStatus | None = None
    required_components: tuple[str, ...] | None = None
    ready_components: tuple[str, ...] | None = None
    missing_components: tuple[str, ...] | None = None
    blocking_issues: tuple[str, ...] | None = None
    regulatory_deadline: datetime | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None


def _compute_evidence_hash(data: list[dict[str, Any]]) -> str:
    """Compute SHA-256 hash of evidence data for audit trail."""
    content = str(sorted([str(sorted(d.items())) for d in data]))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


@canon_phrase(
    Operable.from_structure(DeriveCarveOutReadinessSpecs),
    inputs={"deal_id"},
    outputs={
        "deal_id",
        "ready",
        "status",
        "required_components",
        "ready_components",
        "missing_components",
        "blocking_issues",
        "regulatory_deadline",
        "evidence_hash",
        "derived_at",
    },
)
async def derive_carve_out_readiness(
    options: DeriveCarveOutReadinessSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Derive whether regulatory carve-out is ready for closing.

    Anti-gaming: This derivation examines the actual preparation
    status of carve-out components. Users cannot assert "carve-out
    ready" - the system derives this from evidence.

    Carve-out is ready when ALL required components are:
    - Approved: Fully prepared and approved
    - Not applicable: Component explicitly marked as N/A

    Components that BLOCK readiness:
    - Not started: Component work hasn't begun
    - Planning: Still in planning phase
    - In progress: Work ongoing but not complete
    - Ready for review: Pending approval
    - Blocked: Cannot be completed

    Regulatory:
        - FTC/DOJ: Divestiture must be complete and viable
        - Competition law: Carve-out must be operationally independent
        - Regulatory approvals: Often conditional on carve-out readiness

    Args:
        options: Options containing deal_id
        ctx: Request context (tenant, actor)
        conn: Optional existing database connection

    Returns:
        Dict with derivation outcome
    """
    now = now_utc()
    deal_id = options.deal_id

    # Query carve-out status and components
    rows = await fetch(
        """
        SELECT
            co.carve_out_id,
            co.overall_status,
            co.regulatory_deadline,
            coc.component_name,
            coc.status AS component_status,
            coc.blocking_issues
        FROM carve_outs co
        LEFT JOIN carve_out_components coc ON co.carve_out_id = coc.carve_out_id
        WHERE co.deal_id = $1
        ORDER BY coc.component_name
        """,
        deal_id,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        # No carve-out defined - check if one is required
        deal_rows = await fetch(
            """
            SELECT requires_carve_out
            FROM deals
            WHERE deal_id = $1
            """,
            deal_id,
            conn=conn,
            tenant_scope=TenantScope.REQUIRED,
        )

        if deal_rows and not deal_rows[0].get("requires_carve_out", False):
            # Carve-out not required
            return {
                "deal_id": deal_id,
                "ready": True,
                "status": CarveOutStatus.NOT_APPLICABLE,
                "required_components": (),
                "ready_components": (),
                "missing_components": (),
                "blocking_issues": (),
                "regulatory_deadline": None,
                "evidence_hash": None,
                "derived_at": now,
            }

        # Carve-out required but not started
        return {
            "deal_id": deal_id,
            "ready": False,
            "status": CarveOutStatus.NOT_STARTED,
            "required_components": tuple(sorted(_STANDARD_CARVE_OUT_COMPONENTS)),
            "ready_components": (),
            "missing_components": tuple(sorted(_STANDARD_CARVE_OUT_COMPONENTS)),
            "blocking_issues": ("Carve-out not initiated",),
            "regulatory_deadline": None,
            "evidence_hash": None,
            "derived_at": now,
        }

    # Parse component statuses
    overall_status = CarveOutStatus(rows[0]["overall_status"])
    regulatory_deadline = rows[0].get("regulatory_deadline")

    ready_components: list[str] = []
    missing_components: list[str] = []
    blocking_issues: list[str] = []

    # Determine required components (from what's defined + standard)
    defined_components = {row["component_name"] for row in rows if row["component_name"]}
    required_components = defined_components | _STANDARD_CARVE_OUT_COMPONENTS

    for row in rows:
        component_name = row.get("component_name")
        if not component_name:
            continue

        component_status = CarveOutStatus(row["component_status"])

        if component_status in (CarveOutStatus.APPROVED, CarveOutStatus.NOT_APPLICABLE):
            ready_components.append(component_name)
        else:
            missing_components.append(component_name)

        # Collect blocking issues
        issues = row.get("blocking_issues")
        if issues:
            if isinstance(issues, list):
                blocking_issues.extend(issues)
            else:
                blocking_issues.append(str(issues))

    # Check for missing standard components
    found_components = {row["component_name"] for row in rows if row["component_name"]}
    missing_components.extend(
        std_component
        for std_component in _STANDARD_CARVE_OUT_COMPONENTS
        if std_component not in found_components
    )

    # Evidence hash
    evidence_hash = _compute_evidence_hash(list(rows))

    # Ready if no missing components and no blocking issues
    ready = len(missing_components) == 0 and len(blocking_issues) == 0

    # Determine effective status
    if ready:
        effective_status = CarveOutStatus.APPROVED
    elif blocking_issues:
        effective_status = CarveOutStatus.BLOCKED
    else:
        effective_status = overall_status

    return {
        "deal_id": deal_id,
        "ready": ready,
        "status": effective_status,
        "required_components": tuple(sorted(required_components)),
        "ready_components": tuple(sorted(set(ready_components))),
        "missing_components": tuple(sorted(set(missing_components))),
        "blocking_issues": tuple(sorted(set(blocking_issues))),
        "regulatory_deadline": regulatory_deadline,
        "evidence_hash": evidence_hash,
        "derived_at": now,
    }
