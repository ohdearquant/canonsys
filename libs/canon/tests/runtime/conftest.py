"""Shared fixtures for charter runtime tests."""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from canon.dsl.ast import (
    ActionNode,
    CharterNode,
    FeatureCallNode,
    GrantNode,
    PhaseNode,
    PhaseRefNode,
    RequireNode,
    RoleNode,
    SchemaRefNode,
    WorkflowNode,
)
from canon.dsl.compiler import CompiledCharter

# ---------------------------------------------------------------------------
# Fixed UUIDs for deterministic tests
# ---------------------------------------------------------------------------
TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
CHARTER_ID = UUID("00000000-0000-0000-0000-000000000010")
RUN_ID = UUID("00000000-0000-0000-0000-000000000100")
USER_ID = UUID("00000000-0000-0000-0000-000000001000")
SUBJECT_ID = UUID("00000000-0000-0000-0000-000000010000")
OFFER_ID = UUID("00000000-0000-0000-0000-000000100000")


# ---------------------------------------------------------------------------
# Charter AST fixtures
# ---------------------------------------------------------------------------


def _make_phase(
    name: str,
    requires: tuple[RequireNode, ...] = (),
    actions: tuple[ActionNode, ...] = (),
    grants: tuple[GrantNode, ...] = (),
) -> PhaseNode:
    """Helper to create a PhaseNode with sensible defaults."""
    if not actions:
        actions = (ActionNode(call=FeatureCallNode(name=f"do_{name}", args=())),)
    return PhaseNode(
        name=name,
        requires=requires,
        actions=actions,
        outputs=(),
        grants=grants,
    )


def _make_require_phase(phase_name: str, condition: str = "passed") -> RequireNode:
    """Helper to create a RequireNode referencing another phase."""
    return RequireNode(ref=PhaseRefNode(phase=phase_name, condition=condition))


@pytest.fixture
def three_phase_compiled() -> CompiledCharter:
    """A compiled charter with 3 phases in a linear chain:
    initiation -> hm_approval -> ceo_approval

    hm_approval requires initiation.passed
    ceo_approval requires hm_approval.passed
    """
    initiation = _make_phase("initiation")
    hm_approval = _make_phase(
        "hm_approval",
        requires=(_make_require_phase("initiation"),),
        grants=(GrantNode(document_type="resume"),),
    )
    ceo_approval = _make_phase(
        "ceo_approval",
        requires=(_make_require_phase("hm_approval"),),
    )

    workflow = WorkflowNode(
        name="approval_workflow",
        phases=(initiation, hm_approval, ceo_approval),
    )

    charter_ast = CharterNode(
        name="Test Approval Charter",
        version="v1.0",
        schemas=(SchemaRefNode(namespace="canon.hr", version="2026.01"),),
        packages=(),
        policies=(),
        triggers=(),
        workflows=(workflow,),
        situations=(),
        roles=(
            RoleNode(
                name="hiring_manager",
                actions=("do_initiation", "do_hm_approval"),
                requires_mfa=False,
                break_glass=False,
            ),
            RoleNode(
                name="ceo",
                actions=("do_ceo_approval",),
                requires_mfa=False,
                break_glass=False,
            ),
        ),
    )

    return CompiledCharter(
        name="Test Approval Charter",
        version="v1.0",
        ast=charter_ast,
        feature_names=frozenset({"do_initiation", "do_hm_approval", "do_ceo_approval"}),
        schema_types=MappingProxyType({}),
        phase_order=MappingProxyType(
            {
                "approval_workflow": ("initiation", "hm_approval", "ceo_approval"),
            }
        ),
        policy_ids=frozenset(),
        package_names=frozenset(),
        situations=(),
        roles=charter_ast.roles,
    )


@pytest.fixture
def diamond_compiled() -> CompiledCharter:
    """A compiled charter with diamond dependency:
    initiation -> [review_a, review_b] -> final

    review_a and review_b both require initiation.passed
    final requires both review_a.passed AND review_b.passed
    """
    initiation = _make_phase("initiation")
    review_a = _make_phase(
        "review_a",
        requires=(_make_require_phase("initiation"),),
    )
    review_b = _make_phase(
        "review_b",
        requires=(_make_require_phase("initiation"),),
    )
    final = _make_phase(
        "final",
        requires=(
            _make_require_phase("review_a"),
            _make_require_phase("review_b"),
        ),
    )

    workflow = WorkflowNode(
        name="diamond_workflow",
        phases=(initiation, review_a, review_b, final),
    )

    charter_ast = CharterNode(
        name="Diamond Charter",
        version="v1.0",
        schemas=(SchemaRefNode(namespace="canon.hr", version="2026.01"),),
        packages=(),
        policies=(),
        triggers=(),
        workflows=(workflow,),
        situations=(),
        roles=(),
    )

    return CompiledCharter(
        name="Diamond Charter",
        version="v1.0",
        ast=charter_ast,
        feature_names=frozenset({"do_initiation", "do_review_a", "do_review_b", "do_final"}),
        schema_types=MappingProxyType({}),
        phase_order=MappingProxyType(
            {
                "diamond_workflow": ("initiation", "review_a", "review_b", "final"),
            }
        ),
        policy_ids=frozenset(),
        package_names=frozenset(),
        situations=(),
        roles=(),
    )


# ---------------------------------------------------------------------------
# Mock DB connection
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_conn() -> AsyncMock:
    """A mock asyncpg connection.

    Callers should configure return values per-test:
        mock_conn.fetchrow.return_value = {...}
        mock_conn.fetch.return_value = [...]
        mock_conn.fetchval.return_value = 0
        mock_conn.execute.return_value = "UPDATE 1"
    """
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    return conn
