"""Assess risk level of an access scope.

Complete vertical slice:
- Queries scope definition and data classification
- Calculates risk based on sensitivity and breadth
- Returns risk assessment with factors

Regulatory context:
    - NIST SP 800-53 RA-3 (Risk Assessment)
    - SOC 2 CC3.2 (Risk identification)
    - GDPR Art. 35 (Data protection impact assessment)
    - ISO 27001 (Information security risk assessment)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import RiskLevel

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["AssessScopeRiskLevelSpecs", "assess_scope_risk_level"]


# Data sensitivity to base risk mapping
_SENSITIVITY_RISK: dict[str, int] = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "pii": 3,
    "phi": 4,
    "pci": 4,
}

# Scope type to risk modifier
_SCOPE_TYPE_MODIFIER: dict[str, int] = {
    "read": 0,
    "write": 1,
    "delete": 2,
    "admin": 3,
    "bulk_export": 3,
}


class AssessScopeRiskLevelSpecs(BaseModel):
    """Specs for assess scope risk level phrase."""

    # inputs
    scope_id: UUID
    scope_type: str
    # outputs
    risk_level: RiskLevel | None = None
    data_sensitivity: str | None = None
    access_breadth: int | None = None
    risk_factors: tuple[str, ...] | None = None


@canon_phrase(
    Operable.from_structure(AssessScopeRiskLevelSpecs),
    inputs={"scope_id", "scope_type"},
    outputs={
        "scope_id",
        "scope_type",
        "risk_level",
        "data_sensitivity",
        "access_breadth",
        "risk_factors",
    },
)
async def assess_scope_risk_level(
    options,
    ctx: RequestContext,
) -> dict:
    """Assess risk level of an access scope.

    Calculates risk based on:
    - Data sensitivity (classification level)
    - Scope type (read vs write vs admin)
    - Access breadth (number of records accessible)

    Regulatory citations:
    - NIST SP 800-53 RA-3: Organizations must assess risk
    - SOC 2 CC3.2: Entity identifies and assesses risks
    - GDPR Art. 35: DPIA required for high-risk processing
    - ISO 27001 6.1.2: Information security risk assessment

    Args:
        options: Assessment options (scope_id, scope_type) - typed frozen dataclass
        ctx: Request context (tenant, actor)

    Returns:
        dict with scope_id, scope_type, risk_level, data_sensitivity, access_breadth, risk_factors
    """
    scope_id: UUID = options.scope_id
    scope_type: str = options.scope_type
    risk_factors: list[str] = []

    # Query scope definition
    row = await select_one(
        "scope_definitions",
        where={
            "tenant_id": ctx.tenant_id,
            "id": scope_id,
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # Unknown scope - treat as high risk (fail-closed)
        return {
            "scope_id": scope_id,
            "scope_type": scope_type,
            "risk_level": "high",
            "data_sensitivity": "unknown",
            "access_breadth": 0,
            "risk_factors": ("unknown_scope", "fail_closed"),
        }

    # Extract scope attributes
    data_sensitivity = row.get("data_classification", "internal")
    access_breadth = row.get("record_count", 1)

    # Calculate base risk from sensitivity
    base_risk = _SENSITIVITY_RISK.get(data_sensitivity.lower(), 2)
    risk_factors.append(f"data_sensitivity:{data_sensitivity}")

    # Apply scope type modifier
    type_modifier = _SCOPE_TYPE_MODIFIER.get(scope_type.lower(), 1)
    if type_modifier > 0:
        risk_factors.append(f"scope_type:{scope_type}")

    # Apply breadth modifier
    breadth_modifier = 0
    if access_breadth > 1000:
        breadth_modifier = 2
        risk_factors.append("bulk_access:>1000")
    elif access_breadth > 100:
        breadth_modifier = 1
        risk_factors.append("moderate_breadth:>100")

    # Calculate total risk score
    total_risk = base_risk + type_modifier + breadth_modifier

    # Map score to risk level
    risk_level = _calculate_risk_level(total_risk)

    return {
        "scope_id": scope_id,
        "scope_type": scope_type,
        "risk_level": risk_level,
        "data_sensitivity": data_sensitivity,
        "access_breadth": access_breadth,
        "risk_factors": tuple(risk_factors),
    }


def _calculate_risk_level(total_risk: int) -> RiskLevel:
    """Map total risk score to risk level."""
    if total_risk >= 6:
        return "critical"
    elif total_risk >= 4:
        return "high"
    elif total_risk >= 2:
        return "medium"
    else:
        return "low"
