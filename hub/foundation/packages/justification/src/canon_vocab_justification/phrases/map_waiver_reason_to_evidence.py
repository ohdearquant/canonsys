"""Map waiver reasons to evidence requirements.

Complete vertical slice:
- Maps waiver reasons to required and optional evidence
- Supports tenant-specific custom mappings
- Falls back to standard regulatory mappings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["MapWaiverReasonSpecs", "map_waiver_reason_to_evidence"]


class MapWaiverReasonSpecs(BaseModel):
    """Specs for map waiver reason to evidence phrase."""

    # inputs
    waiver_reason: str
    waiver_type: str
    # outputs
    required_evidence: tuple[str, ...] | None = None
    optional_evidence: tuple[str, ...] | None = None
    escalation_required: bool | None = None


# Waiver reason to evidence mappings
_WAIVER_EVIDENCE_MAPPINGS: dict[str, dict[str, tuple[list[str], list[str], bool]]] = {
    "policy_waiver": {
        "regulatory_exemption": (
            [
                "exemption_letter",
                "legal_opinion",
                "regulator_correspondence",
                "expiry_date_tracking",
            ],
            ["prior_exemption_history", "risk_assessment"],
            False,  # No escalation if regulator approved
        ),
        "business_necessity": (
            [
                "business_case_document",
                "impact_assessment",
                "risk_mitigation_plan",
                "executive_approval",
            ],
            ["alternative_analysis", "timeline_justification"],
            True,  # Escalation required
        ),
        "technical_limitation": (
            [
                "technical_assessment",
                "workaround_documentation",
                "remediation_timeline",
                "risk_acceptance",
            ],
            ["vendor_correspondence", "architecture_review"],
            True,  # Escalation required
        ),
        "cost_prohibition": (
            [
                "cost_benefit_analysis",
                "budget_documentation",
                "alternative_analysis",
                "executive_approval",
            ],
            ["vendor_quotes", "timeline_projection"],
            True,  # Escalation required
        ),
        "emergency": (
            [
                "emergency_declaration",
                "incident_report",
                "immediate_action_documentation",
                "post_incident_review_commitment",
            ],
            ["timeline_documentation", "communication_records"],
            True,  # Escalation required
        ),
    },
    "control_waiver": {
        "compensating_control": (
            [
                "compensating_control_documentation",
                "effectiveness_assessment",
                "audit_approval",
                "periodic_review_schedule",
            ],
            ["control_testing_results", "risk_assessment"],
            False,  # No escalation if audit approved
        ),
        "temporary_exception": (
            [
                "exception_request",
                "duration_justification",
                "remediation_plan",
                "approval_chain_documentation",
            ],
            ["risk_acceptance", "milestone_tracking"],
            True,  # Escalation required
        ),
        "inherited_risk": (
            [
                "acquisition_documentation",
                "inherited_system_inventory",
                "remediation_roadmap",
                "risk_acceptance",
            ],
            ["integration_plan", "due_diligence_findings"],
            True,  # Escalation required
        ),
    },
    "process_waiver": {
        "expedited_processing": (
            [
                "urgency_justification",
                "business_impact_statement",
                "post_facto_review_commitment",
                "approver_acknowledgment",
            ],
            ["timeline_documentation", "prior_expedited_history"],
            True,  # Escalation required
        ),
        "skip_approval": (
            [
                "skip_justification",
                "risk_assessment",
                "executive_authorization",
                "audit_notification",
            ],
            ["compensating_review", "post_approval_commitment"],
            True,  # Escalation required
        ),
    },
}


@canon_phrase(
    Operable.from_structure(MapWaiverReasonSpecs),
    inputs={"waiver_reason", "waiver_type"},
    outputs={
        "waiver_reason",
        "required_evidence",
        "optional_evidence",
        "escalation_required",
    },
)
async def map_waiver_reason_to_evidence(
    options: MapWaiverReasonSpecs,
    ctx: RequestContext,
) -> dict:
    """Map a waiver reason to its required supporting evidence.

    Ensures that waivers of policy, control, or process requirements
    are properly documented with appropriate evidence. Prevents
    waivers from becoming undocumented bypasses of controls.

    Args:
        options: Mapping options (waiver_reason, waiver_type)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with waiver_reason, required_evidence, optional_evidence, escalation_required.

    Regulatory:
        - SOX Section 404 (Control exceptions must be documented)
        - SOC 2 CC1.4 (Exception handling)
        - COSO Framework (Control environment)
        - NIST CSF (Exception management)
        - ISO 27001 (Nonconformity handling)
    """
    waiver_reason_lower = options.waiver_reason.lower().replace("-", "_").replace(" ", "_")
    waiver_type_lower = options.waiver_type.lower().replace("-", "_").replace(" ", "_")

    # Check for tenant-specific mappings first
    rows = await fetch(
        """
        SELECT
            required_evidence,
            optional_evidence,
            escalation_required
        FROM waiver_evidence_mappings
        WHERE tenant_id = $1 AND waiver_type = $2 AND waiver_reason = $3
        """,
        ctx.tenant_id,
        waiver_type_lower,
        waiver_reason_lower,
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if rows:
        row = rows[0]
        return {
            "waiver_reason": waiver_reason_lower,
            "required_evidence": tuple(row["required_evidence"]),
            "optional_evidence": tuple(row["optional_evidence"]),
            "escalation_required": row["escalation_required"],
        }

    # Fall back to standard mappings
    type_mappings = _WAIVER_EVIDENCE_MAPPINGS.get(waiver_type_lower, {})
    mapping = type_mappings.get(waiver_reason_lower)

    if mapping is None:
        # Unknown waiver reason - require comprehensive documentation
        required = [
            "waiver_request_form",
            "justification_document",
            "risk_assessment",
            "approval_documentation",
            "review_schedule",
        ]
        optional = ["supporting_correspondence", "prior_history"]
        escalation_required = True
    else:
        required, optional, escalation_required = mapping

    return {
        "waiver_reason": waiver_reason_lower,
        "required_evidence": tuple(required),
        "optional_evidence": tuple(optional),
        "escalation_required": escalation_required,
    }
