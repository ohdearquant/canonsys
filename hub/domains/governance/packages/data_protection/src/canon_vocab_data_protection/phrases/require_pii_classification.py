"""Require PII classification gate.

Raises PIIExposureError if resource contains PII and target is PUBLIC.

Regulatory context:
    - GDPR Art. 5(1)(f): Integrity and confidentiality
    - CCPA Section 1798.100: Consumer rights
    - CPRA Section 1798.185: Regulations
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.exceptions import ClassificationViolationError, PIIExposureError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ClassificationLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequirePIIClassificationSpecs", "require_pii_classification"]


class RequirePIIClassificationSpecs(BaseModel):
    """Specs for require PII classification phrase."""

    # inputs
    resource_id: UUID
    target_classification: ClassificationLevel
    # outputs
    contains_pii: bool | None = None


require_pii_classification_operable = Operable.from_structure(RequirePIIClassificationSpecs)


@canon_phrase(
    require_pii_classification_operable,
    inputs={"resource_id", "target_classification"},
    outputs={"resource_id", "contains_pii", "target_classification"},
)
async def require_pii_classification(
    options: RequirePIIClassificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that PII-containing resources are not made public.

    Raises PIIExposureError if resource contains PII and target is PUBLIC.

    Args:
        options: Classification options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, contains_pii, target_classification

    Raises:
        PIIExposureError: If PII would be made public.
        ClassificationViolationError: If resource not found in registry.

    Regulatory:
        - GDPR Art. 5(1)(f): Integrity and confidentiality
        - CCPA Section 1798.100: Consumer rights
        - CPRA Section 1798.185: Regulations
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

    contains_pii = row["contains_pii"]

    if not contains_pii:
        return {
            "resource_id": resource_id,
            "contains_pii": False,
            "target_classification": target_classification,
        }

    if target_classification == ClassificationLevel.PUBLIC:
        raise PIIExposureError(
            visibility="public",
            contains_pii=True,
            context={
                "resource_id": str(resource_id),
                "target_classification": target_classification.value,
                "reason": "PII cannot be made public",
            },
        )

    return {
        "resource_id": resource_id,
        "contains_pii": True,
        "target_classification": target_classification,
    }


# Export auto-generated types from the Phrase object
RequirePIIClassificationOptions = require_pii_classification.options_type
RequirePIIClassificationResult = require_pii_classification.result_type
