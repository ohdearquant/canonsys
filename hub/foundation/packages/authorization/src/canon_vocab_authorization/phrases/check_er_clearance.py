"""Check ER (Employee Relations) clearance for a subject.

Complete vertical slice:
- Queries for active ER cases
- Returns clearance status (cleared/not cleared)
- Fail-closed: unknown = not cleared

Regulatory:
    - Employment law compliance
    - Wrongful termination prevention
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

from ..types import ERClearanceStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckERClearanceSpecs", "check_er_clearance"]


class CheckERClearanceSpecs(BaseModel):
    """Specs for check ER clearance phrase."""

    # inputs
    subject_id: UUID
    # outputs (defaults required for instantiation with inputs only)
    cleared: bool = False
    status: ERClearanceStatus | None = None
    checked_at: datetime | None = None
    er_case_id: UUID | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(CheckERClearanceSpecs),
    inputs={"subject_id"},
    outputs={"cleared", "status", "subject_id", "checked_at", "er_case_id", "reason"},
)
async def check_er_clearance(
    options: CheckERClearanceSpecs,
    ctx: RequestContext,
) -> dict:
    """Check ER clearance for a subject.

    Queries for active Employee Relations cases that would prevent
    termination or other HR actions. Fail-closed: if status cannot
    be determined, treat as not cleared.

    Args:
        options: Options containing subject_id
        ctx: Request context (tenant, actor)

    Returns:
        Dict with cleared, status, subject_id, checked_at, er_case_id, reason
    """
    now = now_utc()
    subject_id: UUID = options.subject_id

    # Check for active ER cases
    row = await select_one(
        "er_cases",
        where={
            "tenant_id": ctx.tenant_id,
            "subject_id": subject_id,
            "status": "open",
        },
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if row:
        # Active ER context exists - not cleared
        return {
            "cleared": False,
            "status": ERClearanceStatus.ACTIVE_CONTEXT,
            "subject_id": subject_id,
            "checked_at": now,
            "er_case_id": row["id"],
            "reason": "Active ER case exists - escalation required",
        }

    # No active ER context - cleared
    return {
        "cleared": True,
        "status": ERClearanceStatus.CLEARED,
        "subject_id": subject_id,
        "checked_at": now,
        "er_case_id": None,
        "reason": None,
    }
