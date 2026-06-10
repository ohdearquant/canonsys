"""Verify that bias assessment has been completed for AI/ML workflow.

Complete vertical slice:
- Queries for bias assessment record
- Checks completion status and expiration
- Returns verification result (no exception on failure)

Regulatory Citations:
- NYC LL144 Section 20-870: Requires independent bias audit of automated
  employment decision tools before use and annually thereafter
- EU AI Act Article 9: High-risk AI systems must implement risk management
  including bias identification and mitigation measures
- Colorado SB 21-205: Requires documentation of algorithmic impact
  assessments for consequential decisions
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

from ..types import BiasAssessmentStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyBiasAssessmentCompleteSpecs", "verify_bias_assessment_complete"]


class VerifyBiasAssessmentCompleteSpecs(BaseModel):
    """Specs for verify bias assessment complete phrase."""

    # inputs
    workflow_id: UUID
    # outputs
    verified: bool | None = None
    status: BiasAssessmentStatus | None = None
    checked_at: datetime | None = None
    assessment_id: UUID | None = None
    assessed_at: datetime | None = None
    assessor_id: UUID | None = None
    expires_at: datetime | None = None
    reason: str | None = None


verify_bias_assessment_complete_operable = Operable.from_structure(
    VerifyBiasAssessmentCompleteSpecs
)


@canon_phrase(
    verify_bias_assessment_complete_operable,
    inputs={"workflow_id"},
    outputs={
        "verified",
        "status",
        "workflow_id",
        "checked_at",
        "assessment_id",
        "assessed_at",
        "assessor_id",
        "expires_at",
        "reason",
    },
)
async def verify_bias_assessment_complete(
    options: VerifyBiasAssessmentCompleteSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify that bias assessment has been completed for AI/ML workflow.

    Fail-closed: If assessment status cannot be determined or is expired,
    treat as not verified.

    Regulatory Citations:
        - NYC LL144 Section 20-870: Requires independent bias audit of automated
          employment decision tools before use and annually thereafter
        - EU AI Act Article 9: High-risk AI systems must implement risk management
          including bias identification and mitigation measures
        - Colorado SB 21-205: Requires documentation of algorithmic impact
          assessments for consequential decisions

    Args:
        options: Options containing workflow_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with verification status and assessment details
    """
    workflow_id = options.workflow_id
    now = now_utc()

    # Query for bias assessment record for this workflow
    row = await select_one(
        "bias_assessments",
        where={
            "tenant_id": ctx.tenant_id,
            "workflow_id": workflow_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        return {
            "verified": False,
            "status": BiasAssessmentStatus.NOT_FOUND,
            "workflow_id": workflow_id,
            "checked_at": now,
            "assessment_id": None,
            "assessed_at": None,
            "assessor_id": None,
            "expires_at": None,
            "reason": "No bias assessment record found for workflow - "
            "NYC LL144 Section 20-870 requires independent bias audit",
        }

    # Check if assessment is complete
    assessment_status = row.get("status")
    if assessment_status == "in_progress":
        return {
            "verified": False,
            "status": BiasAssessmentStatus.IN_PROGRESS,
            "workflow_id": workflow_id,
            "checked_at": now,
            "assessment_id": row["id"],
            "assessed_at": None,
            "assessor_id": None,
            "expires_at": None,
            "reason": "Bias assessment in progress - must be completed before deployment",
        }

    # Check if assessment has expired (NYC LL144 requires annual renewal)
    expires_at = row.get("expires_at")
    if expires_at and expires_at < now:
        return {
            "verified": False,
            "status": BiasAssessmentStatus.EXPIRED,
            "workflow_id": workflow_id,
            "checked_at": now,
            "assessment_id": row["id"],
            "assessed_at": row.get("completed_at"),
            "assessor_id": row.get("assessor_id"),
            "expires_at": expires_at,
            "reason": "Bias assessment expired - NYC LL144 requires annual renewal",
        }

    # Assessment is complete and valid
    return {
        "verified": True,
        "status": BiasAssessmentStatus.COMPLETE,
        "workflow_id": workflow_id,
        "checked_at": now,
        "assessment_id": row["id"],
        "assessed_at": row.get("completed_at"),
        "assessor_id": row.get("assessor_id"),
        "expires_at": expires_at,
        "reason": "Bias assessment complete and valid",
    }


# Export auto-generated types from the Phrase object
VerifyBiasAssessmentCompleteOptions = verify_bias_assessment_complete.options_type
VerifyBiasAssessmentCompleteResult = verify_bias_assessment_complete.result_type
