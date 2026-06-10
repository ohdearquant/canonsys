"""Service module - base classes for canon services.

This module provides the base service infrastructure that services in canon
build upon.

Exports:
    - BaseService: Generic service base class with tenant isolation and evidence emission
    - ResponseModel: Standard response wrapper with ok/fail factory methods
    - RequestModel: Base class for service request payloads
    - Action: Base enum class for service actions
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

__all__ = (
    "Action",
    "BaseService",
    "RequestModel",
    "ResponseModel",
)


class Action(str, Enum):
    """Base class for service action enums.

    Services define their own Action subclass listing available operations.

    Example:
        class VendorAction(Action):
            REGISTER = "register"
            GET = "get"
            LIST = "list"
    """

    pass


class RequestModel(BaseModel):
    """Base class for service request models.

    Services define their own RequestModel subclass with:
    - action: The action to perform (from their Action enum)
    - action_class: ClassVar pointing to their Action enum
    - Additional fields for action options
    """

    action_class: ClassVar[type[Action]]


@dataclass
class ResponseModel:
    """Standard response wrapper for service operations.

    Provides uniform structure for success and failure responses
    with optional data payload and error messages.

    Usage:
        # Success
        return ResponseModel.ok({"id": "123", "name": "test"})

        # Failure
        return ResponseModel.fail("Not found", data={"id": "123"})
    """

    status: str
    """Response status: 'success' or 'error'."""

    message: str | None = None
    """Optional message (typically for errors)."""

    data: dict[str, Any] = field(default_factory=dict)
    """Response payload."""

    @classmethod
    def ok(cls, data: dict[str, Any] | None = None) -> ResponseModel:
        """Create a success response.

        Args:
            data: Optional response payload

        Returns:
            ResponseModel with status='success'
        """
        return cls(status="success", data=data or {})

    @classmethod
    def fail(cls, message: str, data: dict[str, Any] | None = None) -> ResponseModel:
        """Create a failure response.

        Args:
            message: Error message
            data: Optional additional error context

        Returns:
            ResponseModel with status='error'
        """
        return cls(status="error", message=message, data=data or {})


R = TypeVar("R", bound=RequestModel)


class BaseService(Generic[R]):
    """Base class for tenant-scoped services.

    Provides:
    - Tenant isolation
    - Uniform request dispatch
    - Evidence emission for compliance tracking

    Services subclass this and implement _handle_{action} methods.

    Example:
        class VendorService(BaseService[VendorRequest]):
            request_class = VendorRequest
            _service_name = "vendor"

            async def _handle_register(self, req: VendorRequest) -> ResponseModel:
                ...
    """

    request_class: ClassVar[type[RequestModel]]
    """Request model class for this service."""

    _service_name: ClassVar[str]
    """Service name for evidence emission."""

    def __init__(self, tenant_id: UUID) -> None:
        """Initialize service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for isolation
        """
        self.tenant_id = tenant_id

    def _options_as(self, req: R, options_class: type[BaseModel]) -> BaseModel:
        """Extract and validate options from request.

        Args:
            req: The incoming request
            options_class: Pydantic model to validate against

        Returns:
            Validated options model
        """
        # Get action from request
        action = getattr(req, "action", None)
        if action is None:
            raise ValueError("Request has no action")

        # Get the action_option_map from the action class
        action_class = req.action_class
        if hasattr(action_class, "action_option_map"):
            option_map = action_class.action_option_map()
            expected_class = option_map.get(action)
            if expected_class and expected_class != options_class:
                raise ValueError(
                    f"Action {action} expects {expected_class.__name__}, "
                    f"got {options_class.__name__}"
                )

        # Extract fields from request that match options_class fields
        request_data = req.model_dump(exclude={"action"})
        return options_class.model_validate(request_data)

    async def emit_chained_evidence(
        self,
        operation: str,
        data: dict[str, Any],
        subject_id: UUID | None = None,
        title: str | None = None,
        collected_by_id: UUID | None = None,
        evidence_type: str | None = None,
        chain_event_type: str | None = None,
    ) -> Any:
        """Emit evidence with chain entry for compliance tracking.

        This is a placeholder that should be overridden or integrated
        with the actual evidence emission system.

        Args:
            operation: Operation name (e.g., "create_pre_adverse")
            data: Evidence payload
            subject_id: Person subject of the operation
            title: Human-readable title
            collected_by_id: User who performed the action
            evidence_type: Evidence classification
            chain_event_type: Optional chain event type

        Returns:
            Created evidence record (implementation-dependent)
        """
        raise NotImplementedError(
            "Evidence emission not yet integrated. "
            "Override emit_chained_evidence() or integrate with the evidence system."
        )
