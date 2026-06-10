"""Resume paused waiting period.

When resuming, the ends_at is extended by the pause duration.
This ensures the full waiting period is observed.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from canon_vocab_evidence import save_evidence
from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable
from kron.utils import now_utc

from .get_waiting_period import EVIDENCE_TYPE_WAITING, get_waiting_period

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["ResumeWaitingPeriodSpecs", "resume_waiting_period"]


class ResumeWaitingPeriodSpecs(BaseModel):
    """Specs for resume waiting period phrase."""

    # inputs
    notice_id: UUID
    # outputs
    success: bool = False
    resumed_at: datetime | None = None
    new_ends_at: datetime | None = None
    pause_duration_seconds: float | None = None
    error: str | None = None


@canon_phrase(
    Operable.from_structure(ResumeWaitingPeriodSpecs),
    inputs={"notice_id"},
    outputs={
        "notice_id",
        "success",
        "resumed_at",
        "new_ends_at",
        "pause_duration_seconds",
        "error",
    },
)
async def resume_waiting_period(
    options,
    ctx: RequestContext,
) -> dict:
    """Resume paused waiting period.

    The ends_at is extended by the pause duration to ensure the full
    waiting period is observed.

    Args:
        options: Resume options (notice_id) - typed frozen dataclass
        ctx: Request context

    Returns:
        dict with notice_id, success, resumed_at, new_ends_at, pause_duration_seconds, error
    """
    notice_id: UUID = options.notice_id

    # 1. Get current waiting period
    result = await get_waiting_period({"notice_id": notice_id}, ctx)

    if not result["found"] or result.get("state") is None:
        return {
            "notice_id": notice_id,
            "success": False,
            "resumed_at": None,
            "new_ends_at": None,
            "pause_duration_seconds": None,
            "error": result.get("reason") or f"No waiting period found for notice: {notice_id}",
        }

    state = result["state"]

    # 2. Validate it is paused
    if state.get("paused_at") is None:
        return {
            "notice_id": notice_id,
            "success": False,
            "resumed_at": None,
            "new_ends_at": None,
            "pause_duration_seconds": None,
            "error": "Waiting period is not paused",
        }

    if state.get("elapsed"):
        return {
            "notice_id": notice_id,
            "success": False,
            "resumed_at": None,
            "new_ends_at": None,
            "pause_duration_seconds": None,
            "error": "Cannot resume an elapsed waiting period",
        }

    # 3. Calculate pause duration
    now = now_utc()
    paused_at = state["paused_at"]
    pause_duration = now - paused_at
    pause_duration_seconds = pause_duration.total_seconds()

    # 4. Calculate new ends_at (extend by pause duration)
    ends_at = state["ends_at"]
    new_ends_at = ends_at + pause_duration

    # 5. Build updated waiting period data
    started_at = state["started_at"]
    updated_data = {
        "notice_id": str(notice_id),
        "started_at": (started_at.isoformat() if hasattr(started_at, "isoformat") else started_at),
        "required_days": state["required_days"],
        "jurisdiction": state["jurisdiction"],
        "ends_at": new_ends_at.isoformat(),
        "elapsed": False,
        "paused_at": None,  # Clear pause state
        "paused_reason": None,  # Clear pause reason
        "resumed_at": now.isoformat(),
        # Include pause info for audit trail
        "pause_duration_seconds": pause_duration_seconds,
        "previous_paused_at": (
            paused_at.isoformat() if hasattr(paused_at, "isoformat") else paused_at
        ),
        "previous_paused_reason": state.get("paused_reason"),
    }

    # 6. Emit evidence with updated state
    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=ctx.subject_id,
        evidence_type=EVIDENCE_TYPE_WAITING,
        title=f"Waiting Period Resumed - extended to {new_ends_at.isoformat()}",
        data=updated_data,
        source="enforcement.resume_waiting_period",
        collected_at=now,
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)
    await save_evidence({"evidence": evidence}, ctx)

    return {
        "notice_id": notice_id,
        "success": True,
        "resumed_at": now,
        "new_ends_at": new_ends_at,
        "pause_duration_seconds": pause_duration_seconds,
        "error": None,
    }
