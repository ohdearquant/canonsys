"""Derive extension duration and validate against maximum.

This is a compliance timing primitive. Extensions MUST be derived
from actual dates, not accepted as user-asserted durations.

Regulatory Context:
    SEC Rule 12b-25 limits filing extensions. Contract extensions
    may have caps. System-derived durations prevent gaming by
    asserting artificially small extensions to bypass approvals.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import TYPE_CHECKING

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveExtensionDaysSpecs", "derive_extension_days"]


class DeriveExtensionDaysSpecs(BaseModel):
    """Specs for extension days derivation phrase."""

    # inputs
    current_eol: date_cls
    requested_eol: date_cls
    max_extension_days: int = 90
    # outputs
    extension_days: int | None = None
    exceeds_max: bool | None = None


@canon_phrase(
    Operable.from_structure(DeriveExtensionDaysSpecs),
    inputs={"current_eol", "requested_eol", "max_extension_days"},
    outputs={
        "extension_days",
        "current_eol",
        "requested_eol",
        "exceeds_max",
        "max_extension_days",
    },
)
async def derive_extension_days(
    options,
    ctx: RequestContext,
) -> dict:
    """Derive extension duration and validate against maximum.

    Args:
        options: Derivation options (current_eol, requested_eol, max_extension_days)
        ctx: Request context for audit trail

    Returns:
        dict with extension_days, current_eol, requested_eol, exceeds_max, max_extension_days

    Raises:
        ValueError: If requested_eol is before current_eol
    """
    current_eol: date_cls = options.current_eol
    requested_eol: date_cls = options.requested_eol
    max_extension_days: int = options.max_extension_days

    extension_days = (requested_eol - current_eol).days

    if extension_days < 0:
        raise ValueError(
            f"requested_eol ({requested_eol}) cannot be before current_eol ({current_eol})"
        )

    return {
        "extension_days": extension_days,
        "current_eol": current_eol,
        "requested_eol": requested_eol,
        "exceeds_max": extension_days > max_extension_days,
        "max_extension_days": max_extension_days,
    }
