"""Metering feature - vertical slice for cost attribution and tenant quotas.

This module provides the complete metering domain implementation:
- Types: UsageOperation, UsageRecord, TenantUsage, QuotaConfig, TenantQuota
- Actions: DecisionMeter, QuotaEnforcer
- Exceptions: QuotaExceededError
- Persistence: UsageRecordContent, UsageRecordEntity

Usage:
    from hub.services.metering import (
        # Types
        UsageOperation,
        UsageRecord,
        TenantUsage,
        QuotaConfig,
        TenantQuota,
        # Actions
        DecisionMeter,
        get_decision_meter,
        flush_meter_to_db,
        QuotaEnforcer,
        get_quota_enforcer,
        # Exceptions
        QuotaExceededError,
    )

Billing Integration:
    # Periodic flush (e.g., every minute or on shutdown)
    from hub.services.metering import flush_meter_to_db
    await flush_meter_to_db(conn)

    # Query usage for billing
    from hub.services.metering import UsageRecordEntity
    totals = await UsageRecordEntity.sum_by_tenant(conn, tenant_id, billing_period="2026-01")

Reference: CONSTRAINTS-001-enterprise-ilities.md S9 Frugality
"""

# Actions (meter and enforcer)
from .actions import (
    DecisionMeter,
    QuotaEnforcer,
    flush_meter_to_db,
    get_decision_meter,
    get_quota_enforcer,
)

# Exceptions
from .exceptions import QuotaExceededError

# Types
from .types import (
    QuotaConfig,
    TenantQuota,
    TenantUsage,
    UsageOperation,
    UsageRecord,
    UsageRecordContent,
    UsageRecordEntity,
)

__all__ = [
    # Types - Operation
    "UsageOperation",
    # Types - In-memory usage
    "UsageRecord",
    "TenantUsage",
    # Types - Persistent entity
    "UsageRecordContent",
    "UsageRecordEntity",
    # Types - Quota
    "QuotaConfig",
    "TenantQuota",
    # Actions - Metering
    "DecisionMeter",
    "get_decision_meter",
    "flush_meter_to_db",
    # Actions - Quota enforcement
    "QuotaEnforcer",
    "get_quota_enforcer",
    # Exceptions
    "QuotaExceededError",
]
