"""Tests for workflow visualization module.

Tests cover:
- Single-phase workflow (trivial case)
- Linear chain (A -> B -> C)
- Diamond DAG (A -> B, A -> C, B -> D, C -> D)
- Wide fan-out (A -> B, A -> C, A -> D)
- Status overlay from phase_statuses
- Layout positions (x/y correctness)
- Edge labels from PhaseRefNode conditions
- Grants and awaits metadata
- Error handling for unknown workflow
- Empty phases handling
"""

from __future__ import annotations

import pytest

from canon.dsl.compiler import compile_charter
from canon.runtime.visualization import (
    INITIAL_OFFSET_X,
    INITIAL_OFFSET_Y,
    LAYER_SPACING_X,
    NODE_SPACING_Y,
    GraphEdge,
    GraphNode,
    WorkflowGraph,
    build_workflow_graph,
)

# ---------------------------------------------------------------------------
# Charter source fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def single_phase_charter():
    """Charter with a single phase (no dependencies)."""
    return compile_charter("""\
charter "Single Phase" v1.0

workflow simple:
    phase start:
        action do_something()
""")


@pytest.fixture()
def linear_chain_charter():
    """Charter with a linear chain: init -> review -> decision."""
    return compile_charter("""\
charter "Linear Chain" v1.0

workflow pipeline:
    phase init:
        action gather_info()

    phase review:
        require init.passed
        action evaluate()

    phase decision:
        require review.passed
        action decide()
""")


@pytest.fixture()
def diamond_dag_charter():
    """Charter with a diamond DAG: start -> (left, right) -> merge."""
    return compile_charter("""\
charter "Diamond DAG" v1.0

workflow diamond:
    phase start:
        action begin()

    phase left_branch:
        require start.passed
        action process_left()

    phase right_branch:
        require start.passed
        action process_right()

    phase merge:
        require left_branch.passed
        require right_branch.passed
        action finalize()
""")


@pytest.fixture()
def fan_out_charter():
    """Charter with fan-out: root -> (a, b, c)."""
    return compile_charter("""\
charter "Fan Out" v1.0

workflow spread:
    phase root:
        action start()

    phase branch_a:
        require root.passed
        action do_a()

    phase branch_b:
        require root.passed
        action do_b()

    phase branch_c:
        require root.passed
        action do_c()
""")


@pytest.fixture()
def grants_and_awaits_charter():
    """Charter with grants, awaits, and multiple actions."""
    return compile_charter("""\
charter "Complex Phase" v1.0

triggers:
    external_event

workflow review:
    phase intake:
        action collect_data()
        action validate_input()

    phase approval:
        require intake.passed
        grants resume
        action approve()

    phase escalation:
        require intake.passed
        require await external_event
        action escalate()
""")


@pytest.fixture()
def multi_workflow_charter():
    """Charter with multiple workflows."""
    return compile_charter("""\
charter "Multi Workflow" v1.0

workflow first:
    phase step_one:
        action do_first()

    phase step_two:
        require step_one.passed
        action do_second()

workflow second:
    phase alpha:
        action do_alpha()

    phase beta:
        require alpha.passed
        action do_beta()

    phase gamma:
        require beta.passed
        action do_gamma()
""")


# ---------------------------------------------------------------------------
# Test: build_workflow_graph basics
# ---------------------------------------------------------------------------


class TestBuildWorkflowGraph:
    """Tests for the build_workflow_graph function."""

    def test_returns_workflow_graph(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        assert isinstance(graph, WorkflowGraph)
        assert graph.workflow_name == "simple"
        assert graph.charter_name == "Single Phase"

    def test_unknown_workflow_raises_value_error(self, single_phase_charter):
        with pytest.raises(ValueError, match="not found"):
            build_workflow_graph(single_phase_charter, "nonexistent")

    def test_nodes_are_frozen(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        assert isinstance(graph.nodes, tuple)
        for node in graph.nodes:
            assert isinstance(node, GraphNode)

    def test_edges_are_frozen(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        assert isinstance(graph.edges, tuple)
        for edge in graph.edges:
            assert isinstance(edge, GraphEdge)


# ---------------------------------------------------------------------------
# Test: single phase
# ---------------------------------------------------------------------------


class TestSinglePhase:
    """Tests for a workflow with a single phase."""

    def test_one_node(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        assert len(graph.nodes) == 1

    def test_no_edges(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        assert len(graph.edges) == 0

    def test_node_properties(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        node = graph.nodes[0]
        assert node.id == "start"
        assert node.phase_name == "start"
        assert node.label == "Start"
        assert node.status is None
        assert node.actions == ("do_something",)
        assert node.has_grants is False
        assert node.has_awaits is False

    def test_node_position_at_origin(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        node = graph.nodes[0]
        assert node.x == INITIAL_OFFSET_X
        assert node.y == INITIAL_OFFSET_Y


# ---------------------------------------------------------------------------
# Test: linear chain
# ---------------------------------------------------------------------------


class TestLinearChain:
    """Tests for a linear chain workflow (A -> B -> C)."""

    def test_three_nodes(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        assert len(graph.nodes) == 3

    def test_two_edges(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        assert len(graph.edges) == 2

    def test_edge_connections(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        edge_pairs = {(e.source, e.target) for e in graph.edges}
        assert ("init", "review") in edge_pairs
        assert ("review", "decision") in edge_pairs

    def test_edge_labels(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        for edge in graph.edges:
            assert edge.label == "passed"

    def test_layer_positions(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        node_map = {n.id: n for n in graph.nodes}

        # init at layer 0
        assert node_map["init"].x == INITIAL_OFFSET_X
        # review at layer 1
        assert node_map["review"].x == INITIAL_OFFSET_X + LAYER_SPACING_X
        # decision at layer 2
        assert node_map["decision"].x == INITIAL_OFFSET_X + 2 * LAYER_SPACING_X

    def test_all_at_same_y(self, linear_chain_charter):
        """All phases in a linear chain are alone in their layer."""
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        for node in graph.nodes:
            assert node.y == INITIAL_OFFSET_Y


# ---------------------------------------------------------------------------
# Test: diamond DAG
# ---------------------------------------------------------------------------


class TestDiamondDAG:
    """Tests for a diamond DAG workflow."""

    def test_four_nodes(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        assert len(graph.nodes) == 4

    def test_four_edges(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        assert len(graph.edges) == 4

    def test_edge_connections(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        edge_pairs = {(e.source, e.target) for e in graph.edges}
        assert ("start", "left_branch") in edge_pairs
        assert ("start", "right_branch") in edge_pairs
        assert ("left_branch", "merge") in edge_pairs
        assert ("right_branch", "merge") in edge_pairs

    def test_layer_depths(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        node_map = {n.id: n for n in graph.nodes}

        # start at layer 0
        assert node_map["start"].x == INITIAL_OFFSET_X
        # left and right at layer 1
        assert node_map["left_branch"].x == INITIAL_OFFSET_X + LAYER_SPACING_X
        assert node_map["right_branch"].x == INITIAL_OFFSET_X + LAYER_SPACING_X
        # merge at layer 2 (max of both predecessors + 1)
        assert node_map["merge"].x == INITIAL_OFFSET_X + 2 * LAYER_SPACING_X

    def test_parallel_phases_different_y(self, diamond_dag_charter):
        """Phases in the same layer should have different y positions."""
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        node_map = {n.id: n for n in graph.nodes}

        left_y = node_map["left_branch"].y
        right_y = node_map["right_branch"].y
        assert left_y != right_y

    def test_parallel_phases_y_spacing(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        node_map = {n.id: n for n in graph.nodes}

        left_y = node_map["left_branch"].y
        right_y = node_map["right_branch"].y
        assert abs(left_y - right_y) == NODE_SPACING_Y


# ---------------------------------------------------------------------------
# Test: fan-out
# ---------------------------------------------------------------------------


class TestFanOut:
    """Tests for fan-out workflow (root -> a, b, c)."""

    def test_four_nodes(self, fan_out_charter):
        graph = build_workflow_graph(fan_out_charter, "spread")
        assert len(graph.nodes) == 4

    def test_three_edges(self, fan_out_charter):
        graph = build_workflow_graph(fan_out_charter, "spread")
        assert len(graph.edges) == 3

    def test_all_edges_from_root(self, fan_out_charter):
        graph = build_workflow_graph(fan_out_charter, "spread")
        for edge in graph.edges:
            assert edge.source == "root"

    def test_branches_at_same_layer(self, fan_out_charter):
        graph = build_workflow_graph(fan_out_charter, "spread")
        node_map = {n.id: n for n in graph.nodes}

        expected_x = INITIAL_OFFSET_X + LAYER_SPACING_X
        assert node_map["branch_a"].x == expected_x
        assert node_map["branch_b"].x == expected_x
        assert node_map["branch_c"].x == expected_x

    def test_branches_spaced_vertically(self, fan_out_charter):
        graph = build_workflow_graph(fan_out_charter, "spread")
        node_map = {n.id: n for n in graph.nodes}

        ys = sorted(
            [
                node_map["branch_a"].y,
                node_map["branch_b"].y,
                node_map["branch_c"].y,
            ]
        )
        # Should be evenly spaced
        assert ys[1] - ys[0] == NODE_SPACING_Y
        assert ys[2] - ys[1] == NODE_SPACING_Y


# ---------------------------------------------------------------------------
# Test: status overlay
# ---------------------------------------------------------------------------


class TestStatusOverlay:
    """Tests for overlaying phase execution statuses."""

    def test_no_statuses_returns_none(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        for node in graph.nodes:
            assert node.status is None

    def test_partial_statuses(self, linear_chain_charter):
        statuses = {"init": "completed", "review": "waiting_user"}
        graph = build_workflow_graph(linear_chain_charter, "pipeline", phase_statuses=statuses)
        node_map = {n.id: n for n in graph.nodes}

        assert node_map["init"].status == "completed"
        assert node_map["review"].status == "waiting_user"
        assert node_map["decision"].status is None

    def test_all_statuses(self, linear_chain_charter):
        statuses = {
            "init": "completed",
            "review": "completed",
            "decision": "waiting_user",
        }
        graph = build_workflow_graph(linear_chain_charter, "pipeline", phase_statuses=statuses)
        node_map = {n.id: n for n in graph.nodes}

        assert node_map["init"].status == "completed"
        assert node_map["review"].status == "completed"
        assert node_map["decision"].status == "waiting_user"

    def test_unknown_phase_status_ignored(self, linear_chain_charter):
        """Statuses for phases that don't exist are silently ignored."""
        statuses = {"init": "completed", "nonexistent": "failed"}
        graph = build_workflow_graph(linear_chain_charter, "pipeline", phase_statuses=statuses)
        node_map = {n.id: n for n in graph.nodes}
        assert node_map["init"].status == "completed"


# ---------------------------------------------------------------------------
# Test: grants and awaits metadata
# ---------------------------------------------------------------------------


class TestGrantsAndAwaits:
    """Tests for grants and awaits metadata on nodes."""

    def test_phase_with_grants(self, grants_and_awaits_charter):
        graph = build_workflow_graph(grants_and_awaits_charter, "review")
        node_map = {n.id: n for n in graph.nodes}

        assert node_map["approval"].has_grants is True
        assert node_map["intake"].has_grants is False
        assert node_map["escalation"].has_grants is False

    def test_phase_with_require_await(self, grants_and_awaits_charter):
        graph = build_workflow_graph(grants_and_awaits_charter, "review")
        node_map = {n.id: n for n in graph.nodes}

        # escalation has `require await external_event`
        assert node_map["escalation"].has_awaits is True
        assert node_map["intake"].has_awaits is False
        assert node_map["approval"].has_awaits is False

    def test_multiple_actions(self, grants_and_awaits_charter):
        graph = build_workflow_graph(grants_and_awaits_charter, "review")
        node_map = {n.id: n for n in graph.nodes}

        assert node_map["intake"].actions == ("collect_data", "validate_input")
        assert node_map["approval"].actions == ("approve",)


# ---------------------------------------------------------------------------
# Test: node label formatting
# ---------------------------------------------------------------------------


class TestNodeLabels:
    """Tests for human-readable label formatting."""

    def test_single_word(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        assert graph.nodes[0].label == "Start"

    def test_underscore_to_title_case(self, diamond_dag_charter):
        graph = build_workflow_graph(diamond_dag_charter, "diamond")
        node_map = {n.id: n for n in graph.nodes}
        assert node_map["left_branch"].label == "Left Branch"
        assert node_map["right_branch"].label == "Right Branch"


# ---------------------------------------------------------------------------
# Test: multi-workflow charter
# ---------------------------------------------------------------------------


class TestMultiWorkflow:
    """Tests for charters with multiple workflows."""

    def test_select_first_workflow(self, multi_workflow_charter):
        graph = build_workflow_graph(multi_workflow_charter, "first")
        assert graph.workflow_name == "first"
        assert len(graph.nodes) == 2

    def test_select_second_workflow(self, multi_workflow_charter):
        graph = build_workflow_graph(multi_workflow_charter, "second")
        assert graph.workflow_name == "second"
        assert len(graph.nodes) == 3

    def test_workflows_independent(self, multi_workflow_charter):
        first = build_workflow_graph(multi_workflow_charter, "first")
        second = build_workflow_graph(multi_workflow_charter, "second")

        first_ids = {n.id for n in first.nodes}
        second_ids = {n.id for n in second.nodes}
        assert first_ids & second_ids == set()  # No overlap


# ---------------------------------------------------------------------------
# Test: dataclass immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    """Tests that graph dataclasses are truly frozen."""

    def test_graph_node_frozen(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        with pytest.raises(AttributeError):
            graph.nodes[0].status = "completed"

    def test_graph_edge_frozen(self, linear_chain_charter):
        graph = build_workflow_graph(linear_chain_charter, "pipeline")
        with pytest.raises(AttributeError):
            graph.edges[0].label = "changed"

    def test_workflow_graph_frozen(self, single_phase_charter):
        graph = build_workflow_graph(single_phase_charter, "simple")
        with pytest.raises(AttributeError):
            graph.workflow_name = "changed"


# ---------------------------------------------------------------------------
# Test: edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_phase_with_no_actions(self):
        """A phase with only a require (no actions) should still work."""
        compiled = compile_charter("""\
charter "No Actions" v1.0

workflow w:
    phase entry:
        action start()

    phase gate:
        require entry.passed
""")
        graph = build_workflow_graph(compiled, "w")
        assert len(graph.nodes) == 2
        node_map = {n.id: n for n in graph.nodes}
        assert node_map["gate"].actions == ()

    def test_complete_condition(self):
        """Edges with .complete condition should have correct label."""
        compiled = compile_charter("""\
charter "Complete Condition" v1.0

workflow w:
    phase first:
        action do_first()

    phase second:
        require first.complete
        action do_second()
""")
        graph = build_workflow_graph(compiled, "w")
        assert graph.edges[0].label == "complete"

    def test_empty_phase_statuses_dict(self, linear_chain_charter):
        """Passing an empty dict should result in all None statuses."""
        graph = build_workflow_graph(linear_chain_charter, "pipeline", phase_statuses={})
        for node in graph.nodes:
            assert node.status is None
