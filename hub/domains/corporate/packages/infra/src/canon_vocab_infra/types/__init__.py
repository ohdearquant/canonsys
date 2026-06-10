"""Infrastructure feature types.

Contains enums and frozen result dataclasses for infrastructure operations.
All types are immutable for audit integrity.

Regulatory context:
    - SOC 2 CC7.5 (Recovery procedures)
    - ISO 27001 A.17 (Business continuity)
    - PCI DSS Req. 12.10 (Incident response)
    - SLA compliance requirements
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

__all__ = [
    "DRTestCooldownResult",
    "DataLossRiskResult",
    "DegradedHoursResult",
    "DependentBackupsResult",
    "RiskBand",
    "RowsReadBandResult",
    "SubdomainDepthResult",
    "TagRiskClass",
    "TagRiskClassResult",
    "TrafficDrainResult",
    "UtilizationVolatilityResult",
    "WriteAcceptanceModeResult",
    "WriteMode",
]


# =============================================================================
# Literal Types
# =============================================================================

RiskBand = Literal["low", "medium", "high", "critical"]
"""Risk classification band for data loss and query volume assessment."""

TagRiskClass = Literal["immutable", "protected", "mutable", "ephemeral"]
"""Tag mutability risk classification levels."""

WriteMode = Literal["strict", "relaxed", "emergency"]
"""Write acceptance modes based on system health."""


# =============================================================================
# Check/Count Result Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class DRTestCooldownResult:
    """Result of DR test cooldown check.

    Attributes:
        cooldown_active: True if cooldown period is still in effect.
        last_test: Timestamp of most recent DR test (None if never tested).
        cooldown_hours: Configured cooldown period in hours.
        hours_remaining: Hours until cooldown expires (None if not active).
    """

    cooldown_active: bool
    last_test: datetime | None
    cooldown_hours: int
    hours_remaining: int | None


@dataclass(frozen=True, slots=True)
class DegradedHoursResult:
    """Result of degraded hours count.

    Attributes:
        hours: Total hours in degraded state over past 30 days.
        incidents: Number of separate degradation incidents.
        is_above_sla: True if degraded hours exceed SLA allowance.
        sla_hours: Configured SLA threshold in hours.
    """

    hours: int
    incidents: int
    is_above_sla: bool
    sla_hours: int


@dataclass(frozen=True, slots=True)
class DependentBackupsResult:
    """Result of dependent backup count.

    Attributes:
        count: Number of backups depending on this resource.
        resource_id: ID of the resource being evaluated.
        backup_ids: IDs of dependent backups.
        oldest_backup: Timestamp of oldest dependent backup (None if none).
    """

    count: int
    resource_id: UUID
    backup_ids: tuple[UUID, ...]
    oldest_backup: datetime | None


# =============================================================================
# Derivation Result Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class DataLossRiskResult:
    """Result of data loss risk derivation.

    Attributes:
        risk_band: Classified risk level (low, medium, high, critical).
        rpo_seconds: Recovery Point Objective in seconds.
        data_criticality: Classification of data importance.
        backup_available: Whether a backup exists for recovery.
        replication_lag_seconds: Lag in replica (None if no replica).
    """

    risk_band: RiskBand
    rpo_seconds: int
    data_criticality: str
    backup_available: bool
    replication_lag_seconds: int | None


@dataclass(frozen=True, slots=True)
class RowsReadBandResult:
    """Result of rows read band derivation.

    Attributes:
        band: Risk band based on row count (low, medium, high, critical).
        rows_read: Actual number of rows read by the query.
        threshold_low: Low threshold boundary.
        threshold_high: High threshold boundary.
        is_bulk_query: Whether this qualifies as a bulk data access.
    """

    band: RiskBand
    rows_read: int
    threshold_low: int
    threshold_high: int
    is_bulk_query: bool


@dataclass(frozen=True, slots=True)
class SubdomainDepthResult:
    """Result of subdomain depth analysis.

    Attributes:
        depth: Number of subdomain levels (e.g., a.b.c.example.com = 3).
        domain: The analyzed domain string.
        is_suspicious: Whether depth exceeds safe threshold.
        max_safe_depth: The configured maximum safe depth.
    """

    depth: int
    domain: str
    is_suspicious: bool
    max_safe_depth: int


@dataclass(frozen=True, slots=True)
class TagRiskClassResult:
    """Result of tag risk classification.

    Attributes:
        risk_class: Classification level (immutable, protected, mutable, ephemeral).
        tag_name: Name of the tag being classified.
        change_frequency: Number of changes in observation period.
        last_changed: Timestamp of most recent change (None if never changed).
    """

    risk_class: TagRiskClass
    tag_name: str
    change_frequency: int
    last_changed: datetime | None


@dataclass(frozen=True, slots=True)
class UtilizationVolatilityResult:
    """Result of utilization volatility analysis.

    Attributes:
        volatility_pct: Calculated volatility as percentage (0-100+).
        is_volatile: True if volatility exceeds threshold.
        samples: Number of data points in analysis window.
        threshold_pct: Configured volatility threshold.
    """

    volatility_pct: int
    is_volatile: bool
    samples: int
    threshold_pct: int


@dataclass(frozen=True, slots=True)
class WriteAcceptanceModeResult:
    """Result of write acceptance mode derivation.

    Attributes:
        mode: The derived write mode (strict, relaxed, emergency).
        reason: Explanation for the mode selection.
        degradation_detected: Whether system degradation is active.
        fallback_available: Whether fallback write path exists.
    """

    mode: WriteMode
    reason: str
    degradation_detected: bool
    fallback_available: bool


# =============================================================================
# Verification Result Dataclasses
# =============================================================================


@dataclass(frozen=True, slots=True)
class TrafficDrainResult:
    """Result of traffic drain verification.

    Attributes:
        drained: True if endpoint has no active connections.
        endpoint_id: ID of the endpoint being verified.
        active_connections: Current number of active connections.
        drain_started_at: When drain operation began (None if not started).
        drain_duration_seconds: Time since drain started (None if not started).
    """

    drained: bool
    endpoint_id: UUID
    active_connections: int
    drain_started_at: datetime | None
    drain_duration_seconds: int | None
