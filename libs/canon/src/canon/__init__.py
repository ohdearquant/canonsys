"""CanonSys Core - Decision certification infrastructure.

Core:
    Entity - Base entity with kron.Node identity + ContentModel
    ContentModel - Domain fields (pure data, no audit logic)
    register_entity - Decorator to bind Entity subclass to a database table

DB:
    FK[Model] - Foreign key annotation
    Vector[dim] - pgvector embedding annotation
    generate_ddl - CREATE TABLE from Entity class

Architecture:
    kron provides: Node, NodeConfig, audit fields, lifecycle methods
    canon-core adds: is_active/activate/deactivate, entity registry
"""

from .db import FK, FKMeta, Vector, VectorMeta, generate_ddl
from .entities import ContentModel, Entity

__all__ = [
    # Core
    "ContentModel",
    "Entity",
    # DB Types
    "FK",
    "FKMeta",
    "Vector",
    "VectorMeta",
    # DDL
    "generate_ddl",
]
