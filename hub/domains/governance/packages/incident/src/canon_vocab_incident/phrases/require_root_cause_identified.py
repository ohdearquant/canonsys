"""Require root cause identification before incident closure.

Enforces incident response requirements by ensuring that root cause
has been identified before allowing closure or reporting operations.

Regulatory: SOC 2 CC7.4, ISO 27001 A.16.1.6, GDPR Art. 33(3)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from .verify_root_cause_identified import verify_root_cause_identified

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireRootCauseIdentifiedSpecs", "require_root_cause_identified"]


class RequireRootCauseIdentifiedSpecs(BaseModel):
    """Specs for require root cause identified phrase."""

    # inputs
    incident_id: UUID
    # outputs
    satisfied: bool = False
    root_cause_id: UUID | None = None
    identified_at: datetime | None = None
    reason: str | None = None


require_root_cause_identified_operable = Operable.from_structure(RequireRootCauseIdentifiedSpecs)


@canon_phrase(
    require_root_cause_identified_operable,
    inputs={"incident_id"},
    outputs={"satisfied", "incident_id", "root_cause_id", "identified_at", "reason"},
)
async def require_root_cause_identified(
    options: RequireRootCauseIdentifiedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require root cause identification before incident closure.

    Raises RequirementNotMetError if root cause not identified.

    Regulatory:
        - SOC 2 CC7.4 (Incident response)
        - ISO 27001 A.16.1.6 (Learning from incidents)
        - GDPR Art. 33(3) (Notification details)

    Args:
        options: Options containing incident_id to check.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with identification status.

    Raises:
        RequirementNotMetError: If root cause is not identified.
    """
    incident_id = options.incident_id

    # Create options for verify phrase
    from .verify_root_cause_identified import VerifyRootCauseIdentifiedSpecs

    verify_options = VerifyRootCauseIdentifiedSpecs(incident_id=incident_id)
    verify_result = await verify_root_cause_identified(verify_options, ctx)

    if not verify_result.get("verified", False):
        raise RequirementNotMetError(
            requirement="root_cause_identified",
            reason=f"Root cause must be identified for incident {incident_id}",
            evidence_id=verify_result.get("root_cause_id"),
        )

    return {
        "satisfied": True,
        "incident_id": incident_id,
        "root_cause_id": verify_result.get("root_cause_id"),
        "identified_at": verify_result.get("identified_at"),
        "reason": "Root cause identified",
    }


# Export auto-generated types from the Phrase object
RequireRootCauseIdentifiedOptions = require_root_cause_identified.options_type
RequireRootCauseIdentifiedResult = require_root_cause_identified.result_type
