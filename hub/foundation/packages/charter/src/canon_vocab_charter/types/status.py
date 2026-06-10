"""Charter status enumeration.

Lifecycle: DRAFT -> ACTIVE -> SUSPENDED/RETIRED

DRAFT: Charter is being authored, not yet enforceable
ACTIVE: Charter is in effect, policies are enforced
SUSPENDED: Temporarily inactive (e.g., during audit/review)
RETIRED: Permanently inactive, superseded by new version
"""

from kron.types import Enum

__all__ = ("CharterStatus",)


class CharterStatus(Enum):
    """Charter lifecycle states.

    Lifecycle: DRAFT -> ACTIVE -> SUSPENDED/RETIRED

    DRAFT: Charter is being authored, not yet enforceable.
    ACTIVE: Charter is in effect, policies are enforced.
    SUSPENDED: Temporarily inactive (e.g., during audit/review).
    RETIRED: Permanently inactive, superseded by new version.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"

    def is_enforceable(self) -> bool:
        """Check if charter can enforce policies in this state."""
        return self == CharterStatus.ACTIVE

    def can_transition_to(self, target: "CharterStatus") -> bool:
        """Check if transition to target state is valid.

        Valid transitions:
        - DRAFT -> ACTIVE (activation)
        - ACTIVE -> SUSPENDED (suspension)
        - ACTIVE -> RETIRED (retirement)
        - SUSPENDED -> ACTIVE (reactivation)
        - SUSPENDED -> RETIRED (retirement from suspension)
        """
        valid_transitions: dict[CharterStatus, frozenset[CharterStatus]] = {
            CharterStatus.DRAFT: frozenset({CharterStatus.ACTIVE}),
            CharterStatus.ACTIVE: frozenset({CharterStatus.SUSPENDED, CharterStatus.RETIRED}),
            CharterStatus.SUSPENDED: frozenset({CharterStatus.ACTIVE, CharterStatus.RETIRED}),
            CharterStatus.RETIRED: frozenset(),  # Terminal state
        }
        return target in valid_transitions.get(self, frozenset())
