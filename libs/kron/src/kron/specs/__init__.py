"""Kron specs absorbed from krons for canon self-containment.

Core Classes:
    - Spec: Framework-agnostic field specification
    - Operable: Ordered Spec collection with adapter interface
    - Phrase: Typed operation template with auto-generated Options/Result types
    - CrudPattern: Declarative CRUD pattern for phrase handlers

Adapters (via adapters submodule):
    - PydanticSpecAdapter: Spec <-> Pydantic FieldInfo/BaseModel
    - DataClassSpecAdapter: Spec <-> dataclass fields
    - SQLSpecAdapter: Spec -> SQL DDL

DDL Types (from adapters.sql_ddl):
    - SchemaSpec, TableSpec: Database schema specifications
    - ColumnSpec, IndexSpec, TriggerSpec: Table structure specs
    - ForeignKeySpec, CheckConstraintSpec, UniqueConstraintSpec: Constraint specs
"""

from .adapters.factory import AdapterType, get_adapter
from .adapters.sql_ddl import (
    FK,
    CheckConstraintSpec,
    ColumnSpec,
    FKMeta,
    ForeignKeySpec,
    IndexMethod,
    IndexSpec,
    OnAction,
    SchemaSpec,
    TableSpec,
    TriggerSpec,
    UniqueConstraintSpec,
    Vector,
    VectorMeta,
)
from .operable import Operable
from .phrase import CrudOperation, CrudPattern, Phrase, phrase
from .protocol import SpecAdapter
from .spec import CommonMeta, Spec

__all__ = (
    # Core
    "CommonMeta",
    "Spec",
    "Operable",
    "Phrase",
    "CrudPattern",
    "CrudOperation",
    "phrase",
    # Protocol
    "SpecAdapter",
    # Adapter factory
    "AdapterType",
    "get_adapter",
    # DDL Enums
    "OnAction",
    "IndexMethod",
    # DDL Types (re-exported from db_types)
    "FK",
    "FKMeta",
    "Vector",
    "VectorMeta",
    # DDL Spec dataclasses
    "ColumnSpec",
    "ForeignKeySpec",
    "IndexSpec",
    "TriggerSpec",
    "CheckConstraintSpec",
    "UniqueConstraintSpec",
    "TableSpec",
    "SchemaSpec",
)
