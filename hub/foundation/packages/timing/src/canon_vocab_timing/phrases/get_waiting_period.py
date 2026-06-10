"""Get waiting period state for a notice.

FCRA requires waiting periods between pre-adverse and adverse action.
This phrase queries the waiting period state from evidence records.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["EVIDENCE_TYPE_WAITING", "GetWaitingPeriodSpecs", "get_waiting_period"]

# Evidence type for waiting period records
EVIDENCE_TYPE_WAITING = "notice.waiting_period"


class WaitingPeriodStateDict(BaseModel):
    """Waiting period state data (for nested output)."""

    notice_id: UUID
    started_at: datetime
    required_days: int
    jurisdiction: str
    ends_at: datetime
    elapsed: bool
    paused_at: datetime | None = None
    paused_reason: str | None = None
    resumed_at: datetime | None = None


class GetWaitingPeriodSpecs(BaseModel):
    """Specs for get waiting period phrase."""

    # inputs
    notice_id: UUID
    # outputs
    found: bool = False
    state: dict[str, Any] | None = None  # WaitingPeriodStateDict as dict
    reason: str | None = None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    # Handle both Z suffix and +00:00 timezone formats
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _row_to_state_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Convert evidence data dict to state dict."""
    return {
        "notice_id": UUID(str(data["notice_id"])),
        "started_at": _parse_datetime(data["started_at"]),
        "required_days": int(data["required_days"]),
        "jurisdiction": str(data["jurisdiction"]),
        "ends_at": _parse_datetime(data["ends_at"]),
        "elapsed": bool(data.get("elapsed", False)),
        "paused_at": _parse_datetime(data.get("paused_at")),
        "paused_reason": data.get("paused_reason"),
        "resumed_at": _parse_datetime(data.get("resumed_at")),
    }


@canon_phrase(
    Operable.from_structure(GetWaitingPeriodSpecs),
    inputs={"notice_id"},
    outputs={"notice_id", "found", "state", "reason"},
)
async def get_waiting_period(
    options,
    ctx: RequestContext,
) -> dict:
    """Get waiting period state for a notice.

    Queries Evidence records with evidence_type="notice.waiting_period"
    and returns the most recent state for the given notice_id.

    Args:
        options: Query options (notice_id) - typed frozen dataclass
        ctx: Request context with tenant_id

    Returns:
        dict with notice_id, found, state, reason
    """
    notice_id: UUID = options.notice_id

    # Query evidence records for waiting periods
    rows = await select(
        "evidences",
        where={
            "tenant_id": ctx.tenant_id,
            "evidence_type": EVIDENCE_TYPE_WAITING,
        },
        order_by="collected_at DESC",
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    # Find records that reference this notice_id
    # The notice_id is stored in the data JSONB field
    for row in rows:
        data = row.get("data")
        if not data:
            continue

        # Match notice_id in data
        if str(data.get("notice_id")) == str(notice_id):
            try:
                state = _row_to_state_dict(data)
                return {
                    "notice_id": notice_id,
                    "found": True,
                    "state": state,
                    "reason": None,
                }
            except (KeyError, ValueError, TypeError) as e:
                return {
                    "notice_id": notice_id,
                    "found": False,
                    "state": None,
                    "reason": f"Invalid waiting period data: {e}",
                }

    return {
        "notice_id": notice_id,
        "found": False,
        "state": None,
        "reason": f"No waiting period found for notice: {notice_id}",
    }
