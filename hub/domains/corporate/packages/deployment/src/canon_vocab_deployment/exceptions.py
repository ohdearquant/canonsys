"""Deployment feature exceptions.

Deployment-specific exceptions for gate failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.exceptions import InvariantViolation

if TYPE_CHECKING:
    from uuid import UUID

    from .types import ApprovalStatus, EnvironmentType

__all__ = [
    "DeploymentApprovalRequiredError",
    "ProductionEnvironmentRequiredError",
    "RequirementNotMetError",
]


class ProductionEnvironmentRequiredError(InvariantViolation):
    """Operation requires production environment.

    Raised when: require_production_environment finds resource
    is not in production environment.

    Regulatory basis:
    - SOC 2 CC6.7: Change management
    - ISO 27001 A.12.1.4: Separation of environments
    - PCI DSS v4.0 Req. 6.5: Separate test/production

    Phrase: require_production_environment
    """

    default_regulation = "SOC 2 CC6.7"
    default_message = "Operation requires production environment"

    __slots__ = ("environment", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        environment: EnvironmentType,
        **kwargs: Any,
    ) -> None:
        """Initialize production environment required error.

        Args:
            resource_id: UUID of the resource.
            environment: Current environment type.
            **kwargs: Additional arguments passed to parent.
        """
        self.resource_id = resource_id
        self.environment = environment
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "environment": environment.value,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Operation requires production environment, got {environment.value}",
            context=merged_context,
            **kwargs,
        )


class DeploymentApprovalRequiredError(InvariantViolation):
    """Deployment requires approval.

    Raised when: require_deployment_approval finds deployment
    lacks approved status.

    Regulatory basis:
    - SOX Section 404: Internal controls
    - SOC 2 CC8.1: Change management
    - ISO 27001 A.12.1.2: Change management

    Phrase: require_deployment_approval
    """

    default_regulation = "SOX Section 404"
    default_message = "Deployment requires approval"

    __slots__ = ("approval_status", "deployment_id")

    def __init__(
        self,
        deployment_id: UUID,
        approval_status: ApprovalStatus,
        **kwargs: Any,
    ) -> None:
        """Initialize deployment approval required error.

        Args:
            deployment_id: UUID of the deployment.
            approval_status: Current approval status.
            **kwargs: Additional arguments passed to parent.
        """
        self.deployment_id = deployment_id
        self.approval_status = approval_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "deployment_id": str(deployment_id),
            "approval_status": approval_status.value,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Deployment approval status: {approval_status.value}",
            context=merged_context,
            **kwargs,
        )
