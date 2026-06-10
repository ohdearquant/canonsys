"""Tenant quota enforcement for cost control.

P2 Fix: Frugality - Tenant-level quotas

Prevents unbounded resource consumption through:
- Per-tenant compute unit limits
- Per-decision-class rate limits
- Graceful quota exceeded handling

Reference: CONSTRAINTS-001-enterprise-ilities.md S9 Frugality
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ..exceptions import QuotaExceededError
from ..types import QuotaConfig, TenantQuota

__all__ = ["QuotaEnforcer", "get_quota_enforcer"]


@dataclass
class QuotaEnforcer:
    """Enforces tenant quotas.

    Usage:
        enforcer = QuotaEnforcer()

        # Before evaluation
        enforcer.check_decision("tenant_123")  # Raises if quota exceeded

        # After evaluation
        enforcer.record_decision("tenant_123", compute_units=5.0)
    """

    default_config: QuotaConfig = field(default_factory=QuotaConfig)

    # Per-tenant quotas
    _tenant_quotas: dict[str, TenantQuota] = field(default_factory=dict, init=False)
    # Custom configs per tenant
    _tenant_configs: dict[str, QuotaConfig] = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _get_quota(self, tenant_id: str) -> TenantQuota:
        """Get or create quota tracker for tenant."""
        with self._lock:
            if tenant_id not in self._tenant_quotas:
                config = self._tenant_configs.get(tenant_id, self.default_config)
                self._tenant_quotas[tenant_id] = TenantQuota(
                    tenant_id=tenant_id,
                    config=config,
                )
            return self._tenant_quotas[tenant_id]

    def set_tenant_config(self, tenant_id: str, config: QuotaConfig) -> None:
        """Set custom quota config for a tenant."""
        with self._lock:
            self._tenant_configs[tenant_id] = config
            # Update existing quota if present
            if tenant_id in self._tenant_quotas:
                self._tenant_quotas[tenant_id].config = config

    def check_decision(self, tenant_id: str, compute_units: float = 5.0) -> None:
        """Check if tenant can make a decision.

        Args:
            tenant_id: Tenant identifier
            compute_units: Expected compute units

        Raises:
            QuotaExceededError: If any quota would be exceeded
        """
        if not self.default_config.enabled:
            return

        quota = self._get_quota(tenant_id)

        if not quota.check_decisions():
            raise QuotaExceededError(
                tenant_id=tenant_id,
                quota_type="decisions_per_minute",
                limit=quota.config.decisions_per_minute,
                current=quota.decisions_count,
                reset_at=time.time() + 60,
            )

        if not quota.check_compute_units(compute_units):
            raise QuotaExceededError(
                tenant_id=tenant_id,
                quota_type="compute_units_per_hour",
                limit=quota.config.compute_units_per_hour,
                current=quota.compute_units_used,
                reset_at=time.time() + 3600,
            )

    def check_gate(self, tenant_id: str) -> None:
        """Check if tenant can evaluate a gate."""
        if not self.default_config.enabled:
            return

        quota = self._get_quota(tenant_id)
        if not quota.check_gates():
            raise QuotaExceededError(
                tenant_id=tenant_id,
                quota_type="gates_per_minute",
                limit=quota.config.gates_per_minute,
                current=quota.gates_count,
                reset_at=time.time() + 60,
            )

    def check_policy(self, tenant_id: str) -> None:
        """Check if tenant can evaluate a policy."""
        if not self.default_config.enabled:
            return

        quota = self._get_quota(tenant_id)
        if not quota.check_policies():
            raise QuotaExceededError(
                tenant_id=tenant_id,
                quota_type="policies_per_minute",
                limit=quota.config.policies_per_minute,
                current=quota.policies_count,
                reset_at=time.time() + 60,
            )

    def record_decision(self, tenant_id: str, compute_units: float) -> None:
        """Record a decision was made."""
        quota = self._get_quota(tenant_id)
        quota.record_decision()
        quota.record_compute_units(compute_units)

    def record_gate(self, tenant_id: str, compute_units: float) -> None:
        """Record a gate was evaluated."""
        quota = self._get_quota(tenant_id)
        quota.record_gate()
        quota.record_compute_units(compute_units)

    def record_policy(self, tenant_id: str, compute_units: float) -> None:
        """Record a policy was evaluated."""
        quota = self._get_quota(tenant_id)
        quota.record_policy()
        quota.record_compute_units(compute_units)

    def get_tenant_status(self, tenant_id: str) -> dict[str, Any]:
        """Get quota status for a tenant."""
        quota = self._get_quota(tenant_id)
        return quota.to_dict()

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        """Get quota status for all tenants."""
        with self._lock:
            return {tid: q.to_dict() for tid, q in self._tenant_quotas.items()}


# Global enforcer
_quota_enforcer: QuotaEnforcer | None = None


def get_quota_enforcer() -> QuotaEnforcer:
    """Get singleton quota enforcer."""
    global _quota_enforcer
    if _quota_enforcer is None:
        _quota_enforcer = QuotaEnforcer()
    return _quota_enforcer
