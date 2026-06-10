from kron.types import Enum

__all__ = ("JITPermitDenyReason",)


class JITPermitDenyReason(Enum):
    """Reasons for permit token denial."""

    NOT_FOUND = "not_found"
    EXPIRED = "expired"
    ALREADY_USED = "already_used"
    REVOKED = "revoked"
    SUBJECT_MISMATCH = "subject_mismatch"
    ACTION_MISMATCH = "action_mismatch"
