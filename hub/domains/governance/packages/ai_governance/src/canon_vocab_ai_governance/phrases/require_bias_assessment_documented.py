"""Require bias assessment documentation for AI/ML model.

Complete vertical slice:
- Queries for documented bias assessment record
- Checks documentation_status is complete
- Raises RequirementNotMetError if not documented

Regulatory:
- NYC LL144 Section 20-870: Bias audit requirements
- EU AI Act Art. 9: Risk management
- CO SB21-169/SB205: Algorithmic discrimination
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireBiasAssessmentDocumentedSpecs", "require_bias_assessment_documented"]


class RequireBiasAssessmentDocumentedSpecs(BaseModel):
    """Specs for require bias assessment documented phrase."""

    # inputs
    model_id: UUID
    # outputs
    satisfied: bool | None = None
    assessment_id: UUID | None = None
    documented_at: datetime | None = None
    document_url: str | None = None
    reason: str | None = None


require_bias_assessment_documented_operable = Operable.from_structure(
    RequireBiasAssessmentDocumentedSpecs
)


@canon_phrase(
    require_bias_assessment_documented_operable,
    inputs={"model_id"},
    outputs={
        "satisfied",
        "model_id",
        "assessment_id",
        "documented_at",
        "document_url",
        "reason",
    },
)
async def require_bias_assessment_documented(
    options: RequireBiasAssessmentDocumentedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require bias assessment documentation exists for AI/ML model.

    Raises RequirementNotMetError if no documented bias assessment exists.

    Regulatory:
        - NYC LL144 Section 20-870 (Bias audit requirements)
        - EU AI Act Art. 9 (Risk management)
        - CO SB21-169/SB205 (Algorithmic discrimination)

    Args:
        options: Options containing model_id to check
        ctx: Request context (tenant, actor)

    Returns:
        Dict with satisfied=True and assessment details if satisfied

    Raises:
        RequirementNotMetError: If no documented bias assessment exists
    """
    model_id = options.model_id

    row = await select_one(
        "ai_bias_assessments",
        where={
            "model_id": model_id,
            "tenant_id": ctx.tenant_id,
            "documentation_status": "complete",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="bias_assessment_documented",
            reason=f"No documented bias assessment for model {model_id}",
        )

    return {
        "satisfied": True,
        "model_id": model_id,
        "assessment_id": row.get("assessment_id") or row.get("id"),
        "documented_at": row.get("documented_at"),
        "document_url": row.get("document_url"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireBiasAssessmentDocumentedOptions = require_bias_assessment_documented.options_type
RequireBiasAssessmentDocumentedResult = require_bias_assessment_documented.result_type
