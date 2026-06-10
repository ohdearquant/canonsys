"""SLO/SLI definitions for governance performance.

P2 Fix: Performability - Formal SLO declarations

Defines Service Level Objectives for governance operations:
- Gate evaluation latency (p99 < 50ms)
- Policy evaluation latency (p99 < 100ms)
- Pool availability (> 99.99%)
- Decision success rate (> 99.9%)

Reference: CONSTRAINTS-001-enterprise-ilities.md §6 Performability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Any


class SLOMetric(str, Enum):
    """Standard SLO metric types."""

    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    AVAILABILITY = "availability"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"


class SLOUnit(str, Enum):
    """SLO measurement units."""

    MILLISECONDS = "ms"
    SECONDS = "s"
    PERCENT = "%"
    COUNT = "count"
    RATE = "rate"


@dataclass(frozen=True)
class SLO:
    """Service Level Objective definition.

    Attributes:
        name: SLO identifier (e.g., "gate.latency.p99")
        description: Human-readable description
        metric: Type of metric being measured
        target: Target value (e.g., 50.0 for 50ms)
        unit: Measurement unit
        window: Measurement window (default 5 minutes)
        critical: Whether SLO breach is critical
    """

    name: str
    description: str
    metric: SLOMetric
    target: float
    unit: SLOUnit = SLOUnit.MILLISECONDS
    window: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    critical: bool = False

    def check(self, value: float) -> bool:
        """Check if value meets SLO target.

        Args:
            value: Measured value

        Returns:
            True if SLO is met
        """
        if self.metric in (
            SLOMetric.LATENCY_P50,
            SLOMetric.LATENCY_P95,
            SLOMetric.LATENCY_P99,
            SLOMetric.ERROR_RATE,
        ):
            # Lower is better
            return value <= self.target
        else:
            # Higher is better (availability, success_rate, throughput)
            return value >= self.target

    def to_dict(self) -> dict[str, Any]:
        """Serialize for export."""
        return {
            "name": self.name,
            "description": self.description,
            "metric": self.metric.value,
            "target": self.target,
            "unit": self.unit.value,
            "window_seconds": self.window.total_seconds(),
            "critical": self.critical,
        }


@dataclass
class SLI:
    """Service Level Indicator - measured value for an SLO.

    Tracks rolling window of measurements for SLO evaluation.
    """

    slo: SLO
    _measurements: list[tuple[float, float]] = field(
        default_factory=list, init=False, repr=False
    )  # (timestamp, value)

    def record(self, value: float, timestamp: float | None = None) -> None:
        """Record a measurement.

        Args:
            value: Measured value
            timestamp: Measurement timestamp (defaults to now, monotonic)
        """
        import time

        ts = timestamp or time.monotonic()
        self._measurements.append((ts, value))
        self._cleanup()

    def _cleanup(self) -> None:
        """Remove measurements outside the window."""
        import time

        cutoff = time.monotonic() - self.slo.window.total_seconds()
        self._measurements = [(ts, v) for ts, v in self._measurements if ts >= cutoff]

    @property
    def current_value(self) -> float | None:
        """Get current aggregated value based on metric type."""
        if not self._measurements:
            return None

        values = [v for _, v in self._measurements]

        if self.slo.metric == SLOMetric.LATENCY_P50:
            return self._percentile(values, 50)
        elif self.slo.metric == SLOMetric.LATENCY_P95:
            return self._percentile(values, 95)
        elif self.slo.metric == SLOMetric.LATENCY_P99:
            return self._percentile(values, 99)
        elif (
            self.slo.metric in (SLOMetric.AVAILABILITY, SLOMetric.SUCCESS_RATE)
            or self.slo.metric == SLOMetric.ERROR_RATE
        ):
            return sum(values) / len(values) * 100  # As percentage
        elif self.slo.metric == SLOMetric.THROUGHPUT:
            window_seconds = self.slo.window.total_seconds()
            return len(values) / window_seconds if window_seconds > 0 else 0
        else:
            return sum(values) / len(values)

    @staticmethod
    def _percentile(values: list[float], p: int) -> float:
        """Calculate percentile."""
        sorted_values = sorted(values)
        idx = int(len(sorted_values) * p / 100)
        return sorted_values[min(idx, len(sorted_values) - 1)]

    @property
    def is_met(self) -> bool | None:
        """Check if SLO is currently met."""
        value = self.current_value
        if value is None:
            return None
        return self.slo.check(value)

    @property
    def measurement_count(self) -> int:
        """Number of measurements in current window."""
        return len(self._measurements)


@dataclass
class SLOBudget:
    """Error budget tracking for an SLO.

    Tracks how much of the error budget has been consumed.
    """

    slo: SLO
    budget_period: timedelta = field(default_factory=lambda: timedelta(days=30))

    _violations: int = field(default=0, init=False)
    _total_checks: int = field(default=0, init=False)

    def record_check(self, value: float) -> bool:
        """Record a check and return whether SLO was met.

        Args:
            value: Measured value

        Returns:
            True if SLO was met
        """
        self._total_checks += 1
        met = self.slo.check(value)
        if not met:
            self._violations += 1
        return met

    @property
    def budget_remaining(self) -> float:
        """Percentage of error budget remaining."""
        if self._total_checks == 0:
            return 100.0

        # Error budget is inverse of target
        # e.g., 99.9% availability target = 0.1% error budget
        if self.slo.metric in (SLOMetric.AVAILABILITY, SLOMetric.SUCCESS_RATE):
            allowed_error_rate = 100.0 - self.slo.target
        else:
            # For latency SLOs, we track violation percentage
            allowed_error_rate = 1.0  # 1% of requests can violate latency SLO

        actual_error_rate = (self._violations / self._total_checks) * 100
        budget_consumed = (
            actual_error_rate / allowed_error_rate * 100 if allowed_error_rate > 0 else 100.0
        )

        return max(0.0, 100.0 - budget_consumed)

    @property
    def is_exhausted(self) -> bool:
        """Check if error budget is exhausted."""
        return self.budget_remaining <= 0

    def reset(self) -> None:
        """Reset budget tracking."""
        self._violations = 0
        self._total_checks = 0


class SLORegistry:
    """Central registry for all governance SLOs.

    Pre-defines standard SLOs for Canon governance operations.
    """

    # Standard governance SLOs
    GATE_LATENCY_P99 = SLO(
        name="canon.gate.latency.p99",
        description="Gate evaluation latency (99th percentile)",
        metric=SLOMetric.LATENCY_P99,
        target=50.0,
        unit=SLOUnit.MILLISECONDS,
        window=timedelta(minutes=5),
        critical=True,
    )

    POLICY_LATENCY_P99 = SLO(
        name="canon.policy.latency.p99",
        description="Policy evaluation latency (99th percentile)",
        metric=SLOMetric.LATENCY_P99,
        target=100.0,
        unit=SLOUnit.MILLISECONDS,
        window=timedelta(minutes=5),
        critical=True,
    )

    POOL_AVAILABILITY = SLO(
        name="canon.pool.availability",
        description="Engine pool availability",
        metric=SLOMetric.AVAILABILITY,
        target=99.99,
        unit=SLOUnit.PERCENT,
        window=timedelta(hours=1),
        critical=True,
    )

    DECISION_SUCCESS_RATE = SLO(
        name="canon.decision.success_rate",
        description="Governance decision success rate (non-error)",
        metric=SLOMetric.SUCCESS_RATE,
        target=99.9,
        unit=SLOUnit.PERCENT,
        window=timedelta(hours=1),
        critical=False,
    )

    TSA_LATENCY_P99 = SLO(
        name="canon.tsa.latency.p99",
        description="TSA timestamping latency (99th percentile)",
        metric=SLOMetric.LATENCY_P99,
        target=60000.0,  # 60 seconds - TSA is slow
        unit=SLOUnit.MILLISECONDS,
        window=timedelta(minutes=15),
        critical=False,
    )

    def __init__(self) -> None:
        self._slos: dict[str, SLO] = {
            self.GATE_LATENCY_P99.name: self.GATE_LATENCY_P99,
            self.POLICY_LATENCY_P99.name: self.POLICY_LATENCY_P99,
            self.POOL_AVAILABILITY.name: self.POOL_AVAILABILITY,
            self.DECISION_SUCCESS_RATE.name: self.DECISION_SUCCESS_RATE,
            self.TSA_LATENCY_P99.name: self.TSA_LATENCY_P99,
        }
        self._slis: dict[str, SLI] = {}
        self._budgets: dict[str, SLOBudget] = {}

    def register(self, slo: SLO) -> None:
        """Register a custom SLO."""
        self._slos[slo.name] = slo

    def get(self, name: str) -> SLO | None:
        """Get SLO by name."""
        return self._slos.get(name)

    def get_sli(self, slo_name: str) -> SLI | None:
        """Get or create SLI for an SLO."""
        slo = self._slos.get(slo_name)
        if not slo:
            return None

        if slo_name not in self._slis:
            self._slis[slo_name] = SLI(slo=slo)
        return self._slis[slo_name]

    def get_budget(self, slo_name: str) -> SLOBudget | None:
        """Get or create budget tracker for an SLO."""
        slo = self._slos.get(slo_name)
        if not slo:
            return None

        if slo_name not in self._budgets:
            self._budgets[slo_name] = SLOBudget(slo=slo)
        return self._budgets[slo_name]

    def record_gate_latency(self, latency_ms: float) -> None:
        """Record gate evaluation latency."""
        sli = self.get_sli(self.GATE_LATENCY_P99.name)
        if sli:
            sli.record(latency_ms)

    def record_policy_latency(self, latency_ms: float) -> None:
        """Record policy evaluation latency."""
        sli = self.get_sli(self.POLICY_LATENCY_P99.name)
        if sli:
            sli.record(latency_ms)

    def record_pool_check(self, available: bool) -> None:
        """Record pool availability check."""
        sli = self.get_sli(self.POOL_AVAILABILITY.name)
        if sli:
            sli.record(1.0 if available else 0.0)

    def record_decision(self, success: bool) -> None:
        """Record decision outcome."""
        sli = self.get_sli(self.DECISION_SUCCESS_RATE.name)
        if sli:
            sli.record(1.0 if success else 0.0)

    def record_tsa_latency(self, latency_ms: float) -> None:
        """Record TSA timestamping latency."""
        sli = self.get_sli(self.TSA_LATENCY_P99.name)
        if sli:
            sli.record(latency_ms)

    def all_slos(self) -> list[SLO]:
        """Get all registered SLOs."""
        return list(self._slos.values())

    def status_report(self) -> dict[str, Any]:
        """Generate status report for all SLOs."""
        report = {}
        for name, slo in self._slos.items():
            sli = self._slis.get(name)
            budget = self._budgets.get(name)

            report[name] = {
                "target": slo.target,
                "unit": slo.unit.value,
                "critical": slo.critical,
                "current_value": sli.current_value if sli else None,
                "is_met": sli.is_met if sli else None,
                "measurement_count": sli.measurement_count if sli else 0,
                "budget_remaining": budget.budget_remaining if budget else None,
            }
        return report


# Global registry
_slo_registry: SLORegistry | None = None


def get_slo_registry() -> SLORegistry:
    """Get singleton SLO registry."""
    global _slo_registry
    if _slo_registry is None:
        _slo_registry = SLORegistry()
    return _slo_registry
