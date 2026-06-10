"""Degraded mode support for fail-open governance.

When the governance system is degraded (pool exhausted, circuit open):
- ADVISORY gates: fail-open (allow with warning)
- SOFT_MANDATORY gates: fail-open with requires_review=True
- HARD_MANDATORY gates: fail-closed (block)

This prevents the governance layer from becoming a SPOF.

Reference: CONSTRAINTS-001-enterprise-ilities.md §2 Availability
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from kron.utils import now_utc


class DegradedReason(str, Enum):
    """Reason for degraded operation."""

    POOL_EXHAUSTED = "pool_exhausted"
    CIRCUIT_OPEN = "circuit_open"
    TIMEOUT = "timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"


@dataclass(frozen=True)
class DegradedModeConfig:
    """Configuration for degraded mode behavior.

    Attributes:
        advisory_fail_open: Allow ADVISORY gates to pass in degraded mode
        soft_mandatory_fail_open: Allow SOFT_MANDATORY gates (with review)
        hard_mandatory_fail_open: Allow HARD_MANDATORY gates (DANGEROUS)
        log_degraded: Log all degraded decisions
    """

    advisory_fail_open: bool = True
    soft_mandatory_fail_open: bool = False
    hard_mandatory_fail_open: bool = False  # NEVER True in production
    log_degraded: bool = True


@dataclass(frozen=True)
class DegradedResult:
    """Result from degraded mode evaluation.

    Indicates that a gate was evaluated in degraded mode.
    """

    allowed: bool
    degraded: bool = True
    reason: DegradedReason = DegradedReason.POOL_EXHAUSTED
    enforcement: str = "advisory"
    message: str = "Evaluated in degraded mode"
    timestamp: datetime = field(default_factory=now_utc)

    @property
    def requires_review(self) -> bool:
        """Whether human review is required."""
        return self.enforcement == "soft_mandatory" and self.allowed

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging/audit."""
        return {
            "allowed": self.allowed,
            "degraded": self.degraded,
            "reason": self.reason.value,
            "enforcement": self.enforcement,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "requires_review": self.requires_review,
        }


@dataclass
class DegradedMode:
    """Handler for degraded mode operations.

    Determines whether to allow actions when normal evaluation is unavailable.

    Usage:
        degraded = DegradedMode()

        try:
            result = await gate.check(ctx)
        except EnginePoolExhausted:
            result = degraded.evaluate(
                enforcement="advisory",
                reason=DegradedReason.POOL_EXHAUSTED,
            )
    """

    config: DegradedModeConfig = field(default_factory=DegradedModeConfig)

    # Metrics
    _degraded_count: int = field(default=0, init=False)
    _allowed_count: int = field(default=0, init=False)
    _blocked_count: int = field(default=0, init=False)

    @property
    def metrics(self) -> dict[str, int]:
        """Get degraded mode metrics."""
        return {
            "degraded_total": self._degraded_count,
            "degraded_allowed": self._allowed_count,
            "degraded_blocked": self._blocked_count,
        }

    def evaluate(
        self,
        enforcement: str,
        reason: DegradedReason | str = DegradedReason.POOL_EXHAUSTED,
        context: dict[str, Any] | None = None,
    ) -> DegradedResult:
        """Evaluate whether to allow action in degraded mode.

        Args:
            enforcement: Enforcement level (hard_mandatory, soft_mandatory, advisory)
            reason: Why degraded mode was triggered
            context: Optional context for logging

        Returns:
            DegradedResult indicating whether action is allowed
        """
        self._degraded_count += 1

        # Convert string reason to enum if needed
        if isinstance(reason, str):
            try:
                reason = DegradedReason(reason)
            except ValueError:
                reason = DegradedReason.SERVICE_UNAVAILABLE

        enforcement_lower = enforcement.lower()

        if enforcement_lower == "advisory":
            allowed = self.config.advisory_fail_open
            message = (
                "Advisory gate bypassed in degraded mode"
                if allowed
                else "Advisory gate blocked in degraded mode"
            )

        elif enforcement_lower == "soft_mandatory":
            allowed = self.config.soft_mandatory_fail_open
            message = (
                "Soft-mandatory gate bypassed in degraded mode (requires review)"
                if allowed
                else "Soft-mandatory gate blocked in degraded mode"
            )

        elif enforcement_lower == "hard_mandatory":
            allowed = self.config.hard_mandatory_fail_open
            if allowed:
                message = "DANGER: Hard-mandatory gate bypassed in degraded mode"
            else:
                message = "Hard-mandatory gate blocked in degraded mode (fail-closed)"

        else:
            allowed = False
            message = f"Unknown enforcement level '{enforcement}' blocked"

        if allowed:
            self._allowed_count += 1
        else:
            self._blocked_count += 1

        return DegradedResult(
            allowed=allowed,
            degraded=True,
            reason=reason,
            enforcement=enforcement_lower,
            message=message,
        )

    def reset_metrics(self) -> None:
        """Reset degraded mode metrics."""
        self._degraded_count = 0
        self._allowed_count = 0
        self._blocked_count = 0


# Global degraded mode handler
_degraded_mode: DegradedMode | None = None


def get_degraded_mode() -> DegradedMode:
    """Get singleton degraded mode handler."""
    global _degraded_mode
    if _degraded_mode is None:
        _degraded_mode = DegradedMode()
    return _degraded_mode


def configure_degraded_mode(config: DegradedModeConfig) -> DegradedMode:
    """Configure global degraded mode handler."""
    global _degraded_mode
    _degraded_mode = DegradedMode(config=config)
    return _degraded_mode


__all__ = [
    "DegradedMode",
    "DegradedModeConfig",
    "DegradedReason",
    "DegradedResult",
    "configure_degraded_mode",
    "get_degraded_mode",
]
