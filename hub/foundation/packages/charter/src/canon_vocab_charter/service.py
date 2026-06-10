"""Charter service - thin wrapper over charter phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import activate_charter, bind_surface, create_charter, evaluate_decision

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["CharterService"]


class CharterService(CanonService):
    """Charter service - manages governance charters.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="charter")

    @action(evidence_type="charter.create")
    async def create(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a new charter in DRAFT status."""
        return await create_charter(payload, ctx)

    @action(evidence_type="charter.activate")
    async def activate(self, payload: dict, ctx: RequestContext) -> dict:
        """Activate a charter (DRAFT -> ACTIVE)."""
        return await activate_charter(payload, ctx)

    @action(evidence_type="charter.bind_surface")
    async def bind_surface(self, payload: dict, ctx: RequestContext) -> dict:
        """Bind a decision surface to a charter."""
        return await bind_surface(payload, ctx)

    @action(skip_evidence=True)
    async def evaluate(self, payload: dict, ctx: RequestContext) -> dict:
        """Evaluate a decision against charter policy (hot path)."""
        return await evaluate_decision(payload, ctx)
