"""Derive overall satisfaction status of closing conditions.

ANTI-GAMING: This derivation examines the actual status of ALL closing
conditions. Users cannot assert "conditions satisfied" - the system
derives this from evidence.

Regulatory Context:
    - M&A contract law: Conditions precedent must be satisfied
    - Shareholder protection: Material conditions for deal approval
    - Regulatory requirements: Approval conditions

Complete vertical slice:
- Queries all closing conditions for deal
- Counts by status and type
- Identifies blocking conditions
- Estimates completion date
- Computes evidence hash for audit trail
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ConditionSatisfactionStatus, ConditionType

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveConditionSatisfactionSpecs", "derive_condition_satisfaction_status"]


class DeriveConditionSatisfactionSpecs(BaseModel):
    """Specs for condition satisfaction derivation phrase."""

    # inputs
    deal_id: UUID

    # outputs
    all_satisfied: bool | None = None
    total_conditions: int | None = None
    satisfied_count: int | None = None
    waived_count: int | None = None
    pending_count: int | None = None
    failed_count: int | None = None
    conditions_by_type: dict[ConditionType, ConditionSatisfactionStatus] | None = None
    blocking_conditions: tuple[UUID, ...] | None = None
    estimated_completion: datetime | None = None
    evidence_hash: str | None = None
    derived_at: datetime | None = None


def _compute_evidence_hash(data: list[dict[str, Any]]) -> str:
    """Compute SHA-256 hash of evidence data for audit trail."""
    content = str(sorted([str(sorted(d.items())) for d in data]))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _status_priority(status: ConditionSatisfactionStatus) -> int:
    """Return priority value for status (higher = worse)."""
    priority_map = {
        ConditionSatisfactionStatus.SATISFIED: 0,
        ConditionSatisfactionStatus.WAIVED: 1,
        ConditionSatisfactionStatus.IN_PROGRESS: 2,
        ConditionSatisfactionStatus.PENDING: 3,
        ConditionSatisfactionStatus.EXPIRED: 4,
        ConditionSatisfactionStatus.FAILED: 5,
    }
    return priority_map.get(status, 3)


@canon_phrase(
    Operable.from_structure(DeriveConditionSatisfactionSpecs),
    inputs={"deal_id"},
    outputs={
        "deal_id",
        "all_satisfied",
        "total_conditions",
        "satisfied_count",
        "waived_count",
        "pending_count",
        "failed_count",
        "conditions_by_type",
        "blocking_conditions",
        "estimated_completion",
        "evidence_hash",
        "derived_at",
    },
)
async def derive_condition_satisfaction_status(
    options: DeriveConditionSatisfactionSpecs,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> dict:
    """Derive overall satisfaction status of closing conditions.

    Anti-gaming: This derivation examines the actual status of ALL
    closing conditions. Users cannot assert "conditions satisfied" -
    the system derives this from evidence.

    Conditions are satisfied when:
    - Satisfied: Condition has been met with evidence
    - Waived: Condition has been formally waived

    Conditions that BLOCK closing:
    - Pending: Not yet addressed
    - In progress: Being worked but not complete
    - Failed: Condition cannot be satisfied
    - Expired: Condition deadline has passed

    Regulatory:
        - M&A contract law: Conditions precedent must be satisfied
        - Shareholder protection: Material conditions for deal approval
        - Regulatory requirements: Approval conditions

    Args:
        options: Options containing deal_id
        ctx: Request context (tenant, actor)
        conn: Optional existing database connection

    Returns:
        Dict with derivation outcome
    """
    now = now_utc()
    deal_id = options.deal_id

    # Query all closing conditions
    rows = await fetch(
        """
        SELECT
            cc.condition_id,
            cc.condition_type,
            cc.status,
            cc.deadline,
            cc.satisfied_at,
            cc.waived_at,
            cc.is_material
        FROM closing_conditions cc
        WHERE cc.deal_id = $1
        ORDER BY cc.is_material DESC, cc.condition_type, cc.created_at
        """,
        deal_id,
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not rows:
        # No conditions defined - all satisfied (vacuously true)
        return {
            "deal_id": deal_id,
            "all_satisfied": True,
            "total_conditions": 0,
            "satisfied_count": 0,
            "waived_count": 0,
            "pending_count": 0,
            "failed_count": 0,
            "conditions_by_type": {},
            "blocking_conditions": (),
            "estimated_completion": None,
            "evidence_hash": None,
            "derived_at": now,
        }

    # Count by status
    satisfied_count = 0
    waived_count = 0
    pending_count = 0
    failed_count = 0
    blocking_conditions: list[UUID] = []
    conditions_by_type: dict[ConditionType, ConditionSatisfactionStatus] = {}

    for row in rows:
        status = ConditionSatisfactionStatus(row["status"])
        condition_type = ConditionType(row["condition_type"])

        # Track overall status per type (worst status wins)
        if condition_type not in conditions_by_type:
            conditions_by_type[condition_type] = status
        else:
            # Update if new status is worse
            current = conditions_by_type[condition_type]
            if _status_priority(status) > _status_priority(current):
                conditions_by_type[condition_type] = status

        # Count by status
        if status == ConditionSatisfactionStatus.SATISFIED:
            satisfied_count += 1
        elif status == ConditionSatisfactionStatus.WAIVED:
            waived_count += 1
        elif (
            status == ConditionSatisfactionStatus.FAILED
            or status == ConditionSatisfactionStatus.EXPIRED
        ):
            failed_count += 1
            blocking_conditions.append(row["condition_id"])
        else:  # PENDING or IN_PROGRESS
            pending_count += 1
            # Only material pending conditions block
            if row.get("is_material", True):
                blocking_conditions.append(row["condition_id"])

    # Evidence hash
    evidence_hash = _compute_evidence_hash(list(rows))

    # All satisfied if no blocking conditions
    all_satisfied = len(blocking_conditions) == 0

    # Estimate completion - find latest deadline among pending conditions
    pending_deadlines = [
        row["deadline"]
        for row in rows
        if row["status"] in ("pending", "in_progress") and row.get("deadline")
    ]
    estimated_completion = max(pending_deadlines) if pending_deadlines else None

    return {
        "deal_id": deal_id,
        "all_satisfied": all_satisfied,
        "total_conditions": len(rows),
        "satisfied_count": satisfied_count,
        "waived_count": waived_count,
        "pending_count": pending_count,
        "failed_count": failed_count,
        "conditions_by_type": conditions_by_type,
        "blocking_conditions": tuple(blocking_conditions),
        "estimated_completion": estimated_completion,
        "evidence_hash": evidence_hash,
        "derived_at": now,
    }
