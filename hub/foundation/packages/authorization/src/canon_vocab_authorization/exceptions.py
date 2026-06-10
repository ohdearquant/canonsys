"""Authorization domain exceptions.

These exceptions are raised by authorization features when requirements are not met.
All inherit from RequirementNotMetError (operational) or AuthorizationViolation (invariant).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from canon.enforcement.errors import RequirementNotMetError
from canon.enforcement.exceptions import AuthorizationViolation

if TYPE_CHECKING:
    from uuid import UUID

__all__ = [
    "ApprovalChainIncompleteError",
    "AuthorizationViolation",
    "ClearanceInsufficientError",
    "DualApprovalRequiredError",
    # Domain-specific exceptions
    "ERClearanceNotGrantedError",
    "JustificationRequiredError",
    # Re-export base classes for convenience
    "RequirementNotMetError",
    "RoleApprovalRequiredError",
    "SegregationAnalysisRequiredError",
    "SoDViolationError",
]


class ERClearanceNotGrantedError(AuthorizationViolation):
    """ER (Employee Relations) clearance not granted for subject.

    Raised when: check_er_clearance finds an active ER case that
    prevents action on the subject.

    Regulatory basis:
        - Employment law (due process)
        - Company policy (ER escalation required)
    """

    default_regulation = "Employment Law"
    default_message = "ER clearance required before action"

    __slots__ = ("er_case_id", "subject_id")

    def __init__(
        self,
        subject_id: UUID,
        er_case_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.subject_id = subject_id
        self.er_case_id = er_case_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"subject_id": str(subject_id)}
        if er_case_id:
            base_context["er_case_id"] = str(er_case_id)
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"ER clearance not granted for subject {subject_id}"
            + (f" (active case: {er_case_id})" if er_case_id else ""),
            context=merged_context,
            **kwargs,
        )


class JustificationRequiredError(AuthorizationViolation):
    """Access justification required for sensitive resource.

    Raised when: require_access_justification finds no approved
    justification for accessing a resource.

    Regulatory basis:
        - HIPAA 164.312(a) (Access controls)
        - GDPR Art. 5(1)(c) (Data minimization)
        - SOC 2 CC6.1 (Logical access)
    """

    default_regulation = "SOC 2 CC6.1"
    default_message = "Documented justification required for access"

    __slots__ = ("requester_id", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        requester_id: UUID,
        **kwargs: Any,
    ) -> None:
        self.resource_id = resource_id
        self.requester_id = requester_id
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "requester_id": str(requester_id),
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Access justification required for resource {resource_id}",
            context=merged_context,
            **kwargs,
        )


class ClearanceInsufficientError(AuthorizationViolation):
    """Requester lacks required clearance level.

    Raised when: require_release_clearance finds the requester's
    clearance level is below what's required for the resource.

    Regulatory basis:
        - ITAR 22 CFR 120-130 (Export controls)
        - EAR 15 CFR 730-774 (Export administration)
        - NISPOM 32 CFR 117 (Classified information)
    """

    default_regulation = "ITAR 22 CFR 120"
    default_message = "Insufficient clearance for information release"

    __slots__ = ("actual_level", "required_level", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        required_level: str,
        actual_level: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.resource_id = resource_id
        self.required_level = required_level
        self.actual_level = actual_level
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "resource_id": str(resource_id),
            "required_level": required_level,
        }
        if actual_level:
            base_context["actual_level"] = actual_level
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Clearance insufficient for resource {resource_id}: "
            f"required '{required_level}'" + (f", has '{actual_level}'" if actual_level else ""),
            context=merged_context,
            **kwargs,
        )


class SoDViolationError(AuthorizationViolation):
    """Segregation of Duties violation - same person in conflicting roles.

    Raised when: require_distinct_identities finds the same identity
    in two roles that must be performed by different people.

    Regulatory basis:
        - SOX Section 404 (Segregation of duties)
        - COSO Framework (Control activities)
        - SOC 2 CC5.1 (Control activities)
        - PCI DSS 6.4.2 (Separation of duties)
    """

    default_regulation = "SOX Section 404"
    default_message = "Segregation of Duties violation"

    __slots__ = ("identity_id", "role_a", "role_b")

    def __init__(
        self,
        identity_id: UUID,
        role_a: str,
        role_b: str,
        **kwargs: Any,
    ) -> None:
        self.identity_id = identity_id
        self.role_a = role_a
        self.role_b = role_b
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "identity_id": str(identity_id),
            "role_a": role_a,
            "role_b": role_b,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"SoD violation: '{role_a}' and '{role_b}' must be different people "
            f"(both are {identity_id})",
            context=merged_context,
            **kwargs,
        )


class DualApprovalRequiredError(AuthorizationViolation):
    """Dual (or multi) approval required but not present.

    Raised when: require_dual_approval finds insufficient approvals.

    Regulatory basis:
        - SOX Section 404 (Segregation of duties)
        - PCI DSS v4.0 Req. 8.6 (Multi-factor)
        - SOC 2 CC6.1 (Logical access controls)
    """

    default_regulation = "SOX Section 404"
    default_message = "Dual approval required"

    __slots__ = ("approvals_received", "approvals_required", "request_id")

    def __init__(
        self,
        request_id: UUID,
        approvals_required: int,
        approvals_received: int,
        **kwargs: Any,
    ) -> None:
        self.request_id = request_id
        self.approvals_required = approvals_required
        self.approvals_received = approvals_received
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "request_id": str(request_id),
            "approvals_required": approvals_required,
            "approvals_received": approvals_received,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Request {request_id} requires {approvals_required} approvals, "
            f"received {approvals_received}",
            context=merged_context,
            **kwargs,
        )


class SegregationAnalysisRequiredError(AuthorizationViolation):
    """Segregation of duties analysis required before access grant.

    Raised when: require_segregation_analysis finds no completed analysis.

    Regulatory basis:
        - SOX Section 404 (Internal controls)
        - SOC 2 CC5.1 (Control activities)
        - COSO Framework (Segregation of duties)
    """

    default_regulation = "SOX Section 404"
    default_message = "Segregation analysis required"

    __slots__ = ("analysis_status", "resource_id")

    def __init__(
        self,
        resource_id: UUID,
        analysis_status: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.resource_id = resource_id
        self.analysis_status = analysis_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {"resource_id": str(resource_id)}
        if analysis_status:
            base_context["analysis_status"] = analysis_status
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Segregation analysis required for resource {resource_id}"
            + (f" (current status: {analysis_status})" if analysis_status else ""),
            context=merged_context,
            **kwargs,
        )


class ApprovalChainIncompleteError(AuthorizationViolation):
    """Approval chain not complete for request.

    Raised when: verify_approval_chain_complete finds the chain
    is not in COMPLETE status.

    Regulatory basis:
        - SOX Section 404 (Segregation of duties)
        - SOC 2 CC6.1 (Logical access controls)
        - ISO 27001 A.9.2 (User access management)
    """

    default_regulation = "SOX Section 404"
    default_message = "Approval chain incomplete"

    __slots__ = ("chain_status", "request_id")

    def __init__(
        self,
        request_id: UUID,
        chain_status: str,
        **kwargs: Any,
    ) -> None:
        self.request_id = request_id
        self.chain_status = chain_status
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "request_id": str(request_id),
            "chain_status": chain_status,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Approval chain for request {request_id} is not complete (status: {chain_status})",
            context=merged_context,
            **kwargs,
        )


class RoleApprovalRequiredError(AuthorizationViolation):
    """Specific role approval required but not obtained.

    Raised when: verify_role_approval finds no approval from the required role.

    Regulatory basis:
        - SOX Section 404 (Internal controls)
        - SOC 2 CC6.1 (Logical access controls)
        - GDPR Art. 37-39 (DPO requirements)
        - ISO 27001 A.6.1.1 (Roles and responsibilities)
    """

    default_regulation = "SOX Section 404"
    default_message = "Role-specific approval required"

    __slots__ = ("request_id", "required_role")

    def __init__(
        self,
        request_id: UUID,
        required_role: str,
        **kwargs: Any,
    ) -> None:
        self.request_id = request_id
        self.required_role = required_role
        extra_context = kwargs.pop("context", None) or {}
        base_context = {
            "request_id": str(request_id),
            "required_role": required_role,
        }
        merged_context = {**base_context, **extra_context}
        super().__init__(
            f"Request {request_id} requires approval from {required_role}",
            context=merged_context,
            **kwargs,
        )
