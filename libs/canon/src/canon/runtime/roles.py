"""Role enforcement for Charter Runtime.

Enforces MFA requirements and break_glass access controls as defined
by RoleNode in compiled charters.

Charter roles declare requirements for phase actions:
    roles:
        hr_manager:
            actions: [assess_eligibility, evaluate_performance]
            requires_mfa: true
        legal_counsel:
            actions: [certify_termination]
            break_glass: true

Enforcement checks:
    - MFA: User's current session must have mfa_verified=True
    - Break glass: User must have an active elevated session

Regulatory Context:
    - SOC 2 CC6.1-6.3: Principle of least privilege, elevated access
    - NIST SP 800-63B: Multi-factor authentication for high-risk actions
    - SOX 302/404: Segregation of duties, documented authority

Usage:
    from canon.runtime.roles import enforce_role_requirements

    # Enforce before allowing phase action
    result = await enforce_role_requirements(
        user_id=user_id,
        phase_name="hm_approval",
        workflow_name="pip_workflow",
        compiled=compiled_charter,
        conn=conn,
    )
    # Raises MFARequiredError or BreakGlassRequiredError on failure
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from canon.db import TenantScope, select_one

if TYPE_CHECKING:
    import asyncpg

    from canon.dsl.ast import RoleNode
    from canon.dsl.compiler import CompiledCharter

__all__ = (
    "BreakGlassRequiredError",
    "MFARequiredError",
    "RoleCheckResult",
    "enforce_role_requirements",
    "find_role_for_phase",
    "verify_role_requirements",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoleCheckResult:
    """Result of verifying a user against role requirements.

    Attributes:
        allowed: True if the user meets all requirements.
        role_name: Name of the role that was checked.
        requires_mfa: Whether the role requires MFA.
        requires_break_glass: Whether the role requires break_glass.
        mfa_verified: Whether the user has verified MFA.
        break_glass_active: Whether the user has active break_glass session.
        reason: Human-readable explanation when not allowed.
    """

    allowed: bool
    role_name: str
    requires_mfa: bool
    requires_break_glass: bool
    mfa_verified: bool
    break_glass_active: bool
    reason: str | None = None

    def to_dict(self) -> dict:
        """Serialize for logging/evidence."""
        return {
            "allowed": self.allowed,
            "role_name": self.role_name,
            "requires_mfa": self.requires_mfa,
            "requires_break_glass": self.requires_break_glass,
            "mfa_verified": self.mfa_verified,
            "break_glass_active": self.break_glass_active,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MFARequiredError(Exception):
    """User needs MFA verification to act on this phase.

    Raised when a role requires MFA but the user's current session
    does not have mfa_verified=True.
    """

    def __init__(self, role_name: str, phase_name: str) -> None:
        self.role_name = role_name
        self.phase_name = phase_name
        super().__init__(
            f"MFA verification required for role '{role_name}' to act on phase '{phase_name}'"
        )


class BreakGlassRequiredError(Exception):
    """Phase requires break_glass elevated access.

    Raised when a role requires break_glass but the user does not have
    an active elevated session.
    """

    def __init__(self, role_name: str, phase_name: str) -> None:
        self.role_name = role_name
        self.phase_name = phase_name
        super().__init__(
            f"Break-glass elevated access required for role '{role_name}' "
            f"to act on phase '{phase_name}'"
        )


# ---------------------------------------------------------------------------
# Role lookup
# ---------------------------------------------------------------------------


def find_role_for_phase(
    phase_name: str,
    workflow_name: str,
    compiled: CompiledCharter,
) -> RoleNode | None:
    """Find which role governs a specific phase based on phase actions.

    Matches the phase's action names against role action lists.
    Returns the first role whose actions include any of the phase's
    actions.

    Args:
        phase_name: Name of the phase.
        workflow_name: Name of the workflow containing the phase.
        compiled: The compiled charter.

    Returns:
        RoleNode if a governing role is found, None if no role
        constrains this phase.
    """
    # Find the phase node
    phase_node = _get_phase_node(compiled, workflow_name, phase_name)
    if phase_node is None:
        return None

    # Collect the phase's action names
    phase_actions = frozenset(action.call.name for action in phase_node.actions)
    if not phase_actions:
        return None

    # Match against roles
    for role in compiled.roles:
        role_actions = frozenset(role.actions)
        if phase_actions & role_actions:
            return role

    return None


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


async def verify_role_requirements(
    *,
    user_id: UUID,
    role_node: RoleNode,
    conn: asyncpg.Connection,
) -> RoleCheckResult:
    """Check if user meets MFA and break_glass requirements for a role.

    Queries the sessions table for the user's most recent active session
    to determine MFA status. For break_glass, checks for an active
    elevated session flag.

    Args:
        user_id: The user attempting the action.
        role_node: The RoleNode defining requirements.
        conn: Database connection (must have tenant context).

    Returns:
        RoleCheckResult with pass/fail and details.
    """
    mfa_verified = False
    break_glass_active = False

    # Check MFA status from the user's most recent active session
    if role_node.requires_mfa:
        mfa_verified = await _check_mfa_verified(user_id, conn)

    # Check break_glass status
    if role_node.break_glass:
        break_glass_active = await _check_break_glass_active(user_id, conn)

    # Determine if allowed
    mfa_ok = mfa_verified if role_node.requires_mfa else True
    bg_ok = break_glass_active if role_node.break_glass else True
    allowed = mfa_ok and bg_ok

    # Build reason if not allowed
    reason: str | None = None
    if not allowed:
        reasons: list[str] = []
        if not mfa_ok:
            reasons.append("MFA verification required but not verified")
        if not bg_ok:
            reasons.append("Break-glass elevated access required but not active")
        reason = "; ".join(reasons)

    return RoleCheckResult(
        allowed=allowed,
        role_name=role_node.name,
        requires_mfa=role_node.requires_mfa,
        requires_break_glass=role_node.break_glass,
        mfa_verified=mfa_verified,
        break_glass_active=break_glass_active,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Combined enforcement
# ---------------------------------------------------------------------------


async def enforce_role_requirements(
    *,
    user_id: UUID,
    phase_name: str,
    workflow_name: str,
    compiled: CompiledCharter,
    conn: asyncpg.Connection,
) -> RoleCheckResult:
    """Find role for phase and verify requirements; raise on failure.

    This is the primary entry point for role enforcement. It combines
    role lookup and verification into a single call.

    When no role governs the phase, returns an allowed result (no
    restrictions apply).

    Args:
        user_id: The user attempting the action.
        phase_name: Name of the phase.
        workflow_name: Name of the workflow.
        compiled: The compiled charter.
        conn: Database connection.

    Returns:
        RoleCheckResult (always allowed if returned without exception).

    Raises:
        MFARequiredError: If the role requires MFA and user hasn't verified.
        BreakGlassRequiredError: If the role requires break_glass and
            user doesn't have an elevated session.
    """
    role_node = find_role_for_phase(phase_name, workflow_name, compiled)

    if role_node is None:
        logger.debug(
            "No role constraints for phase '%s' in workflow '%s'",
            phase_name,
            workflow_name,
        )
        return RoleCheckResult(
            allowed=True,
            role_name="(none)",
            requires_mfa=False,
            requires_break_glass=False,
            mfa_verified=False,
            break_glass_active=False,
            reason=None,
        )

    result = await verify_role_requirements(
        user_id=user_id,
        role_node=role_node,
        conn=conn,
    )

    if not result.allowed:
        logger.warning(
            "Role enforcement failed for user %s on phase '%s' (role: %s, reason: %s)",
            user_id,
            phase_name,
            role_node.name,
            result.reason,
        )

        # Raise the appropriate specific error
        if result.requires_mfa and not result.mfa_verified:
            raise MFARequiredError(role_node.name, phase_name)

        if result.requires_break_glass and not result.break_glass_active:
            raise BreakGlassRequiredError(role_node.name, phase_name)

    logger.debug(
        "Role enforcement passed for user %s on phase '%s' (role: %s)",
        user_id,
        phase_name,
        role_node.name,
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _check_mfa_verified(
    user_id: UUID,
    conn: asyncpg.Connection,
) -> bool:
    """Check if user has an active session with MFA verified.

    Queries sessions table for the most recent non-revoked session
    belonging to the user with mfa_verified=True.

    Args:
        user_id: The user to check.
        conn: Database connection.

    Returns:
        True if user has an MFA-verified active session.
    """
    row = await select_one(
        "sessions",
        where={
            "user_id": user_id,
            "mfa_verified": True,
            "is_revoked": False,
            "is_deleted": False,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    return row is not None


async def _check_break_glass_active(
    user_id: UUID,
    conn: asyncpg.Connection,
) -> bool:
    """Check if user has an active break-glass elevated session.

    Queries sessions table for a non-revoked session with
    auth_method='break_glass'.

    Args:
        user_id: The user to check.
        conn: Database connection.

    Returns:
        True if user has an active break-glass session.
    """
    row = await select_one(
        "sessions",
        where={
            "user_id": user_id,
            "auth_method": "break_glass",
            "is_revoked": False,
            "is_deleted": False,
        },
        conn=conn,
        tenant_scope=TenantScope.REQUIRED,
    )
    return row is not None


def _get_phase_node(compiled: CompiledCharter, workflow_name: str, phase_name: str):
    """Get PhaseNode from compiled charter by workflow and phase name."""
    for workflow in compiled.ast.workflows:
        if workflow.name == workflow_name:
            for phase in workflow.phases:
                if phase.name == phase_name:
                    return phase
    return None
