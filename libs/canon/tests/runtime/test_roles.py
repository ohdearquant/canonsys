"""Tests for role enforcement in Charter Runtime.

Tests MFA and break_glass enforcement as defined by RoleNode
in compiled charters.
"""

from __future__ import annotations

from types import MappingProxyType
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from canon.dsl.ast import (
    ActionNode,
    CharterNode,
    FeatureCallNode,
    PhaseNode,
    RoleNode,
    WorkflowNode,
)
from canon.dsl.compiler import CompiledCharter
from canon.runtime.roles import (
    BreakGlassRequiredError,
    MFARequiredError,
    RoleCheckResult,
    _check_break_glass_active,
    _check_mfa_verified,
    enforce_role_requirements,
    find_role_for_phase,
    verify_role_requirements,
)

# ---------------------------------------------------------------------------
# Helpers to build compiled charter fixtures
# ---------------------------------------------------------------------------


def _make_action(name: str) -> ActionNode:
    return ActionNode(call=FeatureCallNode(name=name, args=()))


def _make_phase(name: str, actions: list[str]) -> PhaseNode:
    return PhaseNode(
        name=name,
        requires=(),
        actions=tuple(_make_action(a) for a in actions),
        outputs=(),
    )


def _make_compiled(
    phases: list[PhaseNode],
    roles: list[RoleNode],
    workflow_name: str = "w",
) -> CompiledCharter:
    workflow = WorkflowNode(name=workflow_name, phases=tuple(phases))
    ast = CharterNode(
        name="Test",
        version="v1",
        workflows=(workflow,),
        roles=tuple(roles),
    )
    return CompiledCharter(
        name="Test",
        version="v1",
        ast=ast,
        feature_names=frozenset(),
        schema_types=MappingProxyType({}),
        phase_order=MappingProxyType({workflow_name: tuple(p.name for p in phases)}),
        policy_ids=frozenset(),
        package_names=frozenset(),
        situations=(),
        roles=tuple(roles),
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def hr_role() -> RoleNode:
    """HR manager role - requires MFA, no break_glass."""
    return RoleNode(
        name="hr_manager",
        actions=("assess_eligibility", "evaluate_performance"),
        break_glass=False,
        requires_mfa=True,
    )


@pytest.fixture()
def legal_role() -> RoleNode:
    """Legal counsel role - requires both MFA and break_glass."""
    return RoleNode(
        name="legal_counsel",
        actions=("certify_termination",),
        break_glass=True,
        requires_mfa=True,
    )


@pytest.fixture()
def viewer_role() -> RoleNode:
    """Viewer role - no MFA, no break_glass."""
    return RoleNode(
        name="viewer",
        actions=("view_report",),
        break_glass=False,
        requires_mfa=False,
    )


@pytest.fixture()
def sample_compiled(hr_role, legal_role) -> CompiledCharter:
    """Compiled charter with two phases governed by different roles."""
    phases = [
        _make_phase("eligibility", ["assess_eligibility"]),
        _make_phase("decision", ["certify_termination"]),
        _make_phase("notification", ["send_notification"]),  # No role
    ]
    return _make_compiled(phases, [hr_role, legal_role])


@pytest.fixture()
def user_id():
    return uuid4()


@pytest.fixture()
def mock_conn():
    """Mock asyncpg connection."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# RoleCheckResult
# ---------------------------------------------------------------------------


class TestRoleCheckResult:
    def test_allowed_result(self):
        result = RoleCheckResult(
            allowed=True,
            role_name="hr_manager",
            requires_mfa=True,
            requires_break_glass=False,
            mfa_verified=True,
            break_glass_active=False,
        )
        assert result.allowed is True
        assert result.reason is None

    def test_denied_result_with_reason(self):
        result = RoleCheckResult(
            allowed=False,
            role_name="legal_counsel",
            requires_mfa=True,
            requires_break_glass=True,
            mfa_verified=False,
            break_glass_active=False,
            reason="MFA required",
        )
        assert result.allowed is False
        assert result.reason == "MFA required"

    def test_to_dict(self):
        result = RoleCheckResult(
            allowed=True,
            role_name="hr_manager",
            requires_mfa=True,
            requires_break_glass=False,
            mfa_verified=True,
            break_glass_active=False,
        )
        d = result.to_dict()
        assert d["allowed"] is True
        assert d["role_name"] == "hr_manager"
        assert d["requires_mfa"] is True
        assert d["requires_break_glass"] is False
        assert d["mfa_verified"] is True
        assert d["break_glass_active"] is False
        assert d["reason"] is None

    def test_frozen(self):
        result = RoleCheckResult(
            allowed=True,
            role_name="hr",
            requires_mfa=False,
            requires_break_glass=False,
            mfa_verified=False,
            break_glass_active=False,
        )
        with pytest.raises(AttributeError):
            result.allowed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_mfa_required_error(self):
        err = MFARequiredError("hr_manager", "eligibility")
        assert err.role_name == "hr_manager"
        assert err.phase_name == "eligibility"
        assert "MFA verification required" in str(err)
        assert "hr_manager" in str(err)
        assert "eligibility" in str(err)

    def test_break_glass_required_error(self):
        err = BreakGlassRequiredError("legal_counsel", "decision")
        assert err.role_name == "legal_counsel"
        assert err.phase_name == "decision"
        assert "Break-glass" in str(err)
        assert "legal_counsel" in str(err)
        assert "decision" in str(err)

    def test_mfa_error_is_exception(self):
        assert issubclass(MFARequiredError, Exception)

    def test_break_glass_error_is_exception(self):
        assert issubclass(BreakGlassRequiredError, Exception)


# ---------------------------------------------------------------------------
# find_role_for_phase
# ---------------------------------------------------------------------------


class TestFindRoleForPhase:
    def test_finds_hr_role_for_eligibility(self, sample_compiled, hr_role):
        role = find_role_for_phase("eligibility", "w", sample_compiled)
        assert role is not None
        assert role.name == "hr_manager"
        assert role.requires_mfa is True
        assert role.break_glass is False

    def test_finds_legal_role_for_decision(self, sample_compiled, legal_role):
        role = find_role_for_phase("decision", "w", sample_compiled)
        assert role is not None
        assert role.name == "legal_counsel"
        assert role.break_glass is True

    def test_returns_none_for_unconstrained_phase(self, sample_compiled):
        role = find_role_for_phase("notification", "w", sample_compiled)
        assert role is None

    def test_returns_none_for_unknown_phase(self, sample_compiled):
        role = find_role_for_phase("nonexistent", "w", sample_compiled)
        assert role is None

    def test_returns_none_for_unknown_workflow(self, sample_compiled):
        role = find_role_for_phase("eligibility", "nonexistent", sample_compiled)
        assert role is None

    def test_phase_with_no_actions(self):
        """Phase with no actions should not match any role."""
        phases = [_make_phase("empty_phase", [])]
        roles = [
            RoleNode(name="r", actions=("some_action",)),
        ]
        compiled = _make_compiled(phases, roles)
        role = find_role_for_phase("empty_phase", "w", compiled)
        assert role is None

    def test_no_roles_defined(self):
        """Charter with no roles should return None for all phases."""
        phases = [_make_phase("p", ["do_stuff"])]
        compiled = _make_compiled(phases, [])
        role = find_role_for_phase("p", "w", compiled)
        assert role is None

    def test_first_matching_role_returned(self):
        """When multiple roles could match, first one wins."""
        phases = [_make_phase("p", ["shared_action"])]
        roles = [
            RoleNode(name="role_a", actions=("shared_action",)),
            RoleNode(name="role_b", actions=("shared_action",)),
        ]
        compiled = _make_compiled(phases, roles)
        role = find_role_for_phase("p", "w", compiled)
        assert role is not None
        assert role.name == "role_a"

    def test_partial_action_overlap(self):
        """Role matches if ANY action overlaps with phase actions."""
        phases = [_make_phase("p", ["action_a", "action_b"])]
        roles = [
            RoleNode(name="r", actions=("action_b", "action_c")),
        ]
        compiled = _make_compiled(phases, roles)
        role = find_role_for_phase("p", "w", compiled)
        assert role is not None
        assert role.name == "r"

    def test_no_action_overlap(self):
        """Role does not match if no actions overlap."""
        phases = [_make_phase("p", ["action_a"])]
        roles = [
            RoleNode(name="r", actions=("action_x", "action_y")),
        ]
        compiled = _make_compiled(phases, roles)
        role = find_role_for_phase("p", "w", compiled)
        assert role is None


# ---------------------------------------------------------------------------
# verify_role_requirements
# ---------------------------------------------------------------------------


class TestVerifyRoleRequirements:
    @pytest.mark.asyncio
    async def test_mfa_required_and_verified(self, user_id, hr_role, mock_conn, monkeypatch):
        """MFA required, user has verified session -> allowed."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=hr_role,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.mfa_verified is True
        assert result.role_name == "hr_manager"
        assert result.reason is None

    @pytest.mark.asyncio
    async def test_mfa_required_but_not_verified(self, user_id, hr_role, mock_conn, monkeypatch):
        """MFA required, user does not have verified session -> denied."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=False),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=hr_role,
            conn=mock_conn,
        )
        assert result.allowed is False
        assert result.mfa_verified is False
        assert "MFA" in result.reason

    @pytest.mark.asyncio
    async def test_break_glass_required_and_active(
        self, user_id, legal_role, mock_conn, monkeypatch
    ):
        """Break glass required, user has elevated session -> allowed."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=True),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=legal_role,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.break_glass_active is True

    @pytest.mark.asyncio
    async def test_break_glass_required_but_not_active(
        self, user_id, legal_role, mock_conn, monkeypatch
    ):
        """Break glass required, no elevated session -> denied."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=False),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=legal_role,
            conn=mock_conn,
        )
        assert result.allowed is False
        assert result.break_glass_active is False
        assert "Break-glass" in result.reason

    @pytest.mark.asyncio
    async def test_both_mfa_and_break_glass_fail(self, user_id, legal_role, mock_conn, monkeypatch):
        """Both MFA and break glass fail -> denied with both reasons."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=False),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=legal_role,
            conn=mock_conn,
        )
        assert result.allowed is False
        assert "MFA" in result.reason
        assert "Break-glass" in result.reason

    @pytest.mark.asyncio
    async def test_no_requirements_always_allowed(
        self, user_id, viewer_role, mock_conn, monkeypatch
    ):
        """Role with no MFA and no break_glass -> always allowed."""
        # Neither check should be called
        mfa_mock = AsyncMock(return_value=False)
        bg_mock = AsyncMock(return_value=False)
        monkeypatch.setattr("canon.runtime.roles._check_mfa_verified", mfa_mock)
        monkeypatch.setattr("canon.runtime.roles._check_break_glass_active", bg_mock)

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=viewer_role,
            conn=mock_conn,
        )
        assert result.allowed is True
        # Neither check was needed
        mfa_mock.assert_not_awaited()
        bg_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_mfa_not_required_skips_check(self, user_id, mock_conn, monkeypatch):
        """When requires_mfa=False, MFA check is skipped entirely."""
        role = RoleNode(
            name="no_mfa",
            actions=("some_action",),
            break_glass=True,
            requires_mfa=False,
        )
        mfa_mock = AsyncMock(return_value=False)
        monkeypatch.setattr("canon.runtime.roles._check_mfa_verified", mfa_mock)
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=True),
        )

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=role,
            conn=mock_conn,
        )
        assert result.allowed is True
        mfa_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_break_glass_not_required_skips_check(
        self, user_id, hr_role, mock_conn, monkeypatch
    ):
        """When break_glass=False, break glass check is skipped."""
        bg_mock = AsyncMock(return_value=False)
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr("canon.runtime.roles._check_break_glass_active", bg_mock)

        result = await verify_role_requirements(
            user_id=user_id,
            role_node=hr_role,
            conn=mock_conn,
        )
        assert result.allowed is True
        bg_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# enforce_role_requirements
# ---------------------------------------------------------------------------


class TestEnforceRoleRequirements:
    @pytest.mark.asyncio
    async def test_no_role_returns_allowed(self, user_id, mock_conn):
        """Phase with no governing role -> allowed, no DB queries."""
        phases = [_make_phase("free_phase", ["uncontrolled_action"])]
        compiled = _make_compiled(phases, [])

        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="free_phase",
            workflow_name="w",
            compiled=compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.role_name == "(none)"

    @pytest.mark.asyncio
    async def test_mfa_satisfied_returns_result(
        self, user_id, mock_conn, sample_compiled, monkeypatch
    ):
        """MFA required and satisfied -> returns allowed result."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )

        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="eligibility",
            workflow_name="w",
            compiled=sample_compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.role_name == "hr_manager"

    @pytest.mark.asyncio
    async def test_mfa_not_satisfied_raises(self, user_id, mock_conn, sample_compiled, monkeypatch):
        """MFA required but not verified -> raises MFARequiredError."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=False),
        )

        with pytest.raises(MFARequiredError) as exc_info:
            await enforce_role_requirements(
                user_id=user_id,
                phase_name="eligibility",
                workflow_name="w",
                compiled=sample_compiled,
                conn=mock_conn,
            )
        assert exc_info.value.role_name == "hr_manager"
        assert exc_info.value.phase_name == "eligibility"

    @pytest.mark.asyncio
    async def test_break_glass_not_satisfied_raises(
        self, user_id, mock_conn, sample_compiled, monkeypatch
    ):
        """Break glass required but not active -> raises BreakGlassRequiredError."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=False),
        )

        with pytest.raises(BreakGlassRequiredError) as exc_info:
            await enforce_role_requirements(
                user_id=user_id,
                phase_name="decision",
                workflow_name="w",
                compiled=sample_compiled,
                conn=mock_conn,
            )
        assert exc_info.value.role_name == "legal_counsel"
        assert exc_info.value.phase_name == "decision"

    @pytest.mark.asyncio
    async def test_mfa_fails_before_break_glass(
        self, user_id, mock_conn, sample_compiled, monkeypatch
    ):
        """When both fail, MFA error is raised first."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=False),
        )

        with pytest.raises(MFARequiredError):
            await enforce_role_requirements(
                user_id=user_id,
                phase_name="decision",
                workflow_name="w",
                compiled=sample_compiled,
                conn=mock_conn,
            )

    @pytest.mark.asyncio
    async def test_both_satisfied_returns_allowed(
        self, user_id, mock_conn, sample_compiled, monkeypatch
    ):
        """Both MFA and break_glass satisfied -> allowed."""
        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr(
            "canon.runtime.roles._check_break_glass_active",
            AsyncMock(return_value=True),
        )

        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="decision",
            workflow_name="w",
            compiled=sample_compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.role_name == "legal_counsel"

    @pytest.mark.asyncio
    async def test_unconstrained_phase_no_db_queries(self, user_id, mock_conn, sample_compiled):
        """Phase with no role -> no DB calls made."""
        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="notification",
            workflow_name="w",
            compiled=sample_compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        # mock_conn should not have been called
        mock_conn.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unknown_phase_returns_allowed(self, user_id, mock_conn, sample_compiled):
        """Unknown phase name returns allowed (no role found)."""
        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="nonexistent_phase",
            workflow_name="w",
            compiled=sample_compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.role_name == "(none)"


# ---------------------------------------------------------------------------
# _check_mfa_verified (integration with select_one)
# ---------------------------------------------------------------------------


class TestCheckMFAVerified:
    @pytest.mark.asyncio
    async def test_returns_true_when_session_found(self, user_id, monkeypatch):
        """select_one returns a row -> True."""
        mock_select = AsyncMock(return_value={"id": uuid4(), "mfa_verified": True})
        monkeypatch.setattr("canon.runtime.roles.select_one", mock_select)

        result = await _check_mfa_verified(user_id, AsyncMock())
        assert result is True

        # Verify query parameters (table is positional, where is keyword)
        mock_select.assert_awaited_once()
        call_args = mock_select.call_args
        assert call_args[0][0] == "sessions"
        where = call_args.kwargs["where"]
        assert where["user_id"] == user_id
        assert where["mfa_verified"] is True
        assert where["is_revoked"] is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_session(self, user_id, monkeypatch):
        """select_one returns None -> False."""
        mock_select = AsyncMock(return_value=None)
        monkeypatch.setattr("canon.runtime.roles.select_one", mock_select)

        result = await _check_mfa_verified(user_id, AsyncMock())
        assert result is False


class TestCheckBreakGlassActive:
    @pytest.mark.asyncio
    async def test_returns_true_when_session_found(self, user_id, monkeypatch):
        """select_one returns a row -> True."""
        mock_select = AsyncMock(return_value={"id": uuid4(), "auth_method": "break_glass"})
        monkeypatch.setattr("canon.runtime.roles.select_one", mock_select)

        result = await _check_break_glass_active(user_id, AsyncMock())
        assert result is True

        # Verify query parameters (table is positional, where is keyword)
        mock_select.assert_awaited_once()
        call_args = mock_select.call_args
        assert call_args[0][0] == "sessions"
        where = call_args.kwargs["where"]
        assert where["user_id"] == user_id
        assert where["auth_method"] == "break_glass"
        assert where["is_revoked"] is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_session(self, user_id, monkeypatch):
        """select_one returns None -> False."""
        mock_select = AsyncMock(return_value=None)
        monkeypatch.setattr("canon.runtime.roles.select_one", mock_select)

        result = await _check_break_glass_active(user_id, AsyncMock())
        assert result is False


# ---------------------------------------------------------------------------
# Import from runtime package
# ---------------------------------------------------------------------------


class TestImports:
    """Verify public API exports from canon.runtime."""

    def test_import_role_check_result(self):
        from canon.runtime import RoleCheckResult as Cls

        assert Cls is RoleCheckResult

    def test_import_mfa_required_error(self):
        from canon.runtime import MFARequiredError as Cls

        assert Cls is MFARequiredError

    def test_import_break_glass_required_error(self):
        from canon.runtime import BreakGlassRequiredError as Cls

        assert Cls is BreakGlassRequiredError

    def test_import_find_role_for_phase(self):
        from canon.runtime import find_role_for_phase as fn

        assert fn is find_role_for_phase

    def test_import_verify_role_requirements(self):
        from canon.runtime import verify_role_requirements as fn

        assert fn is verify_role_requirements

    def test_import_enforce_role_requirements(self):
        from canon.runtime import enforce_role_requirements as fn

        assert fn is enforce_role_requirements


# ---------------------------------------------------------------------------
# Edge cases and integration scenarios
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_role_with_single_action(self):
        """Role with exactly one action matches correctly."""
        phases = [_make_phase("p", ["only_action"])]
        roles = [RoleNode(name="r", actions=("only_action",))]
        compiled = _make_compiled(phases, roles)
        role = find_role_for_phase("p", "w", compiled)
        assert role is not None
        assert role.name == "r"

    def test_multiple_workflows(self):
        """Roles match correctly across multiple workflows."""
        w1 = WorkflowNode(
            name="w1",
            phases=(_make_phase("p1", ["action_a"]),),
        )
        w2 = WorkflowNode(
            name="w2",
            phases=(_make_phase("p2", ["action_b"]),),
        )
        roles = [
            RoleNode(name="role_a", actions=("action_a",)),
            RoleNode(name="role_b", actions=("action_b",)),
        ]
        ast = CharterNode(
            name="Multi",
            version="v1",
            workflows=(w1, w2),
            roles=tuple(roles),
        )
        compiled = CompiledCharter(
            name="Multi",
            version="v1",
            ast=ast,
            feature_names=frozenset(),
            schema_types=MappingProxyType({}),
            phase_order=MappingProxyType({"w1": ("p1",), "w2": ("p2",)}),
            policy_ids=frozenset(),
            package_names=frozenset(),
            situations=(),
            roles=tuple(roles),
        )

        role_w1 = find_role_for_phase("p1", "w1", compiled)
        role_w2 = find_role_for_phase("p2", "w2", compiled)
        assert role_w1 is not None and role_w1.name == "role_a"
        assert role_w2 is not None and role_w2.name == "role_b"

        # Cross-workflow: p1 not in w2
        role_cross = find_role_for_phase("p1", "w2", compiled)
        assert role_cross is None

    @pytest.mark.asyncio
    async def test_enforce_with_default_mfa_true(self, user_id, mock_conn, monkeypatch):
        """RoleNode defaults requires_mfa=True, enforce should check MFA."""
        role = RoleNode(name="default_role", actions=("do_thing",))
        assert role.requires_mfa is True  # Default

        phases = [_make_phase("p", ["do_thing"])]
        compiled = _make_compiled(phases, [role])

        monkeypatch.setattr(
            "canon.runtime.roles._check_mfa_verified",
            AsyncMock(return_value=True),
        )

        result = await enforce_role_requirements(
            user_id=user_id,
            phase_name="p",
            workflow_name="w",
            compiled=compiled,
            conn=mock_conn,
        )
        assert result.allowed is True
        assert result.requires_mfa is True
