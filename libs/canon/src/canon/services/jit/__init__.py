# TODO #227: JIT service requires implementation — document access grants
# with time-bounded tokens. Types and exceptions are defined but no actions
# (issue, redeem, revoke, find, list) are implemented. The backend
# (apps/web/backend) reimplements JIT access directly via Evidence records
# and DocumentAccessToken SQL without using these canonical types.
"""JIT (Just-In-Time) permit feature - vertical slice for single-use execution capability.

This module provides the complete JIT permit domain implementation:
- Types: PermitToken, PermitTokenContent, TokenStatus, TokenType, JITPermitDenyReason
- Actions: (TODO) issue, redeem, revoke, find, list
- Exceptions: PermitNotFoundError, PermitExpiredError, etc.

JIT permits solve the problem of binding authorization to a specific transaction:
- Roles allow multiple actions over time
- PermitToken binds authorization to a single transaction boundary

Usage:
    from hub.services.jit import (
        # Types
        PermitToken,
        PermitTokenContent,
        TokenStatus,
        JITPermitDenyReason,
        # Exceptions
        PermitExpiredError,
        PermitAlreadyUsedError,
    )
"""

# Exceptions
from .exceptions import (
    PermitActionMismatchError,
    PermitAlreadyUsedError,
    PermitExpiredError,
    PermitNotFoundError,
    PermitRevokedError,
    PermitSubjectMismatchError,
)

# Types
from .types import (
    JITPermitDenyReason,
    PermitToken,
    PermitTokenContent,
    TokenStatus,
    TokenType,
)

__all__ = [
    # Types
    "PermitToken",
    "PermitTokenContent",
    "TokenStatus",
    "TokenType",
    "JITPermitDenyReason",
    # Exceptions
    "PermitNotFoundError",
    "PermitExpiredError",
    "PermitAlreadyUsedError",
    "PermitRevokedError",
    "PermitSubjectMismatchError",
    "PermitActionMismatchError",
]
