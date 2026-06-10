"""Service configuration for KronService."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from kron.types import HashableModel

__all__ = (
    "KronConfig",
    "ServiceConfig",
)


# Module-level cache for schema field keys (keyed by class)
_SCHEMA_FIELD_KEYS_CACHE: dict[type[BaseModel], set[str]] = {}


def _get_schema_field_keys(cls: type[BaseModel]) -> set[str]:
    """Get field names for a Pydantic model (cached).

    Uses model_fields instead of model_json_schema to include fields
    that may be excluded from JSON schema (e.g., SkipJsonSchema fields).
    """
    if cls not in _SCHEMA_FIELD_KEYS_CACHE:
        _SCHEMA_FIELD_KEYS_CACHE[cls] = set(cls.model_fields.keys())
    return _SCHEMA_FIELD_KEYS_CACHE[cls]


class ServiceConfig(HashableModel):
    """Base service configuration.

    Provides common configuration for all service backends.
    Extra kwargs are captured in the kwargs dict.
    """

    provider: str = Field(..., min_length=4, max_length=50)
    name: str = Field(..., min_length=4, max_length=100)
    request_options: type[BaseModel] | None = Field(default=None, exclude=True)
    timeout: int = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)
    version: str | None = None
    tags: list[str] = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _validate_kwargs(cls, data: dict[str, Any]) -> dict[str, Any]:
        kwargs = data.pop("kwargs", {})
        field_keys = _get_schema_field_keys(cls)
        for k in list(data.keys()):
            if k not in field_keys:
                kwargs[k] = data.pop(k)
        data["kwargs"] = kwargs
        return data

    @field_validator("request_options", mode="before")
    def _validate_request_options(cls, v):
        if v is None:
            return None
        if isinstance(v, type) and issubclass(v, BaseModel):
            return v
        if isinstance(v, BaseModel):
            return v.__class__
        raise ValueError("request_options must be a Pydantic model type")

    def validate_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate payload against request_options schema.

        Args:
            data: Payload to validate.

        Returns:
            Validated payload (unchanged if valid).

        Raises:
            ValueError: If validation fails.
        """
        if not self.request_options:
            return data
        try:
            self.request_options.model_validate(data)
            return data
        except Exception as e:
            raise ValueError("Invalid payload") from e


class KronConfig(ServiceConfig):
    """Configuration for KronService.

    Attributes:
        operable: Canonical Operable containing all field specs for this service.
        action_timeout: Timeout for action execution (None = no timeout).
        use_policies: Enable policy evaluation.
        policy_timeout: Timeout for policy evaluation.
        fail_open_on_engine_error: Allow action if engine fails (DANGEROUS).
        hooks: Available hooks {name: callable}.
    """

    operable: Any = None
    """Canonical Operable for the service's field namespace."""

    action_timeout: float | None = None
    """Timeout for action execution in seconds. None means no timeout."""

    use_policies: bool = True
    """Enable policy evaluation."""

    policy_timeout: float = 10.0
    """Timeout for policy evaluation in seconds."""

    fail_open_on_engine_error: bool = False
    """If True, allow action when engine fails. DANGEROUS for production."""

    hooks: dict[str, Callable[..., Awaitable[Any]]] = Field(default_factory=dict)
    """Available hooks {name: hook_function}."""
