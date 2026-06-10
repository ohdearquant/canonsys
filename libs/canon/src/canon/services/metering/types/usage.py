"""In-memory usage tracking types.

These types are used for in-memory metering before persistence.
For the persistent entity, see record.py.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from kron.utils import now_utc

__all__ = ["TenantUsage", "UsageRecord"]


@dataclass(frozen=True)
class UsageRecord:
    """Single usage record for cost attribution.

    This is the in-memory representation used during metering.
    For persistent storage, convert to UsageRecordEntity via DecisionMeter.

    Attributes:
        tenant_id: Tenant identifier
        decision_class: Decision class (hr, finance, infra, etc.)
        operation: Operation type (gate, policy, decision)
        compute_units: Compute units consumed
        timestamp: When usage occurred
        metadata: Additional context
    """

    tenant_id: str
    decision_class: str
    operation: str
    compute_units: float
    timestamp: datetime = field(default_factory=now_utc)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for export."""
        return {
            "tenant_id": self.tenant_id,
            "decision_class": self.decision_class,
            "operation": self.operation,
            "compute_units": self.compute_units,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class TenantUsage:
    """Aggregated usage for a tenant.

    Tracks usage by decision class and operation type.
    """

    tenant_id: str
    _usage_by_class: dict[str, float] = field(
        default_factory=lambda: defaultdict(float), init=False
    )
    _usage_by_operation: dict[str, float] = field(
        default_factory=lambda: defaultdict(float), init=False
    )
    _total_units: float = field(default=0.0, init=False)
    _record_count: int = field(default=0, init=False)

    def record(self, record: UsageRecord) -> None:
        """Add a usage record."""
        self._usage_by_class[record.decision_class] += record.compute_units
        self._usage_by_operation[record.operation] += record.compute_units
        self._total_units += record.compute_units
        self._record_count += 1

    @property
    def total_units(self) -> float:
        """Total compute units consumed."""
        return self._total_units

    @property
    def record_count(self) -> int:
        """Number of records."""
        return self._record_count

    def usage_by_class(self) -> dict[str, float]:
        """Usage breakdown by decision class."""
        return dict(self._usage_by_class)

    def usage_by_operation(self) -> dict[str, float]:
        """Usage breakdown by operation type."""
        return dict(self._usage_by_operation)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for export."""
        return {
            "tenant_id": self.tenant_id,
            "total_units": self._total_units,
            "record_count": self._record_count,
            "by_class": self.usage_by_class(),
            "by_operation": self.usage_by_operation(),
        }
