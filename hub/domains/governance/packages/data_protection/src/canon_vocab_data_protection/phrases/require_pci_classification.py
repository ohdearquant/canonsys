"""Require PCI classification gate.

Raises ClassificationViolationError if resource contains PCI data and
target classification is PUBLIC or INTERNAL.

Regulatory context:
    - PCI DSS v4.0 Req. 3.4: Render PAN unreadable
    - PCI DSS v4.0 Req. 7.1: Restrict access
    - PCI DSS v4.0 Req. 9.4: Media protection
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

__all__ = ["RequirePCIClassificationSpecs", "require_pci_classification"]


class RequirePCIClassificationSpecs(BaseModel):
    """Specs for require PCI classification phrase."""

    # inputs
    resource_id: UUID
    target_classification: ClassificationLevel
    # outputs
    contains_pci: bool | None = None


require_pci_classification_operable = Operable.from_structure(RequirePCIClassificationSpecs)


@canon_phrase(
    require_pci_classification_operable,
    inputs={"resource_id", "target_classification"},
    outputs={"resource_id", "contains_pci", "target_classification"},
)
async def require_pci_classification(
    options: RequirePCIClassificationSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that PCI data is classified at CONFIDENTIAL or above.

    Raises ClassificationViolationError if resource contains PCI data and
    target classification is PUBLIC or INTERNAL.

    Args:
        options: Classification options
        ctx: Request context (tenant, actor)

    Returns:
        Dict with resource_id, contains_pci, target_classification (renamed from classification)

    Raises:
        ClassificationViolationError: If PCI data would be below confidential.

    Regulatory:
        - PCI DSS v4.0 Req. 3.4: Render PAN unreadable
        - PCI DSS v4.0 Req. 7.1: Restrict access
        - PCI DSS v4.0 Req. 9.4: Media protection
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

    contains_pci = row["contains_pci"]

    if not contains_pci:
        return {
            "resource_id": resource_id,
            "contains_pci": False,
            "target_classification": target_classification,
        }

    # PCI data must be CONFIDENTIAL or RESTRICTED
    if target_classification in (
        ClassificationLevel.PUBLIC,
        ClassificationLevel.INTERNAL,
    ):
        raise ClassificationViolationError(
            classification="PCI",
            operation=f"classify_as_{target_classification.value}",
            allowed_operations={"classify_as_confidential", "classify_as_restricted"},
            regulation="PCI DSS v4.0 Req. 3.4",
            context={
                "resource_id": str(resource_id),
                "reason": f"PCI data cannot be classified as {target_classification.value}",
            },
        )

    return {
        "resource_id": resource_id,
        "contains_pci": True,
        "target_classification": target_classification,
    }


# Export auto-generated types from the Phrase object
RequirePCIClassificationOptions = require_pci_classification.options_type
RequirePCIClassificationResult = require_pci_classification.result_type
