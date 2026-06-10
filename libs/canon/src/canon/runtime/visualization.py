"""Workflow visualization for Charter Runtime.

Generates graph representations of charter workflows for UI rendering.
Extracts phase nodes, dependency edges, and current execution status
from compiled charters and optional runtime state.

The graph uses a layered layout algorithm based on topological depth:
- Entry phases (no requires) are placed at layer 0
- Each downstream phase is placed at max(layer of predecessors) + 1
- Within a layer, phases are spaced vertically

Usage:
    from canon.runtime.visualization import build_workflow_graph

    # Pure AST-based graph (no runtime state)
    graph = build_workflow_graph(compiled, "approval_workflow")

    # With runtime status overlay
    graph = build_workflow_graph(
        compiled,
        "approval_workflow",
        phase_statuses={"initiation": "completed", "hm_approval": "waiting_user"},
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from canon.dsl.ast import AwaitRefNode, PhaseRefNode

if TYPE_CHECKING:
    import asyncpg

    from canon.dsl.compiler import CompiledCharter

__all__ = (
    "GraphEdge",
    "GraphNode",
    "WorkflowGraph",
    "build_workflow_graph",
    "get_workflow_graph",
)

# Layout constants (pixels)
LAYER_SPACING_X = 250.0
NODE_SPACING_Y = 120.0
INITIAL_OFFSET_X = 50.0
INITIAL_OFFSET_Y = 50.0


@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node in the workflow graph representing a phase.

    Attributes:
        id: Unique identifier (phase name).
        label: Human-readable display name (title-cased).
        phase_name: Original phase name from the charter.
        status: Current execution status (None if no runtime state).
        x: Horizontal position for layout (pixels from left).
        y: Vertical position for layout (pixels from top).
        actions: Names of actions declared in this phase.
        has_grants: Whether this phase has document access grants.
        has_awaits: Whether this phase has await directives.
    """

    id: str
    label: str
    phase_name: str
    status: str | None
    x: float
    y: float
    actions: tuple[str, ...]
    has_grants: bool
    has_awaits: bool


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """An edge in the workflow graph representing a dependency.

    Attributes:
        source: Source phase name (the dependency).
        target: Target phase name (the dependent).
        label: Edge label describing the condition (e.g., "passed").
    """

    source: str
    target: str
    label: str


@dataclass(frozen=True, slots=True)
class WorkflowGraph:
    """Complete workflow graph for visualization.

    Contains all nodes and edges needed to render a workflow DAG,
    along with metadata about the charter.

    Attributes:
        workflow_name: Name of the workflow.
        charter_name: Name of the charter this workflow belongs to.
        nodes: All phase nodes with positions and metadata.
        edges: All dependency edges between phases.
    """

    workflow_name: str
    charter_name: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]


def _find_workflow(compiled: CompiledCharter, workflow_name: str):
    """Find a workflow AST node by name.

    Args:
        compiled: CompiledCharter to search.
        workflow_name: Workflow name to find.

    Returns:
        WorkflowNode if found, None otherwise.
    """
    for wf in compiled.ast.workflows:
        if wf.name == workflow_name:
            return wf
    return None


def _compute_layer_depths(
    compiled: CompiledCharter,
    workflow_name: str,
) -> dict[str, int]:
    """Compute the topological layer depth for each phase.

    Entry phases (no phase-ref requires) get depth 0. Each downstream
    phase gets max(depth of all phase-ref predecessors) + 1.

    Uses the topological order from CompiledCharter.phase_order to
    process phases in dependency order.

    Args:
        compiled: CompiledCharter with phase_order.
        workflow_name: Workflow to analyze.

    Returns:
        Mapping of phase_name -> layer depth (0-based).
    """
    workflow = _find_workflow(compiled, workflow_name)
    if not workflow:
        return {}

    # Extract phase-ref dependencies for each phase
    phase_deps: dict[str, list[str]] = {}
    for phase in workflow.phases:
        deps = []
        for req in phase.requires:
            if isinstance(req.ref, PhaseRefNode):
                deps.append(req.ref.phase)
        phase_deps[phase.name] = deps

    # Compute depths using topological order
    depths: dict[str, int] = {}
    topo_order = compiled.phase_order.get(workflow_name, ())

    for phase_name in topo_order:
        deps = phase_deps.get(phase_name, [])
        if not deps:
            depths[phase_name] = 0
        else:
            max_dep_depth = max(depths.get(d, 0) for d in deps)
            depths[phase_name] = max_dep_depth + 1

    return depths


def build_workflow_graph(
    compiled: CompiledCharter,
    workflow_name: str,
    phase_statuses: dict[str, str] | None = None,
) -> WorkflowGraph:
    """Build a visualization graph from a compiled charter.

    Extracts phases as nodes with layered positions, and require
    dependencies as edges. Optionally overlays execution status
    from a phase_statuses dict.

    Layout uses a simple left-to-right layered approach:
    - x position determined by topological depth
    - y position determined by index within each layer

    Args:
        compiled: CompiledCharter with workflow definitions.
        workflow_name: Name of workflow to visualize.
        phase_statuses: Optional mapping of phase_name -> status string.

    Returns:
        WorkflowGraph with nodes and edges ready for rendering.

    Raises:
        ValueError: If workflow_name is not found in the charter.
    """
    workflow = _find_workflow(compiled, workflow_name)
    if not workflow:
        raise ValueError(f"Workflow '{workflow_name}' not found in charter '{compiled.name}'")

    if phase_statuses is None:
        phase_statuses = {}

    # Compute layer depths
    depths = _compute_layer_depths(compiled, workflow_name)

    # Group phases by layer for vertical spacing
    layers: dict[int, list[str]] = {}
    for phase_name, depth in depths.items():
        layers.setdefault(depth, []).append(phase_name)

    # Preserve topological order within each layer
    topo_order = compiled.phase_order.get(workflow_name, ())
    topo_index = {name: i for i, name in enumerate(topo_order)}
    for depth in layers:
        layers[depth].sort(key=lambda n: topo_index.get(n, 0))

    # Build phase lookup
    phase_map = {p.name: p for p in workflow.phases}

    # Build nodes with positions
    nodes: list[GraphNode] = []
    for depth, phase_names in sorted(layers.items()):
        for idx, phase_name in enumerate(phase_names):
            phase = phase_map.get(phase_name)
            if not phase:
                continue

            x = INITIAL_OFFSET_X + depth * LAYER_SPACING_X
            y = INITIAL_OFFSET_Y + idx * NODE_SPACING_Y

            # Extract action names
            actions = tuple(a.call.name for a in phase.actions)

            # Check for grants and awaits
            has_grants = len(phase.grants) > 0
            has_awaits = len(phase.awaits) > 0 or any(
                isinstance(req.ref, AwaitRefNode) for req in phase.requires
            )

            # Title-case the phase name for display
            label = phase_name.replace("_", " ").title()

            nodes.append(
                GraphNode(
                    id=phase_name,
                    label=label,
                    phase_name=phase_name,
                    status=phase_statuses.get(phase_name),
                    x=x,
                    y=y,
                    actions=actions,
                    has_grants=has_grants,
                    has_awaits=has_awaits,
                )
            )

    # Build edges from require clauses
    edges: list[GraphEdge] = []
    for phase in workflow.phases:
        for req in phase.requires:
            if isinstance(req.ref, PhaseRefNode):
                edges.append(
                    GraphEdge(
                        source=req.ref.phase,
                        target=phase.name,
                        label=req.ref.condition,
                    )
                )

    return WorkflowGraph(
        workflow_name=workflow_name,
        charter_name=compiled.name,
        nodes=tuple(nodes),
        edges=tuple(edges),
    )


async def get_workflow_graph(
    *,
    run_id: UUID,
    conn: asyncpg.Connection,
) -> WorkflowGraph:
    """Get workflow graph with current execution status for a run.

    Loads the CharterRun, compiles the charter, queries phase execution
    statuses, and builds the graph with status overlay.

    Args:
        run_id: UUID of the CharterRun to visualize.
        conn: Database connection.

    Returns:
        WorkflowGraph with nodes annotated with current status.

    Raises:
        ValueError: If run not found.
        CharterNotFoundError: If charter not found.
    """
    from .registry import get_compiled_charter

    # 1. Load the CharterRun
    run_row = await conn.fetchrow(
        """
        SELECT id, charter_id, current_workflow
        FROM charter_runs
        WHERE id = $1
        """,
        run_id,
    )

    if not run_row:
        raise ValueError(f"CharterRun not found: {run_id}")

    charter_id = run_row["charter_id"]
    workflow_name = run_row["current_workflow"]

    if not workflow_name:
        raise ValueError(f"CharterRun {run_id} has no current workflow")

    # 2. Compile the charter
    compiled = await get_compiled_charter(charter_id, conn)

    # 3. Query phase execution statuses
    phase_rows = await conn.fetch(
        """
        SELECT phase_name, status
        FROM phase_executions
        WHERE run_id = $1
        ORDER BY sequence
        """,
        run_id,
    )

    phase_statuses = {row["phase_name"]: row["status"] for row in phase_rows}

    # 4. Build graph with status overlay
    return build_workflow_graph(compiled, workflow_name, phase_statuses)
