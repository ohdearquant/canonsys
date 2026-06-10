"""Check if waiting period has elapsed.

FCRA requires waiting period between pre-adverse and adverse action.
This phrase checks if the waiting period has elapsed, optionally
marking it as elapsed if time has passed.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from canon_vocab_evidence import supersede_evidence
from pydantic import BaseModel

from canon.db import TenantScope, select
from canon.enforcement.executor import canon_phrase
from canon.entities import EvidenceContent
from kron.specs import Operable
from kron.utils import now_utc

from .get_waiting_period import EVIDENCE_TYPE_WAITING, get_waiting_period

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckWaitingPeriodElapsedSpecs", "check_waiting_period_elapsed"]


class CheckWaitingPeriodElapsedSpecs(BaseModel):
    """Specs for check waiting period elapsed phrase."""

    # inputs
    notice_id: UUID
    auto_mark_elapsed: bool = True
    # outputs
    elapsed: bool = False
    ends_at: datetime | None = None
    paused: bool = False
    remaining_seconds: float | None = None
    just_marked_elapsed: bool = False
    reason: str | None = None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO format datetime string to datetime object."""
    if value is None:
        return None
    # Handle both Z suffix and +00:00 timezone formats
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


async def _find_waiting_period_evidence(
    notice_id: UUID,
    ctx: RequestContext,
    *,
    conn: Any | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find the evidence row for a waiting period.

    Returns:
        Tuple of (evidence_row, data_dict) or (None, None) if not found.
    """
    rows = await select(
        "evidences",
        where={
            "tenant_id": ctx.tenant_id,
            "evidence_type": EVIDENCE_TYPE_WAITING,
        },
        order_by="collected_at DESC",
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    for row in rows:
        data = row.get("data")
        if not data:
            continue
        if str(data.get("notice_id")) == str(notice_id):
            return row, data

    return None, None


@canon_phrase(
    Operable.from_structure(CheckWaitingPeriodElapsedSpecs),
    inputs={"notice_id", "auto_mark_elapsed"},
    outputs={
        "notice_id",
        "elapsed",
        "ends_at",
        "paused",
        "remaining_seconds",
        "just_marked_elapsed",
        "reason",
    },
)
async def check_waiting_period_elapsed(
    options,
    ctx: RequestContext,
) -> dict:
    """Check if waiting period has elapsed.

    Args:
        options: Check options (notice_id, auto_mark_elapsed) - typed frozen dataclass
        ctx: Request context

    Returns:
        dict with notice_id, elapsed, ends_at, paused, remaining_seconds,
        just_marked_elapsed, reason
    """
    notice_id: UUID = options.notice_id
    auto_mark_elapsed: bool = options.auto_mark_elapsed

    # 1. Get current waiting period state
    result = await get_waiting_period({"notice_id": notice_id}, ctx)

    if not result["found"] or result.get("state") is None:
        # No waiting period found - cannot check elapsed
        return {
            "notice_id": notice_id,
            "elapsed": False,
            "ends_at": datetime.min,
            "paused": False,
            "remaining_seconds": None,
            "just_marked_elapsed": False,
            "reason": result.get("reason") or f"No waiting period found for notice: {notice_id}",
        }

    state = result["state"]
    current_time = now_utc()

    # 2. Check if elapsed (time passed AND not paused)
    is_paused = state["paused_at"] is not None and state.get("resumed_at") is None
    time_has_passed = current_time >= state["ends_at"]
    is_elapsed = time_has_passed and not is_paused

    # Already marked as elapsed in evidence - return current state
    if state.get("elapsed"):
        return {
            "notice_id": notice_id,
            "elapsed": True,
            "ends_at": state["ends_at"],
            "paused": is_paused,
            "remaining_seconds": None,
            "just_marked_elapsed": False,
            "reason": None,
        }

    # Period is paused - cannot be elapsed yet
    if is_paused:
        return {
            "notice_id": notice_id,
            "elapsed": False,
            "ends_at": state["ends_at"],
            "paused": True,
            "remaining_seconds": None,  # Cannot calculate while paused
            "just_marked_elapsed": False,
            "reason": f"Waiting period paused: {state.get('paused_reason') or 'no reason'}",
        }

    # 4. Calculate remaining_seconds if not elapsed
    if not is_elapsed:
        remaining = (state["ends_at"] - current_time).total_seconds()
        return {
            "notice_id": notice_id,
            "elapsed": False,
            "ends_at": state["ends_at"],
            "paused": False,
            "remaining_seconds": max(0.0, remaining),
            "just_marked_elapsed": False,
            "reason": None,
        }

    # Period has elapsed - optionally mark it
    just_marked = False

    # 3. If auto_mark_elapsed and newly elapsed, emit evidence
    if auto_mark_elapsed:
        # Find the original evidence to supersede
        evidence_row, data = await _find_waiting_period_evidence(notice_id, ctx, conn=ctx.conn)

        if evidence_row is not None and data is not None:
            # Create updated data with elapsed=True
            updated_data = {
                **data,
                "elapsed": True,
                "elapsed_at": current_time.isoformat(),
            }

            # Create correction content
            correction = EvidenceContent(
                tenant_id=ctx.tenant_id,  # type: ignore[arg-type]
                subject_id=evidence_row.get("subject_id"),
                evidence_type=EVIDENCE_TYPE_WAITING,
                title=f"Waiting period elapsed for notice {notice_id}",
                data=updated_data,
                source="system",
                collected_at=current_time,
                collected_by_id=ctx.actor_id,  # type: ignore[arg-type]
            )

            # Supersede with updated state
            await supersede_evidence(
                {
                    "original_id": evidence_row["id"],
                    "correction": correction,
                    "reason": "Waiting period elapsed",
                },
                ctx,
            )

            just_marked = True

    return {
        "notice_id": notice_id,
        "elapsed": True,
        "ends_at": state["ends_at"],
        "paused": False,
        "remaining_seconds": None,
        "just_marked_elapsed": just_marked,
        "reason": None,
    }
