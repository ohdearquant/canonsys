"""Require PHI classification gate.

Raises ClassificationViolationError if resource contains PHI (Protected
Health Information) and target classification is PUBLIC or INTERNAL.

Regulatory context:
    - HIPAA Section 164.502: Uses and disclosures
    - HIPAA Section 164.514: De-identification standard
    - HITECH Act Section 13402: Breach notification
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.exceptions import ClassificationViolationError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ClassificationLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequirePHIClassificationSpecs", "require_phi_classification"]


class RequirePHIClassificationSpecs(BaseModel):
    """Specs for require PHI classification phrase."""

    # inputs
    resource_id: UUID
    target_classification: ClassificationLevel
    # outputs
    contains_phi: bool | None = None


require_phi_classification_operable = Operable.from_structure(RequirePHIClassificationSpecs)


@canon_phrase(
    require_phi_classification_operable,
    inputs={"resource_id", "target_classification"},
    outputs={"resource_id", "contains_phi", "target_classification"},
)
async def require_phi_classification(
    options: RequirePHIClassificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that PHI data is classified at CONFIDENTIAL or above.

    Raises ClassificationViolationError if resource contains PHI (Protected
    Health Information) and target classification is PUBLIC or INTERNAL.

    Args:
        options: Classification options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, contains_phi, target_classification (renamed from classification)

    Raises:
        ClassificationViolationError: If PHI data would be below confidential.

    Regulatory:
        - HIPAA Section 164.502: Uses and disclosures
        - HIPAA Section 164.514: De-identification standard
        - HITECH Act Section 13402: Breach notification
    """
    resource_id = options.resource_id
    target_classification = options.target_classification

    row = await select_one(
        "data_classification_registry",
        where={"resource_id": resource_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        raise ClassificationViolationError(
            classification="UNKNOWN",
            operation=f"classify_as_{target_classification.value}",
            allowed_operations=set(),
            context={
                "resource_id": str(resource_id),
                "reason": "Resource not found in classification registry",
            },
        )

    contains_phi = row["contains_phi"]

    if not contains_phi:
        return {
            "resource_id": resource_id,
            "contains_phi": False,
            "target_classification": target_classification,
        }

    if target_classification in (
        ClassificationLevel.PUBLIC,
        ClassificationLevel.INTERNAL,
    ):
        raise ClassificationViolationError(
            classification="PHI",
            operation=f"classify_as_{target_classification.value}",
            allowed_operations={"classify_as_confidential", "classify_as_restricted"},
            regulation="HIPAA Section 164.502",
            context={
                "resource_id": str(resource_id),
                "reason": f"PHI cannot be classified as {target_classification.value}",
            },
        )

    return {
        "resource_id": resource_id,
        "contains_phi": True,
        "target_classification": target_classification,
    }


# Export auto-generated types from the Phrase object
RequirePHIClassificationOptions = require_phi_classification.options_type
RequirePHIClassificationResult = require_phi_classification.result_type
