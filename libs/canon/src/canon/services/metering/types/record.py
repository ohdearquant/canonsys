"""Persistent usage record entity for billing.

This is the database entity for usage records.
For in-memory tracking, see usage.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from canon.entities.entity import ContentModel, Entity, register_entity
from canon.entities.shared import Tenant
from kron.types import FK
from kron.utils import now_utc

from .operation import UsageOperation

__all__ = (
    "UsageRecordContent",
    "UsageRecordEntity",
)


class UsageRecordContent(ContentModel):
    """Immutable record of governance usage for billing.

    Each record represents a single metered operation (gate, policy, or decision).
    Records are insert-only to ensure billing audit trail integrity.

    Usage:
        record = UsageRecordEntity(content=UsageRecordContent.for_gate(
            tenant_id=tenant_id,
            gate_id="consent.background_check",
            duration_ms=15.0,
            decision_class="hr",
        ))
    """

    # Foreign keys
    tenant_id: FK[Tenant]

    # Operation details
    operation: UsageOperation
    operation_id: str  # gate_id, policy_id, or decision_scope
    decision_class: str = "default"

    # Billing metrics
    compute_units: float
    duration_ms: float

    # Timestamps
    recorded_at: datetime = Field(default_factory=now_utc)
    billing_period: str = ""  # Set via model_post_init based on recorded_at

    # Additional context (non-billing, for debugging)
    metadata_extra: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Set billing_period from recorded_at if not provided."""
        if not self.billing_period:
            # Format: "YYYY-MM" for monthly billing
            object.__setattr__(self, "billing_period", self.recorded_at.strftime("%Y-%m"))

    @classmethod
    def for_gate(
        cls,
        tenant_id: str,
        gate_id: str,
        duration_ms: float,
        decision_class: str = "default",
        compute_units: float | None = None,
    ) -> UsageRecordContent:
        """Create content for gate usage record."""
        # Default compute units calculation
        if compute_units is None:
            compute_units = 1.0 + (duration_ms * 0.01)
        return cls(
            tenant_id=tenant_id,
            operation=UsageOperation.GATE,
            operation_id=gate_id,
            decision_class=decision_class,
            compute_units=compute_units,
            duration_ms=duration_ms,
        )

    @classmethod
    def for_policy(
        cls,
        tenant_id: str,
        policy_id: str,
        duration_ms: float,
        decision_class: str = "default",
        enforcement: str | None = None,
        compute_units: float | None = None,
    ) -> UsageRecordContent:
        """Create content for policy usage record."""
        if compute_units is None:
            compute_units = 2.0 + (duration_ms * 0.01)
        return cls(
            tenant_id=tenant_id,
            operation=UsageOperation.POLICY,
            operation_id=policy_id,
            decision_class=decision_class,
            compute_units=compute_units,
            duration_ms=duration_ms,
            metadata_extra={"enforcement": enforcement} if enforcement else {},
        )

    @classmethod
    def for_decision(
        cls,
        tenant_id: str,
        decision_scope: str,
        duration_ms: float,
        decision_class: str = "default",
        gate_count: int = 0,
        policy_count: int = 0,
        compute_units: float | None = None,
    ) -> UsageRecordContent:
        """Create content for decision usage record."""
        if compute_units is None:
            complexity = 1.0 + (gate_count * 0.1) + (policy_count * 0.2)
            compute_units = (5.0 + (duration_ms * 0.01)) * complexity
        return cls(
            tenant_id=tenant_id,
            operation=UsageOperation.DECISION,
            operation_id=decision_scope,
            decision_class=decision_class,
            compute_units=compute_units,
            duration_ms=duration_ms,
            metadata_extra={"gate_count": gate_count, "policy_count": policy_count},
        )


@register_entity("usage_records", immutable=True)
class UsageRecordEntity(Entity):
    """Immutable entity for usage record billing audit trail."""

    content: UsageRecordContent
