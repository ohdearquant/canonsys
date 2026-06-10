"""Tests for DataOrchestrator graph algorithms: cycle detection and topological sort.

Tests cover:
- _detect_cycle: Cycle detection in data source dependencies
- _topological_sort: Topological ordering of data sources
- DataPlan.from_specs: Plan creation with cycle checking
- DataSourceSpec.from_dict: Parsing with requires field

See test_orchestrator.py for DataOrchestrator execution tests.
"""

from __future__ import annotations

import pytest

from canon.exceptions import DataSourceCycleError
from canon.utils.opa.orchestrator import (
    DataPlan,
    DataSourceSpec,
    DataSourceType,
    _detect_cycle,
    _topological_sort,
)


class TestCycleDetection:
    """Tests for cycle detection in data source dependencies."""

    def test_no_cycle_simple(self):
        """No dependencies means no cycle."""
        specs = [
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
            DataSourceSpec(id="b", type=DataSourceType.CONSTANT, required=True, into="facts.b"),
        ]
        assert _detect_cycle(specs) is None

    def test_no_cycle_linear(self):
        """Linear dependency chain: a -> b -> c."""
        specs = [
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
            DataSourceSpec(
                id="c",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.c",
                requires=("b",),
            ),
        ]
        assert _detect_cycle(specs) is None

    def test_no_cycle_diamond(self):
        """Diamond dependency: a -> b,c -> d (no cycle)."""
        specs = [
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
            DataSourceSpec(
                id="c",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.c",
                requires=("a",),
            ),
            DataSourceSpec(
                id="d",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.d",
                requires=("b", "c"),
            ),
        ]
        assert _detect_cycle(specs) is None

    def test_cycle_self_reference(self):
        """Self-referential dependency: a -> a."""
        specs = [
            DataSourceSpec(
                id="a",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.a",
                requires=("a",),
            ),
        ]
        cycle = _detect_cycle(specs)
        assert cycle is not None
        assert "a" in cycle

    def test_cycle_two_nodes(self):
        """Two-node cycle: a -> b -> a."""
        specs = [
            DataSourceSpec(
                id="a",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.a",
                requires=("b",),
            ),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
        ]
        cycle = _detect_cycle(specs)
        assert cycle is not None
        assert "a" in cycle and "b" in cycle

    def test_cycle_three_nodes(self):
        """Three-node cycle: a -> b -> c -> a."""
        specs = [
            DataSourceSpec(
                id="a",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.a",
                requires=("c",),
            ),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
            DataSourceSpec(
                id="c",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.c",
                requires=("b",),
            ),
        ]
        cycle = _detect_cycle(specs)
        assert cycle is not None
        # All three should be in the cycle
        assert len(set(cycle) & {"a", "b", "c"}) >= 2

    def test_external_dependency_ignored(self):
        """Dependencies on IDs not in specs are ignored."""
        specs = [
            DataSourceSpec(
                id="a",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.a",
                requires=("external_id",),
            ),
        ]
        # "external_id" not in specs, so no cycle possible
        assert _detect_cycle(specs) is None


class TestTopologicalSort:
    """Tests for topological sorting of data sources."""

    def test_empty_list(self):
        """Empty list returns empty."""
        assert _topological_sort([]) == []

    def test_no_dependencies(self):
        """No dependencies - order preserved or any valid order."""
        specs = [
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
            DataSourceSpec(id="b", type=DataSourceType.CONSTANT, required=True, into="facts.b"),
        ]
        result = _topological_sort(specs)
        assert len(result) == 2
        assert {s.id for s in result} == {"a", "b"}

    def test_linear_dependencies(self):
        """Linear chain: a -> b -> c must return a, b, c."""
        specs = [
            DataSourceSpec(
                id="c",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.c",
                requires=("b",),
            ),
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
        ]
        result = _topological_sort(specs)
        ids = [s.id for s in result]
        # a must come before b, b must come before c
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_diamond_dependencies(self):
        """Diamond: a -> b,c -> d."""
        specs = [
            DataSourceSpec(
                id="d",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.d",
                requires=("b", "c"),
            ),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
            DataSourceSpec(
                id="c",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.c",
                requires=("a",),
            ),
            DataSourceSpec(id="a", type=DataSourceType.CONSTANT, required=True, into="facts.a"),
        ]
        result = _topological_sort(specs)
        ids = [s.id for s in result]
        # a must come first, d must come last
        assert ids[0] == "a"
        assert ids[-1] == "d"
        # b and c must come before d
        assert ids.index("b") < ids.index("d")
        assert ids.index("c") < ids.index("d")


class TestDataPlanFromSpecs:
    """Tests for DataPlan.from_specs with cycle detection."""

    def test_raises_on_cycle(self):
        """from_specs raises DataSourceCycleError on cycle."""
        specs = [
            DataSourceSpec(
                id="a",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.a",
                requires=("b",),
            ),
            DataSourceSpec(
                id="b",
                type=DataSourceType.DERIVED,
                required=True,
                into="facts.b",
                requires=("a",),
            ),
        ]
        with pytest.raises(DataSourceCycleError) as exc_info:
            DataPlan.from_specs(specs)
        assert "a" in exc_info.value.cycle or "b" in exc_info.value.cycle

    def test_separates_base_and_derived(self):
        """Base and derived sources are separated into waves."""
        specs = [
            DataSourceSpec(
                id="const1",
                type=DataSourceType.CONSTANT,
                required=True,
                into="facts.c1",
            ),
            DataSourceSpec(
                id="evidence1",
                type=DataSourceType.EVIDENCE,
                required=True,
                into="evidence.e1",
            ),
            DataSourceSpec(
                id="derived1",
                type=DataSourceType.DERIVED,
                required=True,
                into="derived.d1",
                requires=("const1",),
            ),
        ]
        plan = DataPlan.from_specs(specs)
        assert len(plan.base_sources) == 2
        assert len(plan.derived_sources) == 1
        assert all(s.type != DataSourceType.DERIVED for s in plan.base_sources)
        assert all(s.type == DataSourceType.DERIVED for s in plan.derived_sources)

    def test_sorts_within_waves(self):
        """Sources within each wave are topologically sorted."""
        specs = [
            DataSourceSpec(
                id="d2",
                type=DataSourceType.DERIVED,
                required=True,
                into="derived.d2",
                requires=("d1",),
            ),
            DataSourceSpec(id="d1", type=DataSourceType.DERIVED, required=True, into="derived.d1"),
            DataSourceSpec(
                id="b2",
                type=DataSourceType.CONSTANT,
                required=True,
                into="facts.b2",
                requires=("b1",),
            ),
            DataSourceSpec(id="b1", type=DataSourceType.CONSTANT, required=True, into="facts.b1"),
        ]
        plan = DataPlan.from_specs(specs)

        base_ids = [s.id for s in plan.base_sources]
        derived_ids = [s.id for s in plan.derived_sources]

        # b1 must come before b2
        assert base_ids.index("b1") < base_ids.index("b2")
        # d1 must come before d2
        assert derived_ids.index("d1") < derived_ids.index("d2")


class TestDataSourceSpecFromDict:
    """Tests for DataSourceSpec.from_dict parsing."""

    def test_parses_requires_field(self):
        """requires field is parsed into tuple."""
        data = {
            "id": "test",
            "type": "derived",
            "into": "derived.test",
            "requires": ["dep1", "dep2"],
        }
        spec = DataSourceSpec.from_dict(data)
        assert spec.requires == ("dep1", "dep2")

    def test_requires_defaults_to_empty(self):
        """Missing requires defaults to empty tuple."""
        data = {
            "id": "test",
            "type": "constant",
            "into": "facts.test",
        }
        spec = DataSourceSpec.from_dict(data)
        assert spec.requires == ()

    def test_requires_excluded_from_spec_dict(self):
        """requires field is not duplicated in spec dict."""
        data = {
            "id": "test",
            "type": "derived",
            "into": "derived.test",
            "requires": ["dep1"],
            "fn": "compute_something",
        }
        spec = DataSourceSpec.from_dict(data)
        assert "requires" not in spec.spec
        assert spec.spec.get("fn") == "compute_something"
