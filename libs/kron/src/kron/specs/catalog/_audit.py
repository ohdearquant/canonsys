"""Audit field Specs - tracking, versioning, soft delete, hashing."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from kron.specs.operable import Operable
from kron.specs.spec import Spec
from kron.utils import now_utc


class AuditSpecs(BaseModel):
    updated_at: datetime = Field(default_factory=now_utc)
    updated_by: str | None = None
    is_active: bool = True
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    version: int = Field(default=1, ge=0)
    content_hash: str | None = None
    integrity_hash: str | None = None

    @classmethod
    def get_specs(cls, use_uuid: bool) -> list[Spec]:
        """Get list of audit Specs based on actor ID type."""
        operable = Operable.from_structure(cls)
        specs = {spec.name: spec for spec in operable.get_specs()}

        if use_uuid:
            specs["updated_by"] = Spec(UUID, name="updated_by").as_nullable()
            specs["deleted_by"] = Spec(UUID, name="deleted_by").as_nullable()

        return list(specs.values())
