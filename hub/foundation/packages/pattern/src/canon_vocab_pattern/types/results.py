"""Pattern detection result types.

Frozen dataclasses for pattern detection operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

__all__ = ["CumulativeAmountResult", "PatternThresholdResult", "PriorActionCountResult"]


@dataclass(frozen=True, slots=True)
class PriorActionCountResult:
    """Result of prior action count query.

    Attributes:
        count: Number of matching actions in lookback window
        entity_id: The entity whose actions were counted
        action_type: The type of action counted
        lookback_days: The lookback window used
        window_start: Start of lookback window
        window_end: End of lookback window (query time)
    """

    count: int
    entity_id: UUID
    action_type: str
    lookback_days: int
    window_start: datetime
    window_end: datetime


@dataclass(frozen=True, slots=True)
class PatternThresholdResult:
    """Result of pattern threshold check.

    Attributes:
        exceeded: True if pattern count >= threshold
        count: Actual count of prior actions
        threshold: The threshold that was checked
        entity_id: The entity checked
        action_type: The action type checked
        lookback_days: The lookback window used
    """

    exceeded: bool
    count: int
    threshold: int
    entity_id: UUID
    action_type: str
    lookback_days: int


@dataclass(frozen=True, slots=True)
class CumulativeAmountResult:
    """Result of cumulative amount derivation.

    Tracks total amounts within a lookback window for anti-gaming detection.
    Used for "5 small = 1 material" pattern detection.

    Attributes:
        entity_id: The entity whose amounts were summed
        metric: The metric type tracked (reallocation, exception, override, transfer)
        period_days: The lookback window used
        total_amount: Sum of amounts in the window
        count: Number of individual amounts summed
        exceeds_threshold: True if total_amount >= threshold
        threshold: The threshold checked (None if not provided)
        window_start: Start of lookback window
        window_end: End of lookback window (query time)
    """

    entity_id: UUID
    metric: str
    period_days: int
    total_amount: Decimal
    count: int
    exceeds_threshold: bool
    threshold: Decimal | None
    window_start: datetime
    window_end: datetime
