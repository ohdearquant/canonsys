"""Derive compensating logging coverage.

Evaluates logging coverage for compensating control assessment.

Regulatory Context:
    - SOX Section 404 (Compensating controls for material weaknesses)
    - SOC 2 CC7.2 (System monitoring)
    - ISO 27001 A.12.4 (Logging and monitoring)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.db import fetch
from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..types import LoggingCoverage

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["DeriveLoggingCoverageSpecs", "derive_compensating_logging_coverage"]


def _derive_coverage(logged: int, required: int) -> LoggingCoverage:
    """Derive coverage category from counts.

    Thresholds:
        - 100%: full_equivalent
        - >= 80%: partial_equivalent
        - >= 50%: minimal
        - < 50% or unknown: unknown
    """
    if required == 0:
        return "unknown"

    pct = (logged / required) * 100
    if pct >= 100:
        return "full_equivalent"
    elif pct >= 80:
        return "partial_equivalent"
    elif pct >= 50:
        return "minimal"
    return "unknown"


class DeriveLoggingCoverageSpecs(BaseModel):
    """Specs for derive logging coverage phrase."""

    # inputs
    logging_config_id: UUID
    required_events: list[str]
    # outputs
    coverage: LoggingCoverage
    logged_events: int
    required_events_count: int
    missing_events: tuple[str, ...]


@canon_phrase(
    Operable.from_structure(DeriveLoggingCoverageSpecs),
    inputs={"logging_config_id", "required_events"},
    outputs={"coverage", "logged_events", "required_events_count", "missing_events"},
)
async def derive_compensating_logging_coverage(
    options: dict,
    ctx: RequestContext,
) -> dict:
    """Derive logging coverage for compensating control assessment.

    Evaluates whether a logging configuration adequately captures
    required security events. Used when audit logging serves as a
    compensating control for other monitoring mechanisms.

    Args:
        options: Derivation options (logging_config_id, required_events)
        ctx: Request context (tenant, actor)

    Returns:
        dict with coverage, logged_events, required_events_count, missing_events

    Regulatory:
        - SOX Section 404: Logging as evidence of control operation
        - SOC 2 CC7.2: Security event monitoring requirements
        - ISO 27001 A.12.4.1: Event logging policy compliance
    """
    logging_config_id = options.get("logging_config_id")
    required_events = options.get("required_events") or []

    if not required_events:
        return {
            "coverage": "unknown",
            "logged_events": 0,
            "required_events_count": 0,
            "missing_events": (),
        }

    # Query logging configuration for covered events
    query = """
        SELECT event_type
        FROM logging_config_events
        WHERE config_id = $1
          AND tenant_id = $2
          AND enabled = true
    """
    rows = await fetch(
        query,
        logging_config_id,
        ctx.tenant_id,
        conn=ctx.conn,
    )

    if not rows:
        # No logging configuration found
        return {
            "coverage": "unknown",
            "logged_events": 0,
            "required_events_count": len(required_events),
            "missing_events": tuple(required_events),
        }

    # Calculate coverage
    logged_event_types = {row["event_type"] for row in rows}
    required_set = set(required_events)

    covered = logged_event_types & required_set
    missing = required_set - logged_event_types

    coverage = _derive_coverage(len(covered), len(required_set))

    return {
        "coverage": coverage,
        "logged_events": len(covered),
        "required_events_count": len(required_set),
        "missing_events": tuple(sorted(missing)),
    }
