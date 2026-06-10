"""Enforcement levels and specs for policy evaluation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from kron.specs.operable import Operable
from kron.specs.spec import Spec
from kron.utils import now_utc

__all__ = (
    "EnforcementLevel",
    "EnforcementSpecs",
)


from kron.types import Enum


class EnforcementLevel(Enum):
    """How strictly to enforce policy violations."""

    HARD_MANDATORY = "hard_mandatory"
    SOFT_MANDATORY = "soft_mandatory"
    ADVISORY = "advisory"


class EnforcementSpecs(BaseModel):
    """Fields for policy enforcement results."""

    enforcement: str = EnforcementLevel.HARD_MANDATORY.value
    policy_id: str
    violation_code: str | None = None
    evaluated_at: datetime = Field(default_factory=now_utc)
    evaluation_ms: float = Field(default=0.0, ge=0.0)

    @field_validator("enforcement", mode="before")
    @classmethod
    def _extract_enum_value(cls, v):
        """Extract .value from enum members."""
        return v.value if hasattr(v, "value") else v

    @classmethod
    def get_specs(cls) -> list[Spec]:
        """Get list of enforcement Specs."""
        operable = Operable.from_structure(cls)
        return list(operable.get_specs())
