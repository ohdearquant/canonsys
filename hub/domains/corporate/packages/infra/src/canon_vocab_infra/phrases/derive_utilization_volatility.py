"""Derive utilization volatility for a resource.

Analyzes resource utilization variance over a lookback window to
identify unstable systems.

Regulatory Context:
    - SOC 2 CC7.2: System anomaly monitoring
    - ISO 27001 A.12.1.3: Resource usage monitoring
    - SLA Compliance: Performance stability commitments
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .constants import DEFAULT_LOOKBACK_HOURS, DEFAULT_THRESHOLD_PCT

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveUtilizationVolatilitySpecs", "derive_utilization_volatility"]


class DeriveUtilizationVolatilitySpecs(BaseModel):
    """Specs for utilization volatility derivation phrase."""

    # inputs
    resource_id: UUID
    lookback_hours: int = DEFAULT_LOOKBACK_HOURS
    threshold_pct: int = DEFAULT_THRESHOLD_PCT
    # outputs
    volatility_pct: int | None = None
    is_volatile: bool | None = None
    samples: int | None = None


@canon_phrase(
    Operable.from_structure(DeriveUtilizationVolatilitySpecs),
    inputs={"resource_id", "lookback_hours", "threshold_pct"},
    outputs={"volatility_pct", "is_volatile", "samples", "threshold_pct"},
)
async def derive_utilization_volatility(
    options: DeriveUtilizationVolatilitySpecs,
    ctx: RequestContext,
) -> dict:
    """Derive utilization volatility for a resource.

    Analyzes resource utilization variance over a lookback window to
    identify unstable systems. High volatility may indicate capacity
    issues, load spikes, or misconfiguration.

    Regulatory Citations:
        - SOC 2 CC7.2: "The entity monitors system components and the
          operation of those components for anomalies that are indicative
          of malicious acts."
        - ISO 27001 A.12.1.3: "The use of resources shall be monitored,
          tuned and projections made of future capacity requirements."
        - SLA Compliance: Maintains performance stability commitments.

    Args:
        options: Derivation options (resource_id, lookback_hours, threshold_pct)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with volatility_pct, is_volatile, samples, threshold_pct

    Volatility Calculation:
        Coefficient of variation (stddev / mean * 100) over the
        lookback window. Values > threshold indicate instability.
    """
    resource_id = options.resource_id
    lookback_hours = options.lookback_hours
    threshold_pct = options.threshold_pct
    _ = resource_id, lookback_hours  # Will query utilization_metrics

    # Placeholder - would calculate actual volatility from metrics
    # In production: query time series, calculate stddev/mean * 100
    volatility_pct = 25  # Example value
    samples = 24  # Example: hourly samples

    is_volatile = volatility_pct > threshold_pct

    return {
        "volatility_pct": volatility_pct,
        "is_volatile": is_volatile,
        "samples": samples,
        "threshold_pct": threshold_pct,
    }
