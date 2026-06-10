"""Controls service - thin wrapper over controls phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    assess_control_coverage,
    check_exploitability_status,
    derive_compensating_logging_coverage,
    derive_control_equivalence_score,
    verify_required_controls_for_tool,
    verify_sanitization_profile,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["ControlsService"]


class ControlsService(CanonService):
    """Controls service - manages security control assessments.

    Thin wrapper that delegates to phrase functions.
    All operations are read/verification - no evidence emission.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="controls")

    @action(skip_evidence=True)
    async def assess_coverage(self, payload: dict, ctx: RequestContext) -> dict:
        """Assess control coverage for a vulnerability."""
        return await assess_control_coverage(payload, ctx)

    @action(skip_evidence=True)
    async def check_exploitability(self, payload: dict, ctx: RequestContext) -> dict:
        """Check exploitability status via KEV catalog."""
        return await check_exploitability_status(payload, ctx)

    @action(skip_evidence=True)
    async def derive_equivalence(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive control equivalence score between controls."""
        return await derive_control_equivalence_score(payload, ctx)

    @action(skip_evidence=True)
    async def derive_logging_coverage(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive compensating logging coverage."""
        return await derive_compensating_logging_coverage(payload, ctx)

    @action(skip_evidence=True)
    async def verify_sanitization(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify sanitization profile covers required data types."""
        return await verify_sanitization_profile(payload, ctx)

    @action(skip_evidence=True)
    async def verify_tool_controls(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify required controls for a tool are present."""
        return await verify_required_controls_for_tool(payload, ctx)
