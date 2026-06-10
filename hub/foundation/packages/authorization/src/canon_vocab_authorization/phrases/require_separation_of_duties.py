"""Require separation of duties for workflow steps.

Complete vertical slice:
- Verifies that different actors performed different workflow steps
- Ensures no single actor performed conflicting steps
- Raises RequirementNotMetError if SoD violated

Regulatory:
    - SOX Section 404 (Segregation of duties in financial controls)
    - SOC 2 CC5.1 (Control activities - segregation of duties)
    - COSO Framework (Control environment and control activities)
    - PCI DSS 6.4.2 (Separation of duties between dev and prod)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireSeparationOfDutiesSpecs", "require_separation_of_duties"]


class RequireSeparationOfDutiesSpecs(BaseModel):
    """Specs for require separation of duties phrase."""

    # inputs
    workflow_id: UUID
    conflicting_steps: tuple[str, ...] | list[str]  # Steps that must be done by different actors
    # outputs (defaults required for instantiation with inputs only)
    satisfied: bool = False
    step_actors: dict[str, UUID] | None = None
    conflicts_found: tuple[tuple[str, str, UUID], ...] | None = None
    checked_at: datetime | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(RequireSeparationOfDutiesSpecs),
    inputs={"workflow_id", "conflicting_steps"},
    outputs={
        "satisfied",
        "workflow_id",
        "step_actors",
        "conflicts_found",
        "checked_at",
        "reason",
    },
)
async def require_separation_of_duties(
    options: RequireSeparationOfDutiesSpecs,
    ctx: RequestContext,
) -> dict:
    """Require separation of duties for workflow steps.

    Verifies that the specified workflow steps were performed by different
    actors. This is essential for compliance with segregation of duties
    requirements.

    Common use cases:
        - Preparer != Approver (financial transactions)
        - Requester != Authorizer (access grants)
        - Developer != Deployer (change management)
        - Maker != Checker (dual control)

    Args:
        options: Options containing workflow_id and conflicting_steps
        ctx: Request context with connection

    Returns:
        Dict with satisfied=True if all conflicting steps have different actors.

    Raises:
        RequirementNotMetError: If same actor performed conflicting steps
    """
    now = now_utc()
    workflow_id: UUID = options.workflow_id
    conflicting_steps = tuple(options.conflicting_steps)

    # Query workflow steps with their actors
    query = """
        SELECT step_name, actor_id
        FROM workflow_steps
        WHERE workflow_id = $1
          AND step_name = ANY($2)
          AND status = 'completed'
    """
    rows = await ctx.conn.fetch(query, workflow_id, list(conflicting_steps))

    # Build step -> actor mapping
    step_actors: dict[str, UUID] = {}
    for row in rows:
        step_actors[row["step_name"]] = row["actor_id"]

    # Check for conflicts (same actor doing multiple conflicting steps)
    conflicts: list[tuple[str, str, UUID]] = []
    steps_list = list(step_actors.keys())
    for i, step_a in enumerate(steps_list):
        for step_b in steps_list[i + 1 :]:
            if step_actors[step_a] == step_actors[step_b]:
                conflicts.append((step_a, step_b, step_actors[step_a]))

    if conflicts:
        conflict_desc = "; ".join(
            f"'{s1}' and '{s2}' both by actor {aid}" for s1, s2, aid in conflicts
        )
        raise RequirementNotMetError(
            requirement="separation_of_duties",
            reason=f"Segregation of Duties violation: {conflict_desc}",
        )

    return {
        "satisfied": True,
        "workflow_id": workflow_id,
        "step_actors": step_actors,
        "conflicts_found": (),
        "checked_at": now,
        "reason": "Segregation of Duties verified: all conflicting steps performed by different actors",
    }
