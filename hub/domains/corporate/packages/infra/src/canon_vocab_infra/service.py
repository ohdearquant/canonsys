"""Infrastructure service - thin wrapper over infra phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.

Regulatory Context:
    - SOC 2 CC7.5 (Recovery procedures)
    - ISO 27001 A.17 (Business continuity)
    - ISO 27001 A.12.3 (Backup policy)
    - PCI DSS Req. 12.10 (Incident response)
    - NIST 800-53 SC-7 (Boundary protection)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    check_dr_test_cooldown,
    derive_data_loss_risk,
    derive_degraded_hours_last_30d,
    derive_dependent_backup_count,
    derive_rows_read_band,
    derive_subdomain_depth,
    derive_tag_risk_class,
    derive_utilization_volatility,
    derive_write_acceptance_mode,
    verify_traffic_drained,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = ["InfraService"]


class InfraService(CanonService):
    """Infrastructure service - manages operational readiness and compliance.

    Thin wrapper that delegates to phrase functions.
    All operations are read-only derivations/checks (skip_evidence=True).
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="infra")

    @action(skip_evidence=True)
    async def check_dr_cooldown(self, payload: dict, ctx: RequestContext) -> dict:
        """Check DR test cooldown period (SOC 2 CC7.5)."""
        return await check_dr_test_cooldown(payload, ctx)

    @action(skip_evidence=True)
    async def derive_data_loss_risk(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive data loss risk classification (ISO 27001 A.12.3)."""
        return await derive_data_loss_risk(payload, ctx)

    @action(skip_evidence=True)
    async def derive_degraded_hours(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive SLA degraded hours in last 30 days."""
        return await derive_degraded_hours_last_30d(payload, ctx)

    @action(skip_evidence=True)
    async def derive_dependent_backups(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive count of dependent backup jobs (ISO 27001 A.12.3)."""
        return await derive_dependent_backup_count(payload, ctx)

    @action(skip_evidence=True)
    async def derive_rows_read_band(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive query exfiltration risk band (NIST 800-53 SC-7)."""
        return await derive_rows_read_band(payload, ctx)

    @action(skip_evidence=True)
    async def derive_subdomain_depth(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive subdomain depth for blast radius analysis."""
        return await derive_subdomain_depth(payload, ctx)

    @action(skip_evidence=True)
    async def derive_tag_risk_class(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive tag-based risk classification."""
        return await derive_tag_risk_class(payload, ctx)

    @action(skip_evidence=True)
    async def derive_utilization_volatility(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive resource utilization volatility."""
        return await derive_utilization_volatility(payload, ctx)

    @action(skip_evidence=True)
    async def derive_write_acceptance_mode(self, payload: dict, ctx: RequestContext) -> dict:
        """Derive write acceptance mode based on system state."""
        return await derive_write_acceptance_mode(payload, ctx)

    @action(skip_evidence=True)
    async def verify_traffic_drained(self, payload: dict, ctx: RequestContext) -> dict:
        """Verify traffic has been drained from endpoint (SOC 2 CC7.1)."""
        return await verify_traffic_drained(payload, ctx)
