"""Metering domain exceptions.

These exceptions are raised when quota limits are exceeded.
"""

from __future__ import annotations

import datetime

__all__ = ["QuotaExceededError"]


class QuotaExceededError(Exception):
    """Raised when tenant exceeds quota.

    Attributes:
        tenant_id: Tenant that exceeded quota
        quota_type: Type of quota exceeded
        limit: Quota limit
        current: Current usage
        reset_at: When quota resets
    """

    def __init__(
        self,
        tenant_id: str,
        quota_type: str,
        limit: float,
        current: float,
        reset_at: float | None = None,
    ):
        self.tenant_id = tenant_id
        self.quota_type = quota_type
        self.limit = limit
        self.current = current
        self.reset_at = reset_at

        msg = f"Tenant {tenant_id} exceeded {quota_type} quota: {current:.1f}/{limit:.1f}"
        if reset_at:
            reset_dt = datetime.datetime.fromtimestamp(reset_at)
            msg += f" (resets at {reset_dt.isoformat()})"

        super().__init__(msg)
