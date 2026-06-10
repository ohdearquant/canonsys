"""Re-export ConsentStatus from canon-core.

Single source of truth: canon.entities.consent owns ConsentStatus.
"""

from canon.entities.consent import ConsentStatus

__all__ = ("ConsentStatus",)
