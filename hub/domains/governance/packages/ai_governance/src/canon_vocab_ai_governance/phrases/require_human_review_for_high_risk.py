"""Require human review for high-risk AI/ML models.

Complete vertical slice:
- Queries model registry for risk level
- Checks for approved review if high/critical risk
- Raises exception on missing review (fail-closed)

Regulatory:
- EU AI Act Article 6: High-risk AI classification
- EU AI Act Article 9: Risk management system
- NYC LL144 Section 20-870: AEDT requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.exceptions import HumanReviewMissingError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import RiskLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireHumanReviewForHighRiskSpecs", "require_human_review_for_high_risk"]


class RequireHumanReviewForHighRiskSpecs(BaseModel):
    """Specs for require human review for high risk phrase."""

    # inputs
    model_id: UUID
    # outputs
    risk_level: RiskLevel | None = None
    review_id: UUID | None = None
    reviewed_at: datetime | None = None


require_human_review_for_high_risk_operable = Operable.from_structure(
    RequireHumanReviewForHighRiskSpecs
)


@canon_phrase(
    require_human_review_for_high_risk_operable,
    inputs={"model_id"},
    outputs={"model_id", "risk_level", "review_id", "reviewed_at"},
)
async def require_human_review_for_high_risk(
    options: RequireHumanReviewForHighRiskSpecs,
    ctx: RequestContext,
) -> dict:
    """Require human review for high-risk AI/ML models.

    Raises HumanReviewMissingError if model is high/critical risk and lacks
    an approved review.

    Regulatory:
        - EU AI Act Art. 6 (High-risk classification)
        - EU AI Act Art. 9 (Risk management system)
        - NYC LL144 Section 20-870 (AEDT requirements)

    Args:
        options: Options containing model_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with model_id, risk_level, review_id, reviewed_at if review
        exists or not required.

    Raises:
        HumanReviewMissingError: If high-risk model lacks approved review.
    """
    model_id = options.model_id

    # Get model risk level from registry
    risk_row = await select_one(
        "ai_model_registry",
        where={"model_id": model_id, "tenant_id": ctx.tenant_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not risk_row:
        # Fail-closed: unknown model treated as high-risk
        raise HumanReviewMissingError(
            decision_id=model_id,
            risk_level="high",
            context={"reason": "Model not found in registry"},
        )

    risk_level = RiskLevel(risk_row["risk_level"])

    # Low/medium risk doesn't require review
    if risk_level in (RiskLevel.LOW, RiskLevel.MEDIUM):
        return {
            "model_id": model_id,
            "risk_level": risk_level,
            "review_id": None,
            "reviewed_at": None,
        }

    # Check for completed and approved review
    review_row = await select_one(
        "ai_risk_reviews",
        where={
            "model_id": model_id,
            "tenant_id": ctx.tenant_id,
            "status": "approved",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not review_row:
        raise HumanReviewMissingError(
            decision_id=model_id,
            risk_level=risk_level.value,
            context={"reason": "High-risk model requires approved review"},
        )

    return {
        "model_id": model_id,
        "risk_level": risk_level,
        "review_id": review_row.get("review_id") or review_row.get("id"),
        "reviewed_at": review_row.get("reviewed_at"),
    }


# Export auto-generated types from the Phrase object
RequireHumanReviewForHighRiskOptions = require_human_review_for_high_risk.options_type
RequireHumanReviewForHighRiskResult = require_human_review_for_high_risk.result_type
