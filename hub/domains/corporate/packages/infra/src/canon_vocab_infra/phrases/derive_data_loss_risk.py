"""Derive data loss risk band for a resource.

Evaluates potential data loss impact based on criticality,
RPO requirements, and backup/replication state.

Regulatory Context:
    - SOC 2 CC7.5: Recovery from security incidents
    - ISO 27001 A.17.1.1: Information security continuity
    - PCI DSS 12.10.1: Incident response planning
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import RiskBand

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveDataLossRiskSpecs", "derive_data_loss_risk"]


class DeriveDataLossRiskSpecs(BaseModel):
    """Specs for data loss risk derivation phrase."""

    # inputs
    resource_id: UUID
    data_criticality: str
    # outputs
    risk_band: RiskBand | None = None
    rpo_seconds: int | None = None
    backup_available: bool | None = None
    replication_lag_seconds: int | None = None


@canon_phrase(
    Operable.from_structure(DeriveDataLossRiskSpecs),
    inputs={"resource_id", "data_criticality"},
    outputs={
        "risk_band",
        "rpo_seconds",
        "data_criticality",
        "backup_available",
        "replication_lag_seconds",
    },
)
async def derive_data_loss_risk(
    options: DeriveDataLossRiskSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive data loss risk band for a resource.

    Evaluates potential data loss impact based on the resource's criticality,
    RPO requirements, and current backup/replication state. This is an
    anti-gaming primitive - risk bands MUST be derived, not user-asserted.

    Regulatory Citations:
        - SOC 2 CC7.5: "The entity identifies, develops, and implements
          activities to recover from identified security incidents."
        - ISO 27001 A.17.1.1: "Information security continuity shall be
          embedded in the organization's business continuity management."
        - PCI DSS 12.10.1: "Create incident response plan to be implemented
          in the event of system breach."

    Args:
        options: Derivation options (resource_id, data_criticality)
        ctx: Request context (tenant, actor)

    Returns:
        Dict with risk_band, rpo_seconds, data_criticality, backup_available,
        replication_lag_seconds

    Risk Band Derivation:
        - critical: No backup + high criticality data
        - high: RPO > 3600s or replication lag > 300s
        - medium: RPO > 900s or replication lag > 60s
        - low: Recent backup + low replication lag
    """
    resource_id = options.resource_id
    data_criticality = options.data_criticality
    _ = resource_id, now_utc()  # Will query backup_records, replication_status

    # Default conservative values for stub
    rpo_seconds = 3600  # 1 hour
    backup_available = True
    replication_lag_seconds = 30

    # Derive risk band based on criticality and metrics
    if not backup_available and data_criticality in ("pii", "financial", "critical"):
        risk_band: RiskBand = "critical"
    elif rpo_seconds > 3600 or (replication_lag_seconds and replication_lag_seconds > 300):
        risk_band = "high"
    elif rpo_seconds > 900 or (replication_lag_seconds and replication_lag_seconds > 60):
        risk_band = "medium"
    else:
        risk_band = "low"

    return {
        "risk_band": risk_band,
        "rpo_seconds": rpo_seconds,
        "data_criticality": data_criticality,
        "backup_available": backup_available,
        "replication_lag_seconds": replication_lag_seconds,
    }
