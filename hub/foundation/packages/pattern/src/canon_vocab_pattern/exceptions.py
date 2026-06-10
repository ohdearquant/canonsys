"""Pattern domain exceptions.

Exceptions for pattern detection violations.
Pattern violations indicate anti-gaming detection triggers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.exceptions import AuthorizationViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "PatternThresholdExceededError",
]


class PatternThresholdExceededError(AuthorizationViolation):
    """Pattern threshold exceeded - repeated action detected.

    Raised when: check_pattern_threshold finds the action count
    meets or exceeds the configured threshold.

    Regulatory basis:
    - SOX Section 302: Management assessment of internal controls
    - SOC 2 CC5.2: Control activities - anti-gaming
    - BSA/AML: Suspicious activity pattern detection

    Phrase: pattern_threshold_must_not_be_exceeded
    """

    default_regulation = "SOX Section 302"
    default_message = "Pattern threshold exceeded"

    __slots__ = ("action_type", "count", "entity_id", "lookback_days", "threshold")

    def __init__(
        self,
        entity_id: UUID,
        action_type: str,
        count: int,
        threshold: int,
        lookback_days: int,
        **kwargs: Any,
    ) -> None:
        """Initialize pattern threshold exceeded error.

        Args:
            entity_id: UUID of the entity with pattern detected.
            action_type: Type of action being monitored.
            count: Actual count of prior actions.
            threshold: Threshold that was exceeded.
            lookback_days: Lookback window in days.
            **kwargs: Additional arguments passed to parent.
        """
        self.entity_id = entity_id
        self.action_type = action_type
        self.count = count
        self.threshold = threshold
        self.lookback_days = lookback_days
        super().__init__(
            f"Pattern threshold exceeded for '{action_type}': "
            f"{count} actions in {lookback_days} days (threshold: {threshold})",
            context={
                "entity_id": str(entity_id),
                "action_type": action_type,
                "count": count,
                "threshold": threshold,
                "lookback_days": lookback_days,
            },
            **kwargs,
        )
