"""Require all appeals to be exhausted before final action.

Raises AppealNotExhaustedError if appeals still available.

Regulatory:
    - Administrative Procedure Act (APA)
    - Due process requirements
    - Employment appeal procedures
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import AppealNotExhaustedError
from ..types import AppealStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireAppealExhaustedSpecs", "require_appeal_exhausted"]


class RequireAppealExhaustedSpecs(BaseModel):
    """Specs for require appeal exhausted phrase."""

    # inputs
    decision_id: UUID
    # outputs
    satisfied: bool | None = None
    status: AppealStatus | None = None
    appeal_deadline: datetime | None = None
    final_decision_at: datetime | None = None
    reason: str | None = None


require_appeal_exhausted_operable = Operable.from_structure(RequireAppealExhaustedSpecs)


@canon_phrase(
    require_appeal_exhausted_operable,
    inputs={"decision_id"},
    outputs={
        "satisfied",
        "decision_id",
        "status",
        "appeal_deadline",
        "final_decision_at",
        "reason",
    },
)
async def require_appeal_exhausted(
    options: RequireAppealExhaustedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require all appeals to be exhausted before final action.

    Args:
        options: Options containing decision_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfaction status if appeals exhausted.

    Raises:
        AppealNotExhaustedError: If appeals are still pending or available.
    """
    decision_id: UUID = options.decision_id

    row = await select_one(
        "decision_appeals",
        where={"decision_id": decision_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise AppealNotExhaustedError(
            decision_id=decision_id,
            status=None,
            reason=f"No appeal record found for decision {decision_id}",
        )

    status = AppealStatus(row["appeal_status"])

    if status in (AppealStatus.PENDING, AppealStatus.AVAILABLE):
        raise AppealNotExhaustedError(
            decision_id=decision_id,
            status=status,
            appeal_deadline=row.get("appeal_deadline"),
            reason=f"Appeal status: {status.value}",
        )

    return {
        "satisfied": True,
        "decision_id": decision_id,
        "status": status,
        "appeal_deadline": row.get("appeal_deadline"),
        "final_decision_at": row.get("final_decision_at"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireAppealExhaustedOptions = require_appeal_exhausted.options_type
RequireAppealExhaustedResult = require_appeal_exhausted.result_type
