"""Spec adapters for framework-specific transformations.

Adapters:
    - PydanticSpecAdapter: Spec <-> Pydantic FieldInfo/BaseModel
    - DataClassSpecAdapter: Spec <-> dataclass fields
    - SQLSpecAdapter: Spec -> SQL DDL (one-way)

Factory:
    get_adapter(name) - Get adapter class by name
"""

from .factory import AdapterType, get_adapter

__all__ = (
    "AdapterType",
    "get_adapter",
)
