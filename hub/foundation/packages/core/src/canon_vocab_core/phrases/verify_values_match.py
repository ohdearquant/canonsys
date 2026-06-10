"""Verify values match phrase.

Verifies two values match for consistency checks.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import now_utc

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifyValuesMatchSpecs", "verify_values_match"]


class VerifyValuesMatchSpecs(BaseModel):
    """Specs for verify values match phrase.

    Regulatory Citations:
        - FCRA: Pre-adverse action notices must contain accurate information
        - GDPR Art. 5(1)(d): Personal data shall be accurate and kept up to date
        - SOX Section 404: Internal controls must ensure data integrity
    """

    # inputs
    value_a: Any
    value_b: Any
    field_name_a: str
    field_name_b: str
    # outputs
    matched: bool
    checked_at: datetime
    reason: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


@canon_phrase(
    Operable.from_structure(VerifyValuesMatchSpecs),
    inputs={
        "value_a",
        "value_b",
        "field_name_a",
        "field_name_b",
    },
    outputs={
        "matched",
        "value_a",
        "value_b",
        "field_name_a",
        "field_name_b",
        "checked_at",
        "reason",
    },
)
async def verify_values_match(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Verify two values match for consistency checks.

    Generic value comparison for ensuring data consistency across systems.
    Useful for validating that values in notices, documents, or records
    match the corresponding values in systems of record.

    Args:
        options: Verification options (value_a, value_b, field_name_a, field_name_b)
        ctx: Request context

    Returns:
        dict with match result
    """
    value_a = options["value_a"]
    value_b = options["value_b"]
    field_name_a: str = options["field_name_a"]
    field_name_b: str = options["field_name_b"]

    now = now_utc()
    matched = value_a == value_b

    # Build reason for mismatch
    reason: str | None = None
    if not matched:
        val_a_str = _safe_str(value_a)
        val_b_str = _safe_str(value_b)
        reason = (
            f"Value mismatch: {field_name_a}={val_a_str} does not match {field_name_b}={val_b_str}"
        )

    return {
        "matched": matched,
        "value_a": value_a,
        "value_b": value_b,
        "field_name_a": field_name_a,
        "field_name_b": field_name_b,
        "checked_at": now,
        "reason": reason,
    }


def _safe_str(value: Any, max_length: int = 100) -> str:
    """Convert value to string, truncating if needed."""
    s = str(value)
    if len(s) > max_length:
        return s[: max_length - 3] + "..."
    return s
