"""Kron - absorbed from krons for canon self-containment.

This module contains types, utilities, and patterns absorbed from the krons
library to make canon self-contained and independent of external dependencies.

Submodules:
    - core: Element, Node, Progression, Pile, Flow (persistable entities)
    - types: Base types (FK, ID, Enum, HashableModel, DataClass, sentinels)
    - specs: Framework-agnostic field specifications (Spec, Operable, Phrase)
    - utils: Hash utilities, time utilities, SQL validation, concurrency
    - protocols: Runtime-checkable protocols (Serializable, Observable, etc.)
    - errors: Exception hierarchy (KronError, KronConnectionError, etc.)
    - services: Service backends (Endpoint, iModel, hooks, ServiceRegistry)
    - operations: Operation factory registry
    - session: Session, Branch, Message, Exchange (conversation orchestration)
"""

from . import (
    core,
    errors,
    operations,
    protocols,
    services,
    session,
    specs,
    types,
    utils,
)

__all__ = (
    "core",
    "errors",
    "operations",
    "protocols",
    "services",
    "session",
    "specs",
    "types",
    "utils",
)
