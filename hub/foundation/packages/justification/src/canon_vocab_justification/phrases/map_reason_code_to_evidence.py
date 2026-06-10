"""Map reason codes to evidence requirements.

Complete vertical slice:
- Maps reason codes to required evidence by context
- Supports tenant-specific custom mappings
- Falls back to standard regulatory mappings
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

__all__ = ["MapReasonCodeSpecs", "map_reason_code_to_evidence"]


class MapReasonCodeSpecs(BaseModel):
    """Specs for map reason code to evidence phrase."""

    # inputs
    reason_code: str
    context: str
    # outputs
    requirements: tuple[EvidenceRequirement, ...] | None = None
    min_required: int | None = None


# Standard reason code mappings by context
_REASON_CODE_MAPPINGS: dict[str, dict[str, list[tuple[str, bool, str]]]] = {
    "termination": {
        "performance": [
            ("performance_review", True, "Documented performance reviews"),
            ("pip_documentation", True, "Performance improvement plan documentation"),
            ("coaching_records", True, "Records of coaching and feedback sessions"),
            ("manager_attestation", True, "Manager attestation of performance issues"),
            ("metric_evidence", False, "Quantitative performance metrics"),
        ],
        "misconduct": [
            (
                "investigation_report",
                True,
                "Investigation report documenting misconduct",
            ),
            ("witness_statements", True, "Statements from witnesses"),
            ("policy_violation_record", True, "Record of policy violated"),
            ("prior_warnings", False, "Documentation of prior warnings"),
            ("security_footage", False, "Security footage if applicable"),
        ],
        "restructuring": [
            ("business_justification", True, "Business case for restructuring"),
            ("selection_criteria", True, "Objective selection criteria used"),
            ("adverse_impact_analysis", True, "Disparate impact analysis"),
            (
                "position_elimination_memo",
                True,
                "Documentation of position elimination",
            ),
        ],
        "other": [
            ("detailed_explanation", True, "Detailed written explanation of reason"),
            ("supporting_documentation", True, "Supporting documentation for claim"),
            ("legal_review", True, "Legal review of termination rationale"),
            ("hr_consultation", True, "HR consultation documentation"),
        ],
    },
    "transfer": {
        "loan": [
            (
                "interest_rate_documentation",
                True,
                "Documentation of arm's length interest rate",
            ),
            ("repayment_schedule", True, "Repayment schedule and terms"),
            ("credit_analysis", True, "Credit analysis of borrower"),
            ("comparable_rate_analysis", False, "Analysis of comparable market rates"),
        ],
        "service_fee": [
            ("cost_base_documentation", True, "Documentation of cost base"),
            ("markup_rationale", True, "Rationale for markup percentage"),
            ("service_agreement", True, "Service agreement documentation"),
            ("benchmarking_study", False, "Benchmarking study for comparable services"),
        ],
        "dividend": [
            ("board_declaration", True, "Board resolution declaring dividend"),
            (
                "distributable_reserves_analysis",
                True,
                "Analysis of distributable reserves",
            ),
            ("solvency_statement", True, "Solvency statement"),
        ],
    },
    "waiver": {
        "regulatory_exemption": [
            ("exemption_letter", True, "Regulatory exemption letter or approval"),
            ("legal_opinion", True, "Legal opinion supporting exemption"),
            ("expiry_tracking", True, "Expiry date and renewal tracking"),
        ],
        "business_necessity": [
            ("business_case", True, "Business necessity justification"),
            ("impact_assessment", True, "Impact assessment of waiver"),
            ("mitigation_plan", True, "Mitigation plan for risks"),
            ("approval_chain", True, "Documentation of approval chain"),
        ],
    },
}


@canon_phrase(
    Operable.from_structure(MapReasonCodeSpecs),
    inputs={"reason_code", "context"},
    outputs={"reason_code", "context", "requirements", "min_required"},
)
async def map_reason_code_to_evidence(
    options: MapReasonCodeSpecs,
    ctx: RequestContext,
) -> dict:
    """Map a reason code to its required evidence based on context.

    Prevents "OTHER" from becoming a documentation-free junk drawer by
    enforcing evidence requirements for all reason codes. Ensures that
    decisions can be defended with appropriate documentation.

    Args:
        options: Mapping options (reason_code, context)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with reason_code, context, requirements, min_required.

    Regulatory:
        - SOX Section 404 (Documentation of internal controls)
        - Employment law (Termination documentation requirements)
        - EEOC Guidelines (Evidence for adverse employment actions)
        - Transfer pricing regulations (Documentation requirements)
    """
    # Normalize inputs
    reason_code_lower = options.reason_code.lower()
    context_lower = options.context.lower()

    # Check for custom mappings in database first (tenant-specific)
    rows = await fetch(
        """
        SELECT evidence_type, required, description
        FROM reason_code_evidence_mappings
        WHERE tenant_id = $1 AND reason_code = $2 AND context = $3
        ORDER BY sort_order
        """,
        ctx.tenant_id,
        reason_code_lower,
        context_lower,
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
        min_required = sum(1 for r in requirements if r.required)
        return {
            "reason_code": reason_code_lower,
            "context": context_lower,
            "requirements": requirements,
            "min_required": min_required,
        }

    # Fall back to standard mappings
    context_mappings = _REASON_CODE_MAPPINGS.get(context_lower, {})
    evidence_list = context_mappings.get(reason_code_lower)

    if evidence_list is None:
        # Unknown reason code - require comprehensive documentation
        evidence_list = [
            ("detailed_explanation", True, "Detailed written explanation"),
            ("supporting_documentation", True, "Supporting documentation"),
            ("approval_record", True, "Record of appropriate approval"),
        ]

    requirements = tuple(
        EvidenceRequirement(
            evidence_type=ev_type,
            required=required,
            description=desc,
        )
        for ev_type, required, desc in evidence_list
    )

    min_required = sum(1 for r in requirements if r.required)

    return {
        "reason_code": reason_code_lower,
        "context": context_lower,
        "requirements": requirements,
        "min_required": min_required,
    }
