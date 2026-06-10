"""Scope service - thin wrapper over scope phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_environment_scope,
    create_scope_manifest,
    derive_scope_minimization,
    verify_channel_allowed,
    verify_dataset_snapshot_match,
    verify_destination_allowed,
    verify_group_membership_snapshot,
    verify_scope_definition,
    verify_scope_manifest,
    verify_stakeholder_notification_complete,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["ScopeService"]


class ScopeService(CanonService):
    """Scope service - manages scope manifests and verification.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="scope")  # type: ignore[misc]

    # =========================================================================
    # Creation Actions
    # =========================================================================

    @action(evidence_type="scope.manifest.create")
    async def create_manifest(self, payload: dict, ctx: RequestContext) -> dict:
        """Create a scope manifest with cryptographic hash."""
        return await create_scope_manifest(payload, ctx)

    # =========================================================================
    # Verification Actions
    # =========================================================================

    @action(skip_evidence=True)
    async def verify_manifest(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify scope manifest hasn't drifted (hot path)."""
        return await verify_scope_manifest(payload, ctx)

    @action(skip_evidence=True)
    async def verify_definition(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify scope is properly defined (hot path)."""
        return await verify_scope_definition(payload, ctx)

    @action(skip_evidence=True)
    async def verify_notifications(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify stakeholder notifications are complete (hot path)."""
        return await verify_stakeholder_notification_complete(payload, ctx)

    @action(skip_evidence=True)
    async def verify_group_snapshot(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify group membership snapshot (hot path)."""
        return await verify_group_membership_snapshot(payload, ctx)

    @action(skip_evidence=True)
    async def verify_dataset_snapshot(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify dataset snapshot (hot path)."""
        return await verify_dataset_snapshot_match(payload, ctx)

    @action(skip_evidence=True)
    async def verify_destination(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify destination is on allowlist (hot path)."""
        return await verify_destination_allowed(payload, ctx)

    @action(skip_evidence=True)
    async def verify_channel(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify channel is on allowlist (hot path)."""
        return await verify_channel_allowed(payload, ctx)

    # =========================================================================
    # Derivation Actions
    # =========================================================================

    @action(skip_evidence=True)
    async def derive_minimization(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive scope minimization analysis (hot path)."""
        return await derive_scope_minimization(payload, ctx)

    # =========================================================================
    # Check Actions
    # =========================================================================

    @action(skip_evidence=True)
    async def check_environment(self, payload: dict, ctx: RequestContext) -> dict:
        """Check environment scope (hot path)."""
        return await check_environment_scope(payload, ctx)
