"""Re-export ConsentScope from canon-core.

Single source of truth: canon.entities.consent owns ConsentScope.
"""

from canon.entities.consent import ConsentScope

__all__ = ("ConsentScope",)
