"""Require type-specific evidence for transfer types.

Complete vertical slice:
- Maps transfer types to required evidence
- Supports tenant-specific custom requirements
- Falls back to standard transfer pricing documentation requirements
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import EvidenceRequirement

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireTypeSpecificEvidenceSpecs", "require_type_specific_evidence"]


class RequireTypeSpecificEvidenceSpecs(BaseModel):
    """Specs for require type specific evidence phrase."""

    # inputs
    transfer_type: str
    # outputs
    requirements: tuple[EvidenceRequirement, ...] | None = None
    total_required: int | None = None


# Transfer type evidence requirements per transfer pricing regulations
_TRANSFER_TYPE_EVIDENCE: dict[str, list[tuple[str, bool, str]]] = {
    "loan": [
        ("interest_rate_analysis", True, "Arm's length interest rate analysis"),
        ("repayment_schedule", True, "Repayment schedule documentation"),
        ("credit_risk_assessment", True, "Credit risk assessment of borrower"),
        ("comparable_uncontrolled_price", True, "CUP method documentation"),
        ("loan_agreement", True, "Executed loan agreement"),
        ("board_approval", False, "Board approval if above threshold"),
    ],
    "service_fee": [
        ("cost_base_documentation", True, "Documentation of costs incurred"),
        ("markup_rationale", True, "Rationale for markup percentage"),
        ("service_agreement", True, "Service agreement or contract"),
        ("benefit_test", True, "Benefit test documentation"),
        ("allocation_methodology", True, "Cost allocation methodology"),
        ("benchmarking_study", False, "Benchmarking study for comparable services"),
    ],
    "dividend": [
        ("board_declaration", True, "Board resolution declaring dividend"),
        ("distributable_reserves", True, "Distributable reserves analysis"),
        ("solvency_statement", True, "Solvency statement certification"),
        ("withholding_tax_analysis", True, "Withholding tax analysis"),
        ("treaty_benefit_claim", False, "Treaty benefit claim if applicable"),
    ],
    "royalty": [
        ("ip_ownership_documentation", True, "IP ownership documentation"),
        ("royalty_rate_analysis", True, "Arm's length royalty rate analysis"),
        ("license_agreement", True, "License agreement documentation"),
        ("comparable_transaction_analysis", True, "Comparable transaction analysis"),
        ("functions_assets_risks", True, "Functions, assets, risks analysis"),
        ("withholding_tax_analysis", True, "Withholding tax analysis"),
    ],
    "management_fee": [
        ("service_description", True, "Description of management services"),
        ("benefit_documentation", True, "Documentation of benefits received"),
        ("cost_allocation_key", True, "Cost allocation key methodology"),
        ("direct_charge_analysis", True, "Direct vs. indirect charge analysis"),
        ("stewardship_exclusion", False, "Stewardship activity exclusion analysis"),
    ],
    "guarantee_fee": [
        ("credit_enhancement_analysis", True, "Credit enhancement analysis"),
        ("guarantee_fee_rate", True, "Arm's length guarantee fee rate"),
        ("guarantee_agreement", True, "Guarantee agreement documentation"),
        ("probability_of_default", True, "Probability of default assessment"),
        ("loss_given_default", False, "Loss given default analysis"),
    ],
    "cost_sharing": [
        ("cost_sharing_agreement", True, "Cost sharing agreement"),
        ("reasonably_anticipated_benefits", True, "RAB calculation methodology"),
        ("platform_contribution_transaction", True, "PCT documentation if applicable"),
        ("annual_true_up", True, "Annual true-up documentation"),
        ("intangible_development_costs", True, "IDC allocation documentation"),
    ],
}


@canon_phrase(
    Operable.from_structure(RequireTypeSpecificEvidenceSpecs),
    inputs={"transfer_type"},
    outputs={"transfer_type", "requirements", "total_required"},
)
async def require_type_specific_evidence(
    options: RequireTypeSpecificEvidenceSpecs,
    ctx: RequestContext,
) -> dict:
    """Get evidence requirements specific to a transfer type.

    Different intercompany transaction types require different
    documentation for transfer pricing compliance. This feature
    maps transfer types to their required evidence.

    Args:
        options: Options (transfer_type)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with transfer_type, requirements, total_required.

    Regulatory:
        - OECD Transfer Pricing Guidelines (Documentation requirements)
        - IRC Section 482 (Intercompany transactions)
        - IRC Section 6662(e) (Transfer pricing penalties)
        - Treasury Regulations 1.482-1 through 1.482-9
        - Local country transfer pricing documentation rules
    """
    transfer_type_lower = options.transfer_type.lower().replace("-", "_").replace(" ", "_")

    # Check for tenant-specific requirements first
    rows = await fetch(
        """
        SELECT evidence_type, required, description
        FROM transfer_type_evidence_requirements
        WHERE tenant_id = $1 AND transfer_type = $2
        ORDER BY sort_order
        """,
        ctx.tenant_id,
        transfer_type_lower,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if rows:
        requirements = tuple(
            EvidenceRequirement(
                evidence_type=row["evidence_type"],
                required=row["required"],
                description=row["description"],
            )
            for row in rows
        )
    else:
        # Fall back to standard requirements
        evidence_list = _TRANSFER_TYPE_EVIDENCE.get(transfer_type_lower)

        if evidence_list is None:
            # Unknown transfer type - require comprehensive documentation
            evidence_list = [
                ("transaction_description", True, "Detailed transaction description"),
                ("arm_length_analysis", True, "Arm's length pricing analysis"),
                ("comparability_analysis", True, "Comparability analysis"),
                ("method_selection", True, "Transfer pricing method selection"),
                ("supporting_agreements", True, "Supporting contracts and agreements"),
            ]

        requirements = tuple(
            EvidenceRequirement(
                evidence_type=ev_type,
                required=required,
                description=desc,
            )
            for ev_type, required, desc in evidence_list
        )

    total_required = sum(1 for r in requirements if r.required)

    return {
        "transfer_type": transfer_type_lower,
        "requirements": requirements,
        "total_required": total_required,
    }
