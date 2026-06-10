"""Quota configuration types."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

__all__ = ["QuotaConfig", "TenantQuota"]


@dataclass(frozen=True)
class QuotaConfig:
    """Configuration for tenant quotas.

    Attributes:
        compute_units_per_hour: Max compute units per hour
        decisions_per_minute: Max decisions per minute
        gates_per_minute: Max gate evaluations per minute
        policies_per_minute: Max policy evaluations per minute
        enabled: Whether quota enforcement is enabled
    """

    compute_units_per_hour: float = 10000.0
    decisions_per_minute: int = 100
    gates_per_minute: int = 500
    policies_per_minute: int = 200
    enabled: bool = True


@dataclass
class TenantQuota:
    """Quota tracking for a single tenant.

    Tracks multiple quota types with rolling windows.
    """

    tenant_id: str
    config: QuotaConfig = field(default_factory=QuotaConfig)

    # Usage tracking
    _compute_units: list[tuple[float, float]] = field(
        default_factory=list, init=False
    )  # (timestamp, units)
    _decisions: list[float] = field(default_factory=list, init=False)  # timestamps
    _gates: list[float] = field(default_factory=list, init=False)
    _policies: list[float] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _cleanup(self, items: list, window_seconds: float) -> list:
        """Remove items outside the window."""
        cutoff = time.monotonic() - window_seconds
        return [item for item in items if (item[0] if isinstance(item, tuple) else item) >= cutoff]

    def record_compute_units(self, units: float) -> None:
        """Record compute unit usage."""
        with self._lock:
            now = time.monotonic()
            self._compute_units.append((now, units))
            self._compute_units = self._cleanup(self._compute_units, 3600)  # 1 hour window

    def record_decision(self) -> None:
        """Record a decision."""
        with self._lock:
            self._decisions.append(time.monotonic())
            self._decisions = self._cleanup(self._decisions, 60)  # 1 minute window

    def record_gate(self) -> None:
        """Record a gate evaluation."""
        with self._lock:
            self._gates.append(time.monotonic())
            self._gates = self._cleanup(self._gates, 60)

    def record_policy(self) -> None:
        """Record a policy evaluation."""
        with self._lock:
            self._policies.append(time.monotonic())
            self._policies = self._cleanup(self._policies, 60)

    @property
    def compute_units_used(self) -> float:
        """Compute units used in the last hour."""
        with self._lock:
            self._compute_units = self._cleanup(self._compute_units, 3600)
            return sum(units for _, units in self._compute_units)

    @property
    def decisions_count(self) -> int:
        """Decisions in the last minute."""
        with self._lock:
            self._decisions = self._cleanup(self._decisions, 60)
            return len(self._decisions)

    @property
    def gates_count(self) -> int:
        """Gate evaluations in the last minute."""
        with self._lock:
            self._gates = self._cleanup(self._gates, 60)
            return len(self._gates)

    @property
    def policies_count(self) -> int:
        """Policy evaluations in the last minute."""
        with self._lock:
            self._policies = self._cleanup(self._policies, 60)
            return len(self._policies)

    def check_compute_units(self, additional: float = 0) -> bool:
        """Check if compute units quota allows additional usage."""
        return self.compute_units_used + additional <= self.config.compute_units_per_hour

    def check_decisions(self) -> bool:
        """Check if decisions quota allows another decision."""
        return self.decisions_count < self.config.decisions_per_minute

    def check_gates(self) -> bool:
        """Check if gates quota allows another gate."""
        return self.gates_count < self.config.gates_per_minute

    def check_policies(self) -> bool:
        """Check if policies quota allows another policy."""
        return self.policies_count < self.config.policies_per_minute

    def to_dict(self) -> dict[str, Any]:
        """Get quota status."""
        return {
            "tenant_id": self.tenant_id,
            "compute_units": {
                "used": self.compute_units_used,
                "limit": self.config.compute_units_per_hour,
                "remaining": max(0, self.config.compute_units_per_hour - self.compute_units_used),
            },
            "decisions": {
                "used": self.decisions_count,
                "limit": self.config.decisions_per_minute,
            },
            "gates": {
                "used": self.gates_count,
                "limit": self.config.gates_per_minute,
            },
            "policies": {
                "used": self.policies_count,
                "limit": self.config.policies_per_minute,
            },
        }
