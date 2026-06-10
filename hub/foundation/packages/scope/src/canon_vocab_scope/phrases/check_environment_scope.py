"""Check environment scope validity.

Validates operations against permitted environments.

Regulatory context:
    - SOC 2 CC6.1: Logical access controls - environment separation
    - SOC 2 CC8.1: Change management - deployment controls
    - ISO 27001 A.12.1.4: Separation of development, testing, and production
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["CheckEnvironmentScopeSpecs", "check_environment_scope"]


class CheckEnvironmentScopeSpecs(BaseModel):
    """Specs for check environment scope phrase."""

    # inputs
    environment: str = Field(
        ...,
        description="Current environment (e.g., 'production', 'staging', 'dev')",
    )
    allowed_environments: list[str] = Field(
        ...,
        description="List of environments where operation is permitted",
    )
    # outputs
    valid: bool | None = None
    reason: str | None = None


@canon_phrase(
    Operable.from_structure(CheckEnvironmentScopeSpecs),
    inputs={"environment", "allowed_environments"},
    outputs={"valid", "environment", "allowed_environments", "reason"},
)
async def check_environment_scope(
    options: CheckEnvironmentScopeSpecs,
    ctx: RequestContext,
) -> dict:
    """Check that an operation is permitted in the specified environment.

    Validates that the current environment is in the list of allowed
    environments for an operation. Used to enforce environment separation
    and prevent unauthorized cross-environment operations.

    Regulatory Citations:
        - SOC 2 CC6.1: The entity implements logical access security software
          and infrastructure to protect against threats. Environment separation
          is a core control.
        - SOC 2 CC8.1: The entity authorizes, designs, develops, configures,
          documents, tests, approves, and implements changes. Environment
          gates are part of change control.
        - ISO 27001 A.12.1.4: Development, testing, and operational environments
          shall be separated to reduce the risks of unauthorized access or
          changes to the operational environment.

    Args:
        options: Environment scope options (environment, allowed_environments).
        ctx: Request context (tenant, actor).

    Returns:
        dict with valid, environment, allowed_environments, reason.

    Examples:
        >>> # Prevent debug mode in production
        >>> options = CheckEnvironmentScopeSpecs(
        ...     environment="production",
        ...     allowed_environments=["development", "staging"],
        ... )
        >>> result = await check_environment_scope(options, ctx)
        >>> if not result["valid"]:
        ...     raise EnvironmentNotAllowedError(result["reason"])

        >>> # Restrict data export to non-production
        >>> options = CheckEnvironmentScopeSpecs(
        ...     environment="production",
        ...     allowed_environments=["development", "testing"],
        ... )
        >>> result = await check_environment_scope(options, ctx)
        >>> if not result["valid"]:
        ...     raise ProductionDataExportBlockedError()
    """
    environment_normalized = options.environment.strip().lower()
    allowed_normalized = {e.strip().lower() for e in options.allowed_environments}

    valid = environment_normalized in allowed_normalized

    reason: str | None = None
    if not valid:
        allowed_str = ", ".join(sorted(options.allowed_environments))
        reason = (
            f"Environment '{options.environment}' not permitted. "
            f"Allowed environments: {allowed_str}"
        )

    return {
        "valid": valid,
        "environment": options.environment,
        "allowed_environments": tuple(sorted(options.allowed_environments)),
        "reason": reason,
    }
