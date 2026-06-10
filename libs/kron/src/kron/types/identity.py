"""Semantic UUID typing for type-safe entity identification.

Provides ID[T] syntax for associating UUIDs with specific model types,
enabling compile-time type checking and runtime semantic clarity.

Usage:
    from kron.types import ID

    user_id: ID[User] = uuid4()
    org_id: ID[Organization] = uuid4()

    # Type checker distinguishes these despite both being UUID at runtime
"""

from typing import Annotated
from uuid import UUID

__all__ = ("ID",)


class _IDMeta(type):
    """Metaclass enabling ID[T] syntax for semantic UUID typing.

    At runtime: ID[Model] returns Annotated[UUID, ("ID", Model)]
    For type checkers: Provides semantic distinction between UUID types.
    """

    def __getitem__(cls, item: type) -> type:
        return Annotated[UUID, ("ID", item)]


class ID(UUID, metaclass=_IDMeta):
    """Semantic UUID type with model association.

    ID[T] creates a type annotation that:
    - At runtime: Is equivalent to UUID
    - For type checkers: Associates the UUID with model type T

    This enables self-documenting code and catches type mismatches:

        class User(Node): ...
        class Tenant(Node): ...

        def get_user(user_id: ID[User]) -> User: ...
        def get_tenant(tenant_id: ID[Tenant]) -> Tenant: ...

        uid: ID[User] = uuid4()
        tid: ID[Tenant] = uuid4()

        get_user(uid)   # OK
        get_user(tid)   # Type error: expected ID[User], got ID[Tenant]
    """

    pass
