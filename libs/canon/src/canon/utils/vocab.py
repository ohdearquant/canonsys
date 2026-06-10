"""Content validation utilities.

These functions validate content models using attribute access (getattr).
They accept Any type to avoid layering violations - the actual content
models are validated at runtime via duck typing.
"""

from datetime import datetime
from typing import Any

from kron.utils import now_utc

__all__ = (
    "expiration_must_be_set",
    "expiration_must_not_be_met_as_of",
    "status_must_be_active",
    "token_must_be_valid",
)


def expiration_must_be_set(content: Any) -> None:
    """Raise if ``expires_at`` is not set on *content*."""
    if getattr(content, "expires_at", None) is None:
        raise ValueError("Expiration must be set on content model.")


def expiration_must_not_be_met_as_of(content: Any, as_of: datetime | None = None) -> None:
    """Raise if *content* has already expired as of *as_of* (default: now)."""
    if not hasattr(content, "expires_at"):
        raise TypeError("Content model cannot have expiration set.")
    if content.expires_at is not None:
        now = as_of or now_utc()
        if now >= content.expires_at:
            raise ValueError("Content model has expired.")


def status_must_be_active(content: Any) -> None:
    """Raise if *content* status is not ``active``."""
    if _resolve_enum_value(getattr(content, "status", None)) != "active":
        raise ValueError("Content model status is not active.")


def token_must_be_valid(content: Any, as_of: datetime | None = None) -> None:
    """Assert that a consent token content is valid.

    A valid consent token is one that is ACTIVE and not expired
    as of the given reference time.

    Args:
        content: The consent token content to validate.
        as_of: Optional reference time for expiration check.
            Defaults to current UTC time if not provided.

    Raises:
        ValueError: If the token is not active or has expired.
    """
    status_must_be_active(content)
    expiration_must_not_be_met_as_of(content, as_of=as_of)


def _resolve_enum_value(value: object) -> str:
    if hasattr(value, "value"):
        return str(value.value).lower()
    if isinstance(value, str):
        return value.lower()
    return value
