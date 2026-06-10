"""Require that facts conform to a versioned schema.

Complete vertical slice:
- Validates facts against versioned schema definition
- Uses Pydantic for schema validation
- Raises SchemaValidationError if invalid

Regulatory: PRD-017 Section 7.1 - Invalid schema = automatic DENY
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from canon.enforcement.executor import canon_phrase
from kron.specs import Operable
from kron.utils import compute_hash, now_utc

from ..exceptions import RequirementNotMetError

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = [
    "RequireFactsSchemaValidSpecs",
    "SchemaValidationError",
    "require_facts_schema_valid",
]


class SchemaValidationError(RequirementNotMetError):
    """Facts do not conform to required schema.

    Regulatory:
        - PRD-017 Section 7.1: Invalid schema = automatic DENY
        - SPEC-003: Certificate schema enforcement
    """

    def __init__(
        self,
        schema_version: str,
        errors: list[dict[str, Any]],
    ):
        self.schema_version = schema_version
        self.errors = errors
        super().__init__(
            requirement="facts_schema_valid",
            reason=f"Facts do not conform to schema {schema_version}: {len(errors)} errors",
        )


class RequireFactsSchemaValidSpecs(BaseModel):
    """Specs for require facts schema valid phrase."""

    # inputs
    facts: dict[str, Any]
    schema_version: str
    strict: bool = True  # If True, extra fields are forbidden
    # outputs
    satisfied: bool = False
    schema_hash: str | None = None
    validated_at: datetime | None = None


# Schema registry - maps version strings to Pydantic model classes
# In production, this would be loaded from database or config
_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {}


def register_schema(version: str, model: type[BaseModel]) -> None:
    """Register a schema version.

    Args:
        version: Schema version string (e.g., "canon.hr@2026.01").
        model: Pydantic model class for validation.
    """
    _SCHEMA_REGISTRY[version] = model


def get_schema(version: str) -> type[BaseModel] | None:
    """Get a registered schema by version.

    Args:
        version: Schema version string.

    Returns:
        Pydantic model class or None if not found.
    """
    return _SCHEMA_REGISTRY.get(version)


@canon_phrase(
    Operable.from_structure(RequireFactsSchemaValidSpecs),
    inputs={"facts", "schema_version", "strict"},
    outputs={"satisfied", "schema_version", "schema_hash", "validated_at"},
)
async def require_facts_schema_valid(
    options: RequireFactsSchemaValidSpecs,
    ctx: RequestContext,
) -> dict:
    """Require that facts conform to a versioned schema.

    Gate pattern that validates facts against a registered schema.
    Raises SchemaValidationError if validation fails.

    Args:
        options: Options containing facts and schema_version.
        ctx: Request context (tenant, actor).

    Returns:
        Dict with satisfied=True if facts are valid.

    Raises:
        SchemaValidationError: If facts do not conform to schema.
        ValueError: If schema version is not registered.
    """
    facts = options.facts
    schema_version = options.schema_version
    now = now_utc()

    # Get registered schema
    schema_model = get_schema(schema_version)

    if schema_model is None:
        # Schema not registered - fail closed
        raise SchemaValidationError(
            schema_version=schema_version,
            errors=[
                {
                    "type": "schema_not_found",
                    "msg": f"Schema {schema_version} not registered",
                }
            ],
        )

    # Validate using Pydantic
    try:
        if options.strict:
            # Create model with extra='forbid' if strict
            schema_model.model_validate(facts, strict=True)
        else:
            schema_model.model_validate(facts)
    except ValidationError as e:
        errors = [
            {
                "type": err["type"],
                "loc": list(err["loc"]),
                "msg": err["msg"],
            }
            for err in e.errors()
        ]
        raise SchemaValidationError(
            schema_version=schema_version,
            errors=errors,
        ) from e

    # Compute schema hash for reproducibility
    schema_hash = compute_hash({"version": schema_version, "fields": sorted(facts.keys())})

    return {
        "satisfied": True,
        "schema_version": schema_version,
        "schema_hash": schema_hash,
        "validated_at": now,
    }
