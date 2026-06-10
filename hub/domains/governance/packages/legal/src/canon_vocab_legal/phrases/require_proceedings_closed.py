"""Require legal proceedings to be closed before certain actions.

Raises ProceedingsNotClosedError if proceedings still open.

Regulatory:
    - FRCP (Federal Rules of Civil Procedure)
    - Court record sealing requirements
    - Litigation hold release requirements
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import ProceedingsNotClosedError
from ..types import ProceedingsStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["RequireProceedingsClosedSpecs", "require_proceedings_closed"]


class RequireProceedingsClosedSpecs(BaseModel):
    """Specs for require proceedings closed phrase."""

    # inputs
    matter_id: UUID
    # outputs
    satisfied: bool | None = None
    status: ProceedingsStatus | None = None
    closed_at: datetime | None = None
    disposition: str | None = None
    reason: str | None = None


require_proceedings_closed_operable = Operable.from_structure(RequireProceedingsClosedSpecs)


@canon_phrase(
    require_proceedings_closed_operable,
    inputs={"matter_id"},
    outputs={
        "satisfied",
        "matter_id",
        "status",
        "closed_at",
        "disposition",
        "reason",
    },
)
async def require_proceedings_closed(
    options: RequireProceedingsClosedSpecs,
    ctx: RequestContext,
) -> dict:
    """Require legal proceedings to be closed before certain actions.

    Args:
        options: Options containing matter_id
        ctx: Request context (tenant, actor)

    Returns:
        dict with satisfaction status if proceedings are closed.

    Raises:
        ProceedingsNotClosedError: If proceedings are still open or stayed.
    """
    matter_id: UUID = options.matter_id

    row = await select_one(
        "legal_proceedings",
        where={"matter_id": matter_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        raise ProceedingsNotClosedError(
            matter_id=matter_id,
            status=None,
            reason=f"No proceedings found for matter {matter_id}",
        )

    status = ProceedingsStatus(row["status"])

    if status in (ProceedingsStatus.OPEN, ProceedingsStatus.STAYED):
        raise ProceedingsNotClosedError(
            matter_id=matter_id,
            status=status,
            reason=f"Proceedings still {status.value}",
        )

    return {
        "satisfied": True,
        "matter_id": matter_id,
        "status": status,
        "closed_at": row.get("closed_at"),
        "disposition": row.get("disposition"),
        "reason": None,
    }


# Export auto-generated types from the Phrase object
RequireProceedingsClosedOptions = require_proceedings_closed.options_type
RequireProceedingsClosedResult = require_proceedings_closed.result_type
