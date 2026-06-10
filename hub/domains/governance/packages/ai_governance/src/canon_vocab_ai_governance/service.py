"""AI Governance service - thin wrapper over AI governance phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory context:
- NYC LL144 (AEDT bias audits)
- EU AI Act (High-risk AI requirements)
- Colorado SB24-205 (Consumer AI protections)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    RequireBiasAssessmentDocumentedSpecs,
    RequireHumanReviewForHighRiskSpecs,
    RequireHumanReviewPresentSpecs,
    VerifyBiasAssessmentCompleteSpecs,
    VerifyHumanReviewCompleteSpecs,
    VerifySameToolSpecs,
    require_bias_assessment_documented,
    require_human_review_for_high_risk,
    require_human_review_present,
    verify_bias_assessment_complete,
    verify_human_review_complete,
    verify_same_tool,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["AIGovernanceService"]


# =============================================================================
# Request Options
# =============================================================================


class RequireHighRiskReviewOptions(BaseModel):
    """Options for require_human_review_for_high_risk action."""

    model_id: UUID


class BiasAssessmentOptions(BaseModel):
    """Options for bias assessment actions."""

    model_id: UUID | None = None
    workflow_id: UUID | None = None


class HumanReviewOptions(BaseModel):
    """Options for human review actions."""

    model_id: UUID | None = None
    decision_id: UUID | None = None


class SameToolOptions(BaseModel):
    """Options for same-tool verification."""

    workflow_run_id: UUID
    config_id: UUID
    actual_config_hash: str
    subject_id: UUID | None = None


# =============================================================================
# Service
# =============================================================================


class AIGovernanceService(CanonService):
    """AI Governance service - manages AI/ML compliance.

    Thin wrapper that delegates to phrase functions.

    Provides operations for:
    - High-risk AI deployment requirements
    - Bias assessment verification
    - Human review verification
    - Same-tool (AEDT) verification
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon", name="ai_governance"
    )

    @action(skip_evidence=True)
    async def require_high_risk_review(self, payload: dict, ctx: RequestContext) -> dict:
        """Require human review for high-risk AI deployment.

        Raises HumanReviewMissingError if model is high/critical risk without review.
        """
        options = RequireHighRiskReviewOptions(**payload)
        specs = RequireHumanReviewForHighRiskSpecs(model_id=options.model_id)
        return await require_human_review_for_high_risk(specs, ctx)

    @action(evidence_type="ai_governance.require_bias_assessment")
    async def require_bias_assessment(self, payload: dict, ctx: RequestContext) -> dict:
        """Require bias assessment documentation exists.

        Raises RequirementNotMetError if no documented bias assessment exists.
        """
        options = BiasAssessmentOptions(**payload)
        if options.model_id is None:
            raise ValueError("model_id is required for require_bias_assessment")
        specs = RequireBiasAssessmentDocumentedSpecs(model_id=options.model_id)
        return await require_bias_assessment_documented(specs, ctx)

    @action(skip_evidence=True)
    async def verify_bias_assessment(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify bias assessment completion status (hot path)."""
        options = BiasAssessmentOptions(**payload)
        if options.workflow_id is None:
            raise ValueError("workflow_id is required for verify_bias_assessment")
        specs = VerifyBiasAssessmentCompleteSpecs(workflow_id=options.workflow_id)
        return await verify_bias_assessment_complete(specs, ctx)

    @action(evidence_type="ai_governance.require_human_review")
    async def require_human_review(self, payload: dict, ctx: RequestContext) -> dict:
        """Require human review be present for AI decision.

        Raises RequirementNotMetError if no human review exists.
        """
        options = HumanReviewOptions(**payload)
        if options.model_id is None:
            raise ValueError("model_id is required for require_human_review")
        specs = RequireHumanReviewPresentSpecs(
            model_id=options.model_id,
            decision_id=options.decision_id,
        )
        return await require_human_review_present(specs, ctx)

    @action(skip_evidence=True)
    async def verify_human_review(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify human review completion status (hot path)."""
        options = HumanReviewOptions(**payload)
        if options.decision_id is None:
            raise ValueError("decision_id is required for verify_human_review")
        specs = VerifyHumanReviewCompleteSpecs(decision_id=options.decision_id)
        return await verify_human_review_complete(specs, ctx)

    @action(evidence_type="ai_governance.same_tool_verification")
    async def verify_same_tool(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify same-tool gate for AEDT compliance.

        Creates evidence recording the verification result.
        """
        options = SameToolOptions(**payload)
        specs = VerifySameToolSpecs(
            workflow_run_id=options.workflow_run_id,
            config_id=options.config_id,
            actual_config_hash=options.actual_config_hash,
            subject_id=options.subject_id,
        )
        return await verify_same_tool(specs, ctx)
