"""Policy decision outcomes."""

from kron.types import Enum


class PolicyDecision(Enum):
    """Outcome of policy evaluation.

    ALLOW: All requirements satisfied
    DENY: One or more requirements failed
    NOT_APPLICABLE: Policy doesn't apply to this context (vacuous truth)
    """

    ALLOW = "allow"
    DENY = "deny"
    NOT_APPLICABLE = "not_applicable"
