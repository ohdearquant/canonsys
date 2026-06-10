"""Require authentication at minimum assurance level.

Complete vertical slice:
- Validates subject has required authentication posture
- Wraps verify_strong_auth_posture with gate semantics
- Raises AuthPostureInsufficientError if posture below required level

Regulatory: NIST SP 800-63B Section 4 - Authenticator Assurance Levels
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

from ..exceptions import AuthPostureInsufficientError
from ..types import AuthPosture

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "AuthPostureInsufficientError",
    "RequireStrongAuthSpecs",
    "require_strong_auth",
]


class RequireStrongAuthSpecs(BaseModel):
    """Specs for require strong auth phrase."""

    # inputs
    subject_id: UUID
    required_posture: AuthPosture = "strong"
    # outputs
    satisfied: bool = False
    posture: AuthPosture | None = None
    factors: tuple[str, ...] | None = None


@canon_phrase(
    Operable.from_structure(RequireStrongAuthSpecs),
    inputs={"subject_id", "required_posture"},
    outputs={"satisfied", "subject_id", "required_posture", "posture", "factors"},
)
async def require_strong_auth(
    options: RequireStrongAuthSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that subject has authentication at minimum assurance level.

    Gate pattern that enforces authentication posture requirements.
    Wraps verify_strong_auth_posture with raise-on-failure semantics.

    Args:
        options: Options containing subject_id and required_posture.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if posture meets requirement.

    Raises:
        AuthPostureInsufficientError: If posture below required level.

    Regulatory citations:
        - NIST SP 800-63B Section 4: Authenticator assurance levels
        - SOC 2 CC6.1: Logical and physical access controls
        - GDPR Art. 32: Security of processing - appropriate authentication
    """
    from .verify_strong_auth_posture import (
        VerifyStrongAuthPostureSpecs,
        verify_strong_auth_posture,
    )

    verify_options = VerifyStrongAuthPostureSpecs(
        subject_id=options.subject_id,
        required_posture=options.required_posture,
    )
    result = await verify_strong_auth_posture(verify_options, ctx)

    if not result["meets_requirement"]:
        raise AuthPostureInsufficientError(
            subject_id=options.subject_id,
            required_posture=options.required_posture,
            actual_posture=result["posture"],
        )

    return {
        "satisfied": True,
        "subject_id": options.subject_id,
        "required_posture": options.required_posture,
        "posture": result["posture"],
        "factors": result["factors"],
    }
