"""Derive risk tier from evidence and context.

Complete vertical slice:
- Analyzes evidence references and configuration
- Computes risk tier based on evidence composition
- Returns risk tier (LOW/MEDIUM/HIGH) for policy routing

Regulatory: PRD-017 Section 5 - Risk tier determines enforcement
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveRiskTierSpecs", "RiskTier", "derive_risk_tier"]


class RiskTier(str, Enum):
    """Risk classification tiers."""

    LOW = "low"  # Routine decisions, minimal scrutiny
    MEDIUM = "medium"  # Standard decisions, normal controls
    HIGH = "high"  # High-impact decisions, enhanced controls


class DeriveRiskTierSpecs(BaseModel):
    """Specs for derive risk tier phrase."""

    # inputs
    evidence_refs: list[UUID] | None = None
    decision_type: str | None = None
    config: dict[str, Any] | None = None
    # outputs
    risk_tier: RiskTier | None = None
    evidence_count: int = 0
    high_risk_indicators: list[str] | None = None
    rationale: str | None = None


# Default risk escalation rules
DEFAULT_HIGH_RISK_TYPES = frozenset(
    {
        "termination",
        "involuntary_termination",
        "rif",
        "adverse_action",
        "executive_override",
    }
)

DEFAULT_MEDIUM_RISK_TYPES = frozenset(
    {
        "pip",
        "performance_improvement",
        "final_warning",
        "demotion",
        "suspension",
    }
)


@canon_phrase(
    Operable.from_structure(DeriveRiskTierSpecs),
    inputs={"evidence_refs", "decision_type", "config"},
    outputs={"risk_tier", "evidence_count", "high_risk_indicators", "rationale"},
)
async def derive_risk_tier(
    options: DeriveRiskTierSpecs,
    ctx: RequestContext,
) -> dict:
    """Derive risk tier from evidence and context.

    Analyzes the decision type and evidence composition to determine
    the appropriate risk tier. Used to route decisions through
    appropriate control levels.

    Args:
        options: Options containing evidence_refs, decision_type, config.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with risk_tier, evidence_count, high_risk_indicators, rationale.
    """
    evidence_refs = options.evidence_refs or []
    decision_type = (options.decision_type or "").lower()
    config = options.config or {}

    # Get configurable rules
    high_risk_types = config.get("high_risk_types", DEFAULT_HIGH_RISK_TYPES)
    medium_risk_types = config.get("medium_risk_types", DEFAULT_MEDIUM_RISK_TYPES)
    min_evidence_for_high = config.get("min_evidence_for_high", 3)

    high_risk_indicators: list[str] = []
    evidence_count = len(evidence_refs)

    # Check decision type
    if decision_type in high_risk_types:
        high_risk_indicators.append(f"decision_type:{decision_type}")

    # Check evidence quantity (more evidence often means higher stakes)
    if evidence_count >= min_evidence_for_high:
        high_risk_indicators.append(f"evidence_count:{evidence_count}")

    # Analyze evidence types if we have CEP references
    for cep_id in evidence_refs:
        row = await select_one(
            "certified_evidence_packets",
            where={"id": cep_id},
            conn=ctx.conn,
            tenant_scope=TenantScope.REQUIRED,
        )
        if row:
            cep_type = row.get("cep_type", "")
            # Investigation rulings and conduct records elevate risk
            if cep_type in ("investigation_ruling", "conduct_record", "pip_fail"):
                high_risk_indicators.append(f"cep_type:{cep_type}")
                break  # One is enough to escalate

    # Determine tier
    if high_risk_indicators:
        risk_tier = RiskTier.HIGH
        rationale = f"High risk due to: {', '.join(high_risk_indicators)}"
    elif decision_type in medium_risk_types:
        risk_tier = RiskTier.MEDIUM
        rationale = f"Medium risk due to decision type: {decision_type}"
    else:
        risk_tier = RiskTier.LOW
        rationale = "Standard risk profile"

    return {
        "risk_tier": risk_tier,
        "evidence_count": evidence_count,
        "high_risk_indicators": high_risk_indicators or None,
        "rationale": rationale,
    }
