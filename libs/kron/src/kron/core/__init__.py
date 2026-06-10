"""Core kron components: Element, Node, Event, Graph, Progression, Pile, Flow.

Element: Base class with UUID identity, timestamps, and polymorphic serialization.
Node: Persistable element with structured content, audit trail, and DDL generation.
Event: Async executable with lifecycle tracking and execution state.
Graph: Directed graph with adjacency-based operations.
Progression: Ordered UUID sequence with O(1) membership.
Pile: Thread-safe typed collection with rich query interface.
Flow: Workflow state container with items and named progressions.
"""

from .element import LN_ELEMENT_FIELDS, Element
from .event import Event, EventStatus, Execution
from .flow import Flow
from .graph import Edge, EdgeCondition, Graph
from .node import (
    NODE_REGISTRY,
    PERSISTABLE_NODE_REGISTRY,
    Node,
    NodeConfig,
    _register_persistable,
    create_node,
    generate_all_ddl,
    generate_ddl,
    get_fk_dependencies,
)
from .pile import Pile
from .progression import Progression

__all__ = (
    # Element
    "Element",
    "LN_ELEMENT_FIELDS",
    # Node
    "Node",
    "NodeConfig",
    "NODE_REGISTRY",
    "PERSISTABLE_NODE_REGISTRY",
    "_register_persistable",
    # Event
    "Event",
    "EventStatus",
    "Execution",
    # Graph
    "Edge",
    "EdgeCondition",
    "Graph",
    # Progression
    "Progression",
    # Pile
    "Pile",
    # Flow
    "Flow",
    # Factory & DDL
    "create_node",
    "generate_ddl",
    "generate_all_ddl",
    "get_fk_dependencies",
)
