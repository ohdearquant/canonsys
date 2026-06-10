"""Policy scope enumeration."""

from kron.types import Enum


class PolicyScope(Enum):
    """Scope of policy application.

    Determines at what level a policy is enforced.
    Narrower scopes can override broader ones.
    """

    GLOBAL = "global"  # Platform-wide default
    JURISDICTION = "jurisdiction"  # Regional (US-NYC, EU-DE)
    TENANT = "tenant"  # Company-specific override
    ACTION = "action"  # Per-action configuration
