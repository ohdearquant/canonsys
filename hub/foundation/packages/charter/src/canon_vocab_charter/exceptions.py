"""Charter domain exceptions.

Business rule violations specific to charter operations.
"""

from canon.exceptions import CanonError

__all__ = (
    "CharterAlreadyActiveError",
    "CharterError",
    "CharterNotFoundError",
    "CharterNotRatifiedError",
    "CharterStatusError",
    "PolicyEvaluationError",
    "SurfaceAlreadyBoundError",
    "SurfaceNotBoundError",
)


class CharterError(CanonError):
    """Base exception for charter domain errors."""

    pass


class CharterNotFoundError(CharterError):
    """Raised when charter is not found."""

    def __init__(self, charter_id: str) -> None:
        super().__init__(f"Charter not found: {charter_id}")
        self.charter_id = charter_id


class CharterStatusError(CharterError):
    """Raised when charter is in invalid status for operation."""

    def __init__(self, charter_id: str, current_status: str, required_status: str) -> None:
        super().__init__(
            f"Charter {charter_id} is in status '{current_status}', "
            f"but '{required_status}' is required"
        )
        self.charter_id = charter_id
        self.current_status = current_status
        self.required_status = required_status


class CharterAlreadyActiveError(CharterError):
    """Raised when trying to activate already active charter."""

    def __init__(self, charter_id: str) -> None:
        super().__init__(f"Charter {charter_id} is already active")
        self.charter_id = charter_id


class CharterNotRatifiedError(CharterError):
    """Raised when trying to activate unratified charter."""

    def __init__(self, charter_id: str) -> None:
        super().__init__(f"Charter {charter_id} must be ratified before activation")
        self.charter_id = charter_id


class SurfaceNotBoundError(CharterError):
    """Raised when surface is not bound to charter."""

    def __init__(self, charter_id: str, surface_id: str) -> None:
        super().__init__(f"Surface '{surface_id}' is not bound to charter {charter_id}")
        self.charter_id = charter_id
        self.surface_id = surface_id


class SurfaceAlreadyBoundError(CharterError):
    """Raised when surface is already bound to charter."""

    def __init__(self, charter_id: str, surface_id: str) -> None:
        super().__init__(f"Surface '{surface_id}' is already bound to charter {charter_id}")
        self.charter_id = charter_id
        self.surface_id = surface_id


class PolicyEvaluationError(CharterError):
    """Raised when policy evaluation fails."""

    def __init__(self, message: str, policy_id: str | None = None) -> None:
        super().__init__(message)
        self.policy_id = policy_id
