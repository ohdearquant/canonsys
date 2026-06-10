"""Check if receipt was submitted within required window.

Receipts must be submitted within a defined window from the
transaction date to maintain audit trail integrity.

Regulatory Context:
    IRS Publication 463 requires substantiation of expenses.
    SOX Section 404 requires timely documentation of transactions.
    Late submissions may trigger additional review requirements.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import FreshnessStatus

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckReceiptFreshnessSpecs", "check_receipt_freshness"]


class CheckReceiptFreshnessSpecs(BaseModel):
    """Specs for receipt freshness check phrase."""

    # inputs
    receipt_ts: datetime
    submission_ts: datetime
    window_days: int = 60
    stale_threshold_days: int = 45
    # outputs
    status: FreshnessStatus | None = None


@canon_phrase(
    Operable.from_structure(CheckReceiptFreshnessSpecs),
    inputs={"receipt_ts", "submission_ts", "window_days", "stale_threshold_days"},
    outputs={"status", "receipt_ts", "submission_ts", "window_days"},
)
async def check_receipt_freshness(
    options,
    ctx: RequestContext,
) -> dict:
    """Check if receipt was submitted within required window.

    Args:
        options: Check options (receipt_ts, submission_ts, window_days, stale_threshold_days)
        ctx: Request context for audit trail

    Returns:
        dict with status, receipt_ts, submission_ts, window_days
    """
    receipt_ts: datetime = options.receipt_ts
    submission_ts: datetime = options.submission_ts
    window_days: int = options.window_days
    stale_threshold_days: int = options.stale_threshold_days

    days_elapsed = (submission_ts - receipt_ts).days

    if days_elapsed > window_days:
        status: FreshnessStatus = "expired"
    elif days_elapsed > stale_threshold_days:
        status = "stale"
    else:
        status = "fresh"

    return {
        "status": status,
        "receipt_ts": receipt_ts,
        "submission_ts": submission_ts,
        "window_days": window_days,
    }
