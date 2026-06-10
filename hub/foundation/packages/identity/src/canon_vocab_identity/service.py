"""Identity service - thin wrapper over identity phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    assess_scope_risk_level,
    get_ca_level,
    verify_assurance_equivalent,
    verify_idp_posture_attestation,
    verify_request_source_authenticated,
    verify_strong_auth_posture,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["IdentityService"]


class IdentityService(CanonService):
    """Identity service - manages identity verification and assessment.

    Thin wrapper that delegates to phrase functions.
    All operations are reads/verifications (no evidence emission).
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="identity")

    # =========================================================================
    # Assessment operations (reads - no evidence)
    # =========================================================================

    @action(skip_evidence=True)
    async def assess_scope_risk_level(self, payload: dict, ctx: RequestContext) -> dict:
        """Assess risk level of an access scope."""
        return await assess_scope_risk_level(payload, ctx)

    # =========================================================================
    # Query operations (reads - no evidence)
    # =========================================================================

    @action(skip_evidence=True)
    async def get_ca_level(self, payload: dict, ctx: RequestContext) -> dict:
        """Get certificate authority trust level for a certificate."""
        return await get_ca_level(payload, ctx)

    # =========================================================================
    # Verify operations (reads - no evidence)
    # =========================================================================

    @action(skip_evidence=True)
    async def verify_assurance_equivalent(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify source AAL is equivalent to or higher than target."""
        return await verify_assurance_equivalent(payload, ctx)

    @action(skip_evidence=True)
    async def verify_idp_posture_attestation(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify identity provider has valid security posture attestation."""
        return await verify_idp_posture_attestation(payload, ctx)

    @action(skip_evidence=True)
    async def verify_request_source_authenticated(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify the source of a request is properly authenticated."""
        return await verify_request_source_authenticated(payload, ctx)

    @action(skip_evidence=True)
    async def verify_strong_auth_posture(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify subject has required authentication posture."""
        return await verify_strong_auth_posture(payload, ctx)
