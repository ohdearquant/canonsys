"""Authorization service - thin wrapper over authorization phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_er_clearance,
    require_access_justification,
    require_distinct_identities,
    require_dual_approval,
    require_release_clearance,
    require_segregation_analysis,
    verify_approval_chain_complete,
    verify_role_approval,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["AuthorizationService"]


class AuthorizationService(CanonService):
    """Authorization service - manages authorization gates and approvals.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon", name="authorization"
    )

    # =========================================================================
    # Check operations (reads - no evidence)
    # =========================================================================

    @action(skip_evidence=True)
    async def check_er_clearance(self, payload: dict, ctx: RequestContext) -> dict:
        """Check Employee Relations clearance for a subject."""
        return await check_er_clearance(payload, ctx)

    # =========================================================================
    # Require operations (gates - emit evidence)
    # =========================================================================

    @action(evidence_type="authorization.require_justification")
    async def require_access_justification(self, payload: dict, ctx: RequestContext) -> dict:
        """Require documented justification for accessing sensitive resources."""
        return await require_access_justification(payload, ctx)

    @action(evidence_type="authorization.require_segregation")
    async def require_distinct_identities(self, payload: dict, ctx: RequestContext) -> dict:
        """Require that two identities are distinct for Segregation of Duties."""
        return await require_distinct_identities(payload, ctx)

    @action(evidence_type="authorization.require_dual_approval")
    async def require_dual_approval(self, payload: dict, ctx: RequestContext) -> dict:
        """Require dual (or multi) approval for high-risk operations."""
        return await require_dual_approval(payload, ctx)

    @action(evidence_type="authorization.require_clearance")
    async def require_release_clearance(self, payload: dict, ctx: RequestContext) -> dict:
        """Require proper clearance for information release."""
        return await require_release_clearance(payload, ctx)

    @action(evidence_type="authorization.require_segregation_analysis")
    async def require_segregation_analysis(self, payload: dict, ctx: RequestContext) -> dict:
        """Require segregation of duties analysis before access grant."""
        return await require_segregation_analysis(payload, ctx)

    # =========================================================================
    # Verify operations (reads - no evidence)
    # =========================================================================

    @action(skip_evidence=True)
    async def verify_approval_chain_complete(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that all required approvals in a chain are complete."""
        return await verify_approval_chain_complete(payload, ctx)

    @action(skip_evidence=True)
    async def verify_role_approval(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify that a specific role has approved a request."""
        return await verify_role_approval(payload, ctx)
