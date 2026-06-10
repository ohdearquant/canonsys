"""Content field Specs - identity, timestamps, content, metadata, embeddings."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from kron.specs.operable import Operable
from kron.specs.spec import Spec
from kron.types import Unset, UnsetType
from kron.types.db_types import VectorMeta
from kron.utils import now_utc


class ContentSpecs(BaseModel):
    """Core content fields for elements/nodes."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now_utc)
    content: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None

    @classmethod
    def get_specs(
        cls,
        *,
        content_type: type | UnsetType = Unset,
        dim: int | UnsetType = Unset,
    ) -> list[Spec]:
        """Get list of content Specs.

        Args:
            content_type: Type for content/metadata fields (default: dict).
            dim: Embedding dimension. Unset = list[float], int = Vector[dim].
        """
        operable = Operable.from_structure(cls)
        specs = {spec.name: spec for spec in operable.get_specs()}

        # Override content/metadata type if specified
        if content_type is not Unset:
            specs["content"] = Spec(content_type, name="content").as_nullable()
            specs["metadata"] = Spec(content_type, name="metadata").as_nullable()

        # Add node_metadata alias (DB mode uses this name to avoid SQL reserved word)
        specs["node_metadata"] = Spec(dict[str, Any], name="node_metadata").as_nullable()

        # Override embedding with vector dimension if specified
        if dim is not Unset and isinstance(dim, int):
            specs["embedding"] = Spec(
                list[float],
                name="embedding",
                embedding=VectorMeta(dim),
            ).as_nullable()

        return list(specs.values())
