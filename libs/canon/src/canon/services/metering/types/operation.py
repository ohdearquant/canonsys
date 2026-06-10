"""Usage operation types for metering."""

from __future__ import annotations

from enum import Enum

__all__ = ["UsageOperation"]


class UsageOperation(str, Enum):
    """Type of governance operation metered."""

    GATE = "gate"
    POLICY = "policy"
    DECISION = "decision"
