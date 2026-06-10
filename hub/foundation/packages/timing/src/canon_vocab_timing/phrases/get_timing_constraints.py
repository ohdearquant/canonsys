"""Query applicable timing constraints for a context.

Compliance Context:
    - FCRA Section 1681b(b)(3) (Jurisdiction-specific waiting periods)
    - State law variations (California, NYC, etc.)
    - Employment law notice periods
    - Industry-specific SLAs
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ConstraintType", "GetTimingConstraintsSpecs", "get_timing_constraints"]


class ConstraintType(StrEnum):
    """Types of timing constraints."""

    WAITING_PERIOD = "waiting_period"
    NOTICE_PERIOD = "notice_period"
    RESPONSE_DEADLINE = "response_deadline"
    COOLING_OFF = "cooling_off"
    RETENTION_PERIOD = "retention_period"
    SLA = "sla"


class TimingConstraintDict(BaseModel):
    """Single timing constraint (for nested output)."""

    constraint_id: str
    constraint_type: ConstraintType
    name: str
    required_days: int | None = None
    required_hours: int | None = None
    regulatory_basis: str | None = None
    jurisdiction: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)


class GetTimingConstraintsSpecs(BaseModel):
    """Specs for get timing constraints phrase."""

    # inputs
    context_type: str = Field(
        description="Type of action/context (adverse_action, termination, etc.)"
    )
    jurisdiction: str = Field(default="federal", description="Applicable jurisdiction")
    industry: str | None = Field(default=None, description="Industry for SLA lookup")
    # outputs
    found: bool = False
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    default_waiting_days: int | None = None
    reason: str | None = None


# Default timing constraints by context and jurisdiction
_DEFAULT_CONSTRAINTS: dict[str, dict[str, dict[str, Any]]] = {
    "adverse_action": {
        "federal": {"waiting_days": 5, "basis": "FCRA Section 1681b(b)(3)"},
        "california": {"waiting_days": 7, "basis": "CA Civil Code 1786.40"},
        "nyc": {"waiting_days": 5, "basis": "FCRA (federal)"},
        "new_york_state": {"waiting_days": 5, "basis": "FCRA (federal)"},
    },
    "termination_notice": {
        "federal": {"notice_days": 60, "basis": "WARN Act"},
        "california": {"notice_days": 60, "basis": "California WARN Act"},
        "nyc": {"notice_days": 90, "basis": "NYC WARN"},
    },
    "dispute_response": {
        "federal": {"response_days": 30, "basis": "FCRA Section 1681i"},
        "california": {"response_days": 30, "basis": "FCRA Section 1681i"},
    },
}


@canon_phrase(
    Operable.from_structure(GetTimingConstraintsSpecs),
    inputs={"context_type", "jurisdiction", "industry"},
    outputs={
        "found",
        "context_type",
        "jurisdiction",
        "constraints",
        "default_waiting_days",
        "reason",
    },
)
async def get_timing_constraints(
    options,
    ctx: RequestContext,
) -> dict:
    """Query applicable timing constraints for a context.

    Returns all timing constraints that apply to the given action type
    and jurisdiction combination.

    Args:
        options: Query options (context_type, jurisdiction, industry)
        ctx: Request context (tenant, actor, subject)

    Returns:
        dict with found, context_type, jurisdiction, constraints, default_waiting_days, reason

    Example:
        >>> result = await get_timing_constraints(
        ...     {"context_type": "adverse_action", "jurisdiction": "california"}, ctx
        ... )
        >>> waiting_days = result["default_waiting_days"]  # 7 for California
    """
    context_type: str = options.context_type
    jurisdiction: str = options.jurisdiction.lower()

    # Look up constraints from defaults
    context_constraints = _DEFAULT_CONSTRAINTS.get(context_type, {})
    jurisdiction_data = context_constraints.get(jurisdiction)

    if not jurisdiction_data:
        # Fall back to federal if jurisdiction not found
        jurisdiction_data = context_constraints.get("federal")

    if not jurisdiction_data:
        return {
            "found": False,
            "context_type": context_type,
            "jurisdiction": jurisdiction,
            "constraints": [],
            "default_waiting_days": None,
            "reason": f"No timing constraints found for {context_type} in {jurisdiction}",
        }

    # Build constraint list
    constraints = []

    if "waiting_days" in jurisdiction_data:
        constraints.append(
            {
                "constraint_id": f"{context_type}_{jurisdiction}_waiting",
                "constraint_type": ConstraintType.WAITING_PERIOD,
                "name": f"{context_type.replace('_', ' ').title()} Waiting Period",
                "required_days": jurisdiction_data["waiting_days"],
                "regulatory_basis": jurisdiction_data.get("basis"),
                "jurisdiction": jurisdiction,
            }
        )

    if "notice_days" in jurisdiction_data:
        constraints.append(
            {
                "constraint_id": f"{context_type}_{jurisdiction}_notice",
                "constraint_type": ConstraintType.NOTICE_PERIOD,
                "name": f"{context_type.replace('_', ' ').title()} Notice Period",
                "required_days": jurisdiction_data["notice_days"],
                "regulatory_basis": jurisdiction_data.get("basis"),
                "jurisdiction": jurisdiction,
            }
        )

    if "response_days" in jurisdiction_data:
        constraints.append(
            {
                "constraint_id": f"{context_type}_{jurisdiction}_response",
                "constraint_type": ConstraintType.RESPONSE_DEADLINE,
                "name": f"{context_type.replace('_', ' ').title()} Response Deadline",
                "required_days": jurisdiction_data["response_days"],
                "regulatory_basis": jurisdiction_data.get("basis"),
                "jurisdiction": jurisdiction,
            }
        )

    default_waiting = jurisdiction_data.get("waiting_days")

    return {
        "found": True,
        "context_type": context_type,
        "jurisdiction": jurisdiction,
        "constraints": constraints,
        "default_waiting_days": default_waiting,
        "reason": None,
    }
