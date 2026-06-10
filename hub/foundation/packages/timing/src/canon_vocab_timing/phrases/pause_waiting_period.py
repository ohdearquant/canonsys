"""Pause waiting period clock.

When a dispute is filed, the waiting period clock must pause.
This phrase records the pause in the evidence chain.
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

__all__ = ["PauseWaitingPeriodSpecs", "pause_waiting_period"]


class PauseWaitingPeriodSpecs(BaseModel):
    """Specs for pause waiting period phrase."""

    # inputs
    notice_id: UUID
    reason: str
    # outputs
    success: bool = False
    paused_at: datetime | None = None
    error: str | None = None


@canon_phrase(
    Operable.from_structure(PauseWaitingPeriodSpecs),
    inputs={"notice_id", "reason"},
    outputs={"notice_id", "success", "paused_at", "reason", "error"},
)
async def pause_waiting_period(
    options,
    ctx: RequestContext,
) -> dict:
    """Pause waiting period clock.

    When a dispute is filed during the FCRA waiting period, the clock
    must pause until the dispute is resolved. This creates a new Evidence
    record capturing the pause state.

    Args:
        options: Pause options (notice_id, reason) - typed frozen dataclass
        ctx: Request context

    Returns:
        dict with notice_id, success, paused_at, reason, error
    """
    notice_id: UUID = options.notice_id
    reason: str = options.reason

    # 1. Get current waiting period
    wp_result = await get_waiting_period({"notice_id": notice_id}, ctx)

    if not wp_result["found"] or wp_result.get("state") is None:
        return {
            "notice_id": notice_id,
            "success": False,
            "paused_at": None,
            "reason": reason,
            "error": wp_result.get("reason") or f"No waiting period found for notice: {notice_id}",
        }

    state = wp_result["state"]

    # 2. Validate not already paused (paused_at set but not resumed)
    if state.get("paused_at") is not None and state.get("resumed_at") is None:
        paused_at = state["paused_at"]
        paused_at_str = paused_at.isoformat() if hasattr(paused_at, "isoformat") else str(paused_at)
        return {
            "notice_id": notice_id,
            "success": False,
            "paused_at": None,
            "reason": reason,
            "error": f"Waiting period already paused at {paused_at_str}",
        }

    # 3. Validate not already elapsed
    if state.get("elapsed"):
        return {
            "notice_id": notice_id,
            "success": False,
            "paused_at": None,
            "reason": reason,
            "error": "Cannot pause: waiting period has already elapsed",
        }

    # 4. Create new evidence with paused state
    paused_at = now_utc()

    evidence_data = {
        "notice_id": str(notice_id),
        "started_at": (
            state["started_at"].isoformat()
            if hasattr(state["started_at"], "isoformat")
            else state["started_at"]
        ),
        "required_days": state["required_days"],
        "jurisdiction": state["jurisdiction"],
        "ends_at": (
            state["ends_at"].isoformat()
            if hasattr(state["ends_at"], "isoformat")
            else state["ends_at"]
        ),
        "elapsed": False,
        "paused_at": paused_at.isoformat(),
        "paused_reason": reason,
        "resumed_at": None,
    }

    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=ctx.subject_id,
        evidence_type=EVIDENCE_TYPE_WAITING,
        title=f"Waiting period paused: {reason}",
        data=evidence_data,
        source="enforcement.pause_waiting_period",
        collected_at=paused_at,
        collected_by_id=ctx.actor_id,
    )

    evidence = Evidence(content=evidence_content)

    # 5. Save evidence
    await save_evidence({"evidence": evidence}, ctx)

    return {
        "notice_id": notice_id,
        "success": True,
        "paused_at": paused_at,
        "reason": reason,
        "error": None,
    }
