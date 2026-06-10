"""Consent service - thin wrapper over consent phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    cascade_revoke_consent_token,
    grant_consent_token,
    list_consent_tokens,
    revoke_consent_token,
    verify_consent_token,
)
from .types import ConsentScope

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["ConsentService"]


class ConsentService(CanonService):
    """Consent service - manages consent tokens.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="consent")

    @action(evidence_type="consent.grant")
    async def grant(self, payload: dict, ctx: RequestContext) -> dict:
        """Grant consent for a scope."""
        return await grant_consent_token(payload, ctx)

    @action(skip_evidence=True)
    async def verify(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify consent exists and is valid (hot path)."""
        return await verify_consent_token(payload, ctx)

    @action(evidence_type="consent.revoke")
    async def revoke(self, payload: dict, ctx: RequestContext) -> dict:
        """Revoke consent for a scope."""
        result = await revoke_consent_token(payload, ctx)

        # Cascade if revoking primary consent
        scope = payload.get("scope")
        if scope and scope in ConsentScope.primary():
            cascade_options = {
                "trigger_scope": scope,
                "trigger_reason": payload.get("reason"),
            }
            cascade_result = await cascade_revoke_consent_token(cascade_options, ctx)
            return {
                **result,
                "cascade": cascade_result,
            }

        return result

    @action(skip_evidence=True)
    async def list(self, payload: dict, ctx: RequestContext) -> dict:
        """List consent tokens for subject."""
        return await list_consent_tokens(payload, ctx)
