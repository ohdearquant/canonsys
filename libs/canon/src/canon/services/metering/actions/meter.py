"""Decision metering for cost attribution.

P2 Fix: Frugality - Usage tracking

Tracks governance compute units per:
- Tenant
- Decision class
- Gate/Policy type

Enables cost visibility and optimization decisions.

Persistence:
    For billing, use persist_record() or configure auto_persist=True.
    Records are stored in the usage_records table via UsageRecord entity.

Reference: CONSTRAINTS-001-enterprise-ilities.md S9 Frugality
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..types import TenantUsage, UsageRecord

if TYPE_CHECKING:
    from ..types import UsageRecordEntity

logger = logging.getLogger(__name__)

__all__ = ["DecisionMeter", "flush_meter_to_db", "get_decision_meter"]


@dataclass
class DecisionMeter:
    """Meter for tracking governance decision costs.

    Usage:
        meter = DecisionMeter()

        # Record gate evaluation
        meter.record_gate(
            tenant_id="tenant_123",
            gate_id="consent.background_check",
            decision_class="hr",
            duration_ms=15.0,
        )

        # Get tenant usage
        usage = meter.get_tenant_usage("tenant_123")
        print(f"Total units: {usage.total_units}")
    """

    # Compute unit costs (configurable)
    gate_base_cost: float = 1.0
    policy_base_cost: float = 2.0
    decision_base_cost: float = 5.0
    ms_cost_factor: float = 0.01  # Cost per ms of evaluation time

    # Internal storage
    _tenant_usage: dict[str, TenantUsage] = field(default_factory=dict, init=False, repr=False)
    _records: list[UsageRecord] = field(default_factory=list, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # Retention
    max_records: int = 100000  # Max records to keep in memory

    def _compute_units(
        self,
        base_cost: float,
        duration_ms: float,
        complexity: float = 1.0,
    ) -> float:
        """Calculate compute units.

        Args:
            base_cost: Base cost for operation type
            duration_ms: Evaluation duration
            complexity: Complexity multiplier (default 1.0)

        Returns:
            Total compute units
        """
        time_cost = duration_ms * self.ms_cost_factor
        return (base_cost + time_cost) * complexity

    def record_gate(
        self,
        tenant_id: str,
        gate_id: str,
        decision_class: str,
        duration_ms: float,
        **metadata: Any,
    ) -> UsageRecord:
        """Record gate evaluation usage.

        Args:
            tenant_id: Tenant identifier
            gate_id: Gate identifier
            decision_class: Decision class
            duration_ms: Evaluation duration
            **metadata: Additional context

        Returns:
            Created UsageRecord
        """
        units = self._compute_units(self.gate_base_cost, duration_ms)
        record = UsageRecord(
            tenant_id=tenant_id,
            decision_class=decision_class,
            operation="gate",
            compute_units=units,
            metadata={"gate_id": gate_id, "duration_ms": duration_ms, **metadata},
        )
        self._store_record(record)
        return record

    def record_policy(
        self,
        tenant_id: str,
        policy_id: str,
        decision_class: str,
        duration_ms: float,
        **metadata: Any,
    ) -> UsageRecord:
        """Record policy evaluation usage.

        Args:
            tenant_id: Tenant identifier
            policy_id: Policy identifier
            decision_class: Decision class
            duration_ms: Evaluation duration
            **metadata: Additional context

        Returns:
            Created UsageRecord
        """
        units = self._compute_units(self.policy_base_cost, duration_ms)
        record = UsageRecord(
            tenant_id=tenant_id,
            decision_class=decision_class,
            operation="policy",
            compute_units=units,
            metadata={"policy_id": policy_id, "duration_ms": duration_ms, **metadata},
        )
        self._store_record(record)
        return record

    def record_decision(
        self,
        tenant_id: str,
        decision_scope: str,
        decision_class: str,
        duration_ms: float,
        gate_count: int = 0,
        policy_count: int = 0,
        **metadata: Any,
    ) -> UsageRecord:
        """Record full decision evaluation usage.

        Args:
            tenant_id: Tenant identifier
            decision_scope: Decision scope
            decision_class: Decision class
            duration_ms: Total evaluation duration
            gate_count: Number of gates evaluated
            policy_count: Number of policies evaluated
            **metadata: Additional context

        Returns:
            Created UsageRecord
        """
        # Complexity based on number of evaluations
        complexity = 1.0 + (gate_count * 0.1) + (policy_count * 0.2)
        units = self._compute_units(self.decision_base_cost, duration_ms, complexity)

        record = UsageRecord(
            tenant_id=tenant_id,
            decision_class=decision_class,
            operation="decision",
            compute_units=units,
            metadata={
                "decision_scope": decision_scope,
                "duration_ms": duration_ms,
                "gate_count": gate_count,
                "policy_count": policy_count,
                **metadata,
            },
        )
        self._store_record(record)
        return record

    def _store_record(self, record: UsageRecord) -> None:
        """Store a usage record (thread-safe)."""
        with self._lock:
            # Store in records list
            self._records.append(record)

            # Trim if over limit
            if len(self._records) > self.max_records:
                self._records = self._records[-self.max_records :]

            # Update tenant usage
            if record.tenant_id not in self._tenant_usage:
                self._tenant_usage[record.tenant_id] = TenantUsage(tenant_id=record.tenant_id)
            self._tenant_usage[record.tenant_id].record(record)

    def get_tenant_usage(self, tenant_id: str) -> TenantUsage | None:
        """Get usage for a specific tenant."""
        with self._lock:
            return self._tenant_usage.get(tenant_id)

    def get_all_tenant_usage(self) -> dict[str, TenantUsage]:
        """Get usage for all tenants."""
        with self._lock:
            return dict(self._tenant_usage)

    def get_recent_records(self, limit: int = 100) -> list[UsageRecord]:
        """Get recent usage records."""
        with self._lock:
            return list(self._records[-limit:])

    def total_units(self) -> float:
        """Get total compute units across all tenants."""
        with self._lock:
            return sum(u.total_units for u in self._tenant_usage.values())

    def reset(self) -> None:
        """Reset all usage tracking."""
        with self._lock:
            self._tenant_usage.clear()
            self._records.clear()

    # =========================================================================
    # Persistence for Billing
    # =========================================================================

    def to_persistent_record(
        self,
        record: UsageRecord,
    ) -> UsageRecordEntity:
        """Convert in-memory UsageRecord to persistent UsageRecord entity.

        Args:
            record: In-memory usage record

        Returns:
            Persistent UsageRecord entity ready for database insertion
        """
        from ..types import UsageRecordContent, UsageRecordEntity

        if record.operation == "gate":
            content = UsageRecordContent.for_gate(
                tenant_id=record.tenant_id,
                gate_id=record.metadata.get("gate_id", "unknown"),
                duration_ms=record.metadata.get("duration_ms", 0.0),
                decision_class=record.decision_class,
                compute_units=record.compute_units,
            )
        elif record.operation == "policy":
            content = UsageRecordContent.for_policy(
                tenant_id=record.tenant_id,
                policy_id=record.metadata.get("policy_id", "unknown"),
                duration_ms=record.metadata.get("duration_ms", 0.0),
                decision_class=record.decision_class,
                enforcement=record.metadata.get("enforcement"),
                compute_units=record.compute_units,
            )
        else:  # decision
            content = UsageRecordContent.for_decision(
                tenant_id=record.tenant_id,
                decision_scope=record.metadata.get("decision_scope", "unknown"),
                duration_ms=record.metadata.get("duration_ms", 0.0),
                decision_class=record.decision_class,
                gate_count=record.metadata.get("gate_count", 0),
                policy_count=record.metadata.get("policy_count", 0),
                compute_units=record.compute_units,
            )

        return UsageRecordEntity(content=content)

    async def persist_record(
        self,
        record: UsageRecord,
        conn: Any,
    ) -> UsageRecordEntity:
        """Persist a single usage record to the database.

        Args:
            record: In-memory usage record to persist
            conn: Database connection

        Returns:
            Inserted UsageRecord entity
        """
        entity = self.to_persistent_record(record)
        await entity.insert(conn)
        return entity

    async def persist_recent(
        self,
        conn: Any,
        limit: int = 100,
    ) -> int:
        """Persist recent in-memory records to database.

        Args:
            conn: Database connection
            limit: Max records to persist

        Returns:
            Number of records persisted
        """
        records = self.get_recent_records(limit)
        count = 0

        for record in records:
            try:
                await self.persist_record(record, conn)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to persist usage record: {e}")

        return count

    async def flush_to_db(
        self,
        conn: Any,
        batch_size: int = 100,
    ) -> int:
        """Flush all in-memory records to database.

        Use this for periodic persistence (e.g., every minute).

        Args:
            conn: Database connection
            batch_size: Records per batch

        Returns:
            Total records persisted
        """
        total = 0

        with self._lock:
            records = list(self._records)
            self._records.clear()

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            for record in batch:
                try:
                    await self.persist_record(record, conn)
                    total += 1
                except Exception as e:
                    logger.warning(f"Failed to persist usage record: {e}")
                    # Re-add failed records back to memory
                    with self._lock:
                        self._records.append(record)

        return total


# Global meter
_decision_meter: DecisionMeter | None = None


def get_decision_meter() -> DecisionMeter:
    """Get singleton decision meter."""
    global _decision_meter
    if _decision_meter is None:
        _decision_meter = DecisionMeter()
    return _decision_meter


async def flush_meter_to_db(conn: Any) -> int:
    """Convenience function to flush global meter to database.

    Call this periodically (e.g., every minute) or on shutdown
    to ensure billing records are persisted.

    Args:
        conn: Database connection

    Returns:
        Number of records flushed
    """
    meter = get_decision_meter()
    return await meter.flush_to_db(conn)
