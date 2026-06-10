"""Validate business justification documents.

Complete vertical slice:
- Validates justification document completeness
- Checks for required elements (reason, impact, plan, owner)
- Checks tenant-specific additional requirements
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ValidateBusinessJustificationSpecs", "validate_business_justification"]


class ValidateBusinessJustificationSpecs(BaseModel):
    """Specs for validate business justification phrase."""

    # inputs
    justification_doc_id: UUID
    # outputs
    valid: bool | None = None
    has_reason: bool | None = None
    has_impact: bool | None = None
    has_plan: bool | None = None
    has_owner: bool | None = None
    missing_elements: tuple[str, ...] | None = None


# Required elements for a complete business justification
_REQUIRED_ELEMENTS = {
    "reason": "Business rationale or reason",
    "impact": "Impact assessment",
    "plan": "Mitigation or implementation plan",
    "owner": "Responsible owner or accountable party",
}


@canon_phrase(
    Operable.from_structure(ValidateBusinessJustificationSpecs),
    inputs={"justification_doc_id"},
    outputs={
        "valid",
        "has_reason",
        "has_impact",
        "has_plan",
        "has_owner",
        "missing_elements",
    },
)
async def validate_business_justification(
    options: ValidateBusinessJustificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Validate that a business justification document is complete.

    Checks that the justification includes all required elements:
    - Clear business reason/rationale
    - Impact assessment (risk, cost, resource)
    - Mitigation or implementation plan
    - Responsible owner identified

    Args:
        options: Validation options (justification_doc_id)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with valid, has_reason, has_impact, has_plan, has_owner, missing_elements.

    Regulatory:
        - SOX Section 404 (Documentation of business decisions)
        - COSO Framework (Risk assessment and response)
        - IIA Standards (Audit trail requirements)
        - Transfer pricing regulations (Documentation)
    """
    # Query justification document
    row = await select_one(
        "business_justifications",
        where={
            "tenant_id": ctx.tenant_id,
            "justification_id": options.justification_doc_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # Document not found - all elements missing
        return {
            "valid": False,
            "has_reason": False,
            "has_impact": False,
            "has_plan": False,
            "has_owner": False,
            "missing_elements": (
                "reason",
                "impact",
                "plan",
                "owner",
                "document_not_found",
            ),
        }

    # Check each element - must have content longer than 50 chars
    has_reason = bool(row.get("reason_text") and len(row["reason_text"]) > 50)
    has_impact = bool(row.get("impact_assessment") and len(row["impact_assessment"]) > 50)
    has_plan = bool(row.get("mitigation_plan") and len(row["mitigation_plan"]) > 50)
    has_owner = bool(row.get("owner_id"))

    # Collect missing elements
    missing: list[str] = []
    if not has_reason:
        missing.append("reason")
    if not has_impact:
        missing.append("impact")
    if not has_plan:
        missing.append("plan")
    if not has_owner:
        missing.append("owner")

    # Check for additional tenant-specific requirements
    additional_missing = await fetch(
        """
        SELECT element_name
        FROM business_justification_requirements
        WHERE tenant_id = $1 AND required = true
        AND NOT EXISTS (
            SELECT 1 FROM business_justification_elements
            WHERE justification_id = $2 AND element_name = business_justification_requirements.element_name
        )
        """,
        ctx.tenant_id,
        options.justification_doc_id,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    missing.extend(row["element_name"] for row in additional_missing)

    valid = len(missing) == 0

    return {
        "valid": valid,
        "has_reason": has_reason,
        "has_impact": has_impact,
        "has_plan": has_plan,
        "has_owner": has_owner,
        "missing_elements": tuple(missing),
    }
