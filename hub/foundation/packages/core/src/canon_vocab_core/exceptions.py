"""Core feature exceptions.

Re-exports exceptions used by core compliance features.

For the full exception hierarchy, see:
- canon.enforcement.exceptions (InvariantViolation hierarchy)
- canon.enforcement.errors (RequirementNotMetError)
"""

from __future__ import annotations

from decimal import Decimal

from canon.enforcement.errors import RequirementNotMetError

__all__ = [
    "RequirementNotMetError",
    "ValueExceedsLimitError",
]


class ValueExceedsLimitError(RequirementNotMetError):
    """Raised when a value exceeds the allowed limit.

    Regulatory:
        - BSA/AML (Bank Secrecy Act) - CTR thresholds
        - SOX Section 404 - Internal controls
        - COSO Framework - Authorization limits
    """

    def __init__(
        self,
        value: Decimal,
        limit: Decimal,
        description: str | None = None,
    ):
        self.value = value
        self.limit = limit
        self.exceeded_by = value - limit
        self.description = description

        desc_suffix = f" ({description})" if description else ""
        super().__init__(
            requirement="value_within_limit",
            reason=f"Value {value} exceeds limit {limit} by {self.exceeded_by}{desc_suffix}",
        )
