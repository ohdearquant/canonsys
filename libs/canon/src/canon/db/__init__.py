"""Database utilities for CanonSys.

Types:
    FK[Model] - Foreign key annotation
    Vector[dim] - pgvector embedding annotation

DDL:
    generate_ddl(entity_cls) - Generate CREATE TABLE from Entity
    get_fk_dependencies(entity_cls) - Get FK dependency table names

Connection:
    connection - Get connection with tenant context injection
    transaction - Get connection with transaction and tenant context
    DbContext - Database context for tenant isolation
    TenantScope - Tenant context enforcement mode

CRUD:
    insert, upsert, update, delete - Write operations
    select, select_one, count - Read operations
    execute, fetch, fetchval - Raw SQL

Errors:
    map_db_error - Map asyncpg exceptions to typed CanonError

Validation:
    validate_identifier - SQL injection prevention
    sanitize_order_by - Safe ORDER BY clause
"""

from kron.core import generate_ddl, get_fk_dependencies
from kron.types import FK, FKMeta, Vector, VectorMeta, extract_kron_db_meta

from .connection import (
    DbContext,
    TenantContextRequired,
    TenantScope,
    close_pool,
    connection,
    get_db_context,
    get_pool,
    set_db_context,
    transaction,
    with_context,
)
from .crud import (
    count,
    delete,
    execute,
    fetch,
    fetchval,
    insert,
    select,
    select_one,
    update,
    upsert,
)
from .entity_crud import delete_entity, get_entity, insert_entity, update_entity
from .errors import map_db_error
from .validation import sanitize_order_by, validate_identifier

__all__ = (
    # Types
    "FK",
    "FKMeta",
    "Vector",
    "VectorMeta",
    "extract_kron_db_meta",
    # DDL
    "generate_ddl",
    "get_fk_dependencies",
    # Connection
    "DbContext",
    "TenantContextRequired",
    "TenantScope",
    "close_pool",
    "connection",
    "get_db_context",
    "get_pool",
    "set_db_context",
    "transaction",
    "with_context",
    # CRUD (low-level)
    "count",
    "delete",
    "execute",
    "fetch",
    "fetchval",
    "insert",
    "select",
    "select_one",
    "update",
    "upsert",
    # CRUD (Entity-based)
    "delete_entity",
    "get_entity",
    "insert_entity",
    "update_entity",
    # Errors
    "map_db_error",
    # Validation
    "sanitize_order_by",
    "validate_identifier",
)
