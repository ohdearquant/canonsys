"""Require that data classification has been assigned before processing.

Ensures all data resources have an explicit classification level assigned
before any processing operations proceed. Fail-closed: unclassified data
cannot be processed.

Regulatory: GDPR Art. 5(1)(f), ISO 27001 A.8.2.1, NIST SP 800-53 RA-2
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import ClassificationLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireDataClassificationAssignedSpecs",
    "require_data_classification_assigned",
]


class RequireDataClassificationAssignedSpecs(BaseModel):
    """Specs for require data classification assigned phrase."""

    # inputs
    resource_id: UUID
    # outputs
    classification: ClassificationLevel | None = None


require_data_classification_assigned_operable = Operable.from_structure(
    RequireDataClassificationAssignedSpecs
)


@canon_phrase(
    require_data_classification_assigned_operable,
    inputs={"resource_id"},
    outputs={"resource_id", "classification"},
)
async def require_data_classification_assigned(
    options: RequireDataClassificationAssignedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that a data classification level has been assigned to a resource.

    Fail-closed gate: if no classification record exists, or if the
    classification level is not set, processing is denied. Data must
    be explicitly classified before any processing can occur.

    Regulatory:
        - GDPR Art. 5(1)(f): Integrity and confidentiality principle
          (appropriate security measures require knowing data sensitivity)
        - GDPR Art. 35: DPIA required for high-risk processing
          (classification determines risk level)
        - ISO 27001 A.8.2.1: Classification of information
        - NIST SP 800-53 RA-2: Security categorization
        - SOC 2 CC6.1: Logical and physical access controls
          (access controls depend on classification)

    Args:
        options: Options containing resource_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with resource_id and classification level.

    Raises:
        RequirementNotMetError: If no classification is assigned.
    """
    resource_id = options.resource_id

    # Query the data classification registry
    row = await select_one(
        "data_classification_registry",
        where={"resource_id": resource_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.OPTIONAL,
    )

    if not row:
        raise RequirementNotMetError(
            requirement="data_classification_assigned",
            reason=(
                f"No data classification record found for resource {resource_id}. "
                "All data must be classified before processing."
            ),
        )

    classification_value = row.get("classification_level")

    if not classification_value:
        raise RequirementNotMetError(
            requirement="data_classification_assigned",
            reason=(
                f"Resource {resource_id} has a classification record but no "
                "classification level assigned. Explicit classification required."
            ),
        )

    classification = ClassificationLevel(classification_value)

    return {
        "resource_id": resource_id,
        "classification": classification,
    }


# Export auto-generated types from the Phrase object
RequireDataClassificationAssignedOptions = require_data_classification_assigned.options_type
RequireDataClassificationAssignedResult = require_data_classification_assigned.result_type
