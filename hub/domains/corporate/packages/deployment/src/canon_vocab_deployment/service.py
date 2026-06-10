"""Deployment service - thin wrapper over deployment phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    require_backup_verified,
    require_deployment_approval,
    require_monitoring_active,
    require_production_environment,
    require_rollback_tested,
    verify_backup_complete,
    verify_rollback_plan_present,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["DeploymentService"]


class DeploymentService(CanonService):
    """Deployment service - manages deployment controls.

    Thin wrapper that delegates to phrase functions.

    Regulatory context:
        - SOX Section 404 (Change management controls)
        - SOC 2 CC8.1 (Change management)
        - ISO 27001 A.12.1.2 (Change management)
        - NIST SP 800-53 (Security controls)
        - PCI DSS v4.0 (Separation of environments)
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="deployment")

    # --- Requirement phrases (mutations with evidence) ---

    @action(evidence_type="deployment.require_approval")
    async def require_approval(self, payload: dict, ctx: RequestContext) -> dict:
        """Require deployment approval gate."""
        return await require_deployment_approval(payload, ctx)

    @action(evidence_type="deployment.require_backup")
    async def require_backup(self, payload: dict, ctx: RequestContext) -> dict:
        """Require backup verification gate."""
        return await require_backup_verified(payload, ctx)

    @action(evidence_type="deployment.require_monitoring")
    async def require_monitoring(self, payload: dict, ctx: RequestContext) -> dict:
        """Require monitoring active gate."""
        return await require_monitoring_active(payload, ctx)

    @action(evidence_type="deployment.require_production_env")
    async def require_production_env(self, payload: dict, ctx: RequestContext) -> dict:
        """Require production environment gate."""
        return await require_production_environment(payload, ctx)

    @action(evidence_type="deployment.require_rollback")
    async def require_rollback(self, payload: dict, ctx: RequestContext) -> dict:
        """Require rollback tested gate."""
        return await require_rollback_tested(payload, ctx)

    # --- Verification phrases (reads, no evidence) ---

    @action(skip_evidence=True)
    async def verify_backup(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify backup is complete (hot path)."""
        return await verify_backup_complete(payload, ctx)

    @action(skip_evidence=True)
    async def verify_rollback_plan(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify rollback plan is present (hot path)."""
        return await verify_rollback_plan_present(payload, ctx)
