"""Justification service - thin wrapper over justification phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory Context:
    - SOX Section 404 (Documentation requirements)
    - Employment law (Termination documentation)
    - Financial regulations (Transaction justification)
    - Transfer pricing regulations (Intercompany documentation)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    classify_justification,
    map_reason_code_to_evidence,
    map_waiver_reason_to_evidence,
    require_type_specific_evidence,
    validate_business_justification,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["JustificationService"]


class JustificationService(CanonService):
    """Justification service - manages business justifications.

    Thin wrapper that delegates to phrase functions.
    All phrases are read-only classifications/mappings/validations (no mutations).
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon", name="justification"
    )

    @action(skip_evidence=True)
    async def classify(self, payload: dict, ctx: RequestContext) -> dict:
        """Classify justification type and determine required evidence."""
        return await classify_justification(payload, ctx)

    @action(skip_evidence=True)
    async def map_reason_code(self, payload: dict, ctx: RequestContext) -> dict:
        """Map reason code to required evidence types."""
        return await map_reason_code_to_evidence(payload, ctx)

    @action(skip_evidence=True)
    async def map_waiver_reason(self, payload: dict, ctx: RequestContext) -> dict:
        """Map waiver reason to required evidence types."""
        return await map_waiver_reason_to_evidence(payload, ctx)

    @action(skip_evidence=True)
    async def require_type_specific_evidence(self, payload: dict, ctx: RequestContext) -> dict:
        """Get evidence requirements specific to a transfer type."""
        return await require_type_specific_evidence(payload, ctx)

    @action(skip_evidence=True)
    async def validate(self, payload: dict, ctx: RequestContext) -> dict:
        """Validate business justification meets requirements."""
        return await validate_business_justification(payload, ctx)
