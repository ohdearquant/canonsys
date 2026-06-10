"""Awareness protocols for content model introspection."""

from __future__ import annotations

from typing import Literal

AwareOf = Literal["actor", "user", "tenant", "subject"]
"""Valid awareness types for content models."""


def is_aware_of(obj: object, fields: set[AwareOf], /) -> bool:
    """Check if object has all specified awareness fields.

    Args:
        obj: Object to check (typically a ContentModel instance)
        fields: Set of awareness types to check for

    Returns:
        True if obj has {field}_id attribute for all fields

    Example:
        >>> is_aware_of(some_content, {"tenant", "actor"})
        True  # if some_content has tenant_id and actor_id
    """
    for field in fields:
        if not hasattr(obj, f"{field}_id"):
            return False
    return True
