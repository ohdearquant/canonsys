"""Tests for canon.runtime.phase_state module."""

from __future__ import annotations

import pytest

from canon.runtime.phase_state import (
    PHASE_TRANSITIONS,
    InvalidPhaseTransition,
    PhaseState,
    get_terminal_states,
    is_valid_transition,
)


class TestPhaseStateEnum:
    """Test PhaseState enum values and completeness."""

    def test_all_states_exist(self):
        assert PhaseState.PENDING.value == "pending"
        assert PhaseState.WAITING_GATE.value == "waiting_gate"
        assert PhaseState.WAITING_USER.value == "waiting_user"
        assert PhaseState.WAITING_TRIGGER.value == "waiting_trigger"
        assert PhaseState.IN_PROGRESS.value == "in_progress"
        assert PhaseState.COMPLETED.value == "completed"
        assert PhaseState.SKIPPED.value == "skipped"
        assert PhaseState.FAILED.value == "failed"

    def test_eight_states(self):
        assert len(PhaseState) == 8

    def test_roundtrip_from_string(self):
        for state in PhaseState:
            assert PhaseState(state.value) is state


class TestPhaseTransitions:
    """Test the transition matrix is correct and complete."""

    def test_all_states_in_transitions(self):
        for state in PhaseState:
            assert state in PHASE_TRANSITIONS, f"{state} missing from PHASE_TRANSITIONS"

    def test_pending_transitions(self):
        targets = PHASE_TRANSITIONS[PhaseState.PENDING]
        assert PhaseState.WAITING_GATE in targets
        assert PhaseState.WAITING_USER in targets
        assert PhaseState.WAITING_TRIGGER in targets
        assert PhaseState.SKIPPED in targets
        assert len(targets) == 4

    def test_waiting_gate_transitions(self):
        targets = PHASE_TRANSITIONS[PhaseState.WAITING_GATE]
        assert PhaseState.WAITING_USER in targets
        assert PhaseState.FAILED in targets
        assert PhaseState.SKIPPED in targets
        assert len(targets) == 3

    def test_waiting_user_transitions(self):
        targets = PHASE_TRANSITIONS[PhaseState.WAITING_USER]
        assert PhaseState.IN_PROGRESS in targets
        assert PhaseState.WAITING_TRIGGER in targets
        assert PhaseState.SKIPPED in targets
        assert len(targets) == 3

    def test_waiting_trigger_transitions(self):
        targets = PHASE_TRANSITIONS[PhaseState.WAITING_TRIGGER]
        assert PhaseState.IN_PROGRESS in targets
        assert PhaseState.FAILED in targets
        assert len(targets) == 2

    def test_in_progress_transitions(self):
        targets = PHASE_TRANSITIONS[PhaseState.IN_PROGRESS]
        assert PhaseState.COMPLETED in targets
        assert PhaseState.FAILED in targets
        assert len(targets) == 2

    def test_terminal_states_have_no_transitions(self):
        for state in (PhaseState.COMPLETED, PhaseState.SKIPPED, PhaseState.FAILED):
            assert len(PHASE_TRANSITIONS[state]) == 0

    def test_no_self_transitions(self):
        for state, targets in PHASE_TRANSITIONS.items():
            assert state not in targets, f"{state} allows self-transition"

    def test_no_backward_to_pending(self):
        """Once you leave PENDING, you can never go back."""
        for state in PhaseState:
            if state == PhaseState.PENDING:
                continue
            targets = PHASE_TRANSITIONS[state]
            assert PhaseState.PENDING not in targets


class TestIsValidTransition:
    """Test the is_valid_transition helper."""

    def test_valid_happy_path(self):
        assert is_valid_transition(PhaseState.PENDING, PhaseState.WAITING_USER)
        assert is_valid_transition(PhaseState.WAITING_USER, PhaseState.IN_PROGRESS)
        assert is_valid_transition(PhaseState.IN_PROGRESS, PhaseState.COMPLETED)

    def test_valid_gate_path(self):
        assert is_valid_transition(PhaseState.PENDING, PhaseState.WAITING_GATE)
        assert is_valid_transition(PhaseState.WAITING_GATE, PhaseState.WAITING_USER)

    def test_valid_skip(self):
        assert is_valid_transition(PhaseState.PENDING, PhaseState.SKIPPED)
        assert is_valid_transition(PhaseState.WAITING_GATE, PhaseState.SKIPPED)
        assert is_valid_transition(PhaseState.WAITING_USER, PhaseState.SKIPPED)

    def test_valid_failure(self):
        assert is_valid_transition(PhaseState.WAITING_GATE, PhaseState.FAILED)
        assert is_valid_transition(PhaseState.WAITING_TRIGGER, PhaseState.FAILED)
        assert is_valid_transition(PhaseState.IN_PROGRESS, PhaseState.FAILED)

    def test_invalid_terminal_to_anything(self):
        for target in PhaseState:
            assert not is_valid_transition(PhaseState.COMPLETED, target)
            assert not is_valid_transition(PhaseState.SKIPPED, target)
            assert not is_valid_transition(PhaseState.FAILED, target)

    def test_invalid_skip_backwards(self):
        assert not is_valid_transition(PhaseState.IN_PROGRESS, PhaseState.PENDING)
        assert not is_valid_transition(PhaseState.COMPLETED, PhaseState.PENDING)

    def test_invalid_pending_to_completed_directly(self):
        assert not is_valid_transition(PhaseState.PENDING, PhaseState.COMPLETED)

    def test_invalid_pending_to_in_progress_directly(self):
        assert not is_valid_transition(PhaseState.PENDING, PhaseState.IN_PROGRESS)


class TestGetTerminalStates:
    """Test terminal state detection."""

    def test_terminal_states(self):
        terminal = get_terminal_states()
        assert terminal == frozenset(
            {
                PhaseState.COMPLETED,
                PhaseState.SKIPPED,
                PhaseState.FAILED,
            }
        )

    def test_non_terminal_states_not_included(self):
        terminal = get_terminal_states()
        for state in (
            PhaseState.PENDING,
            PhaseState.WAITING_GATE,
            PhaseState.WAITING_USER,
            PhaseState.WAITING_TRIGGER,
            PhaseState.IN_PROGRESS,
        ):
            assert state not in terminal

    def test_returns_frozenset(self):
        terminal = get_terminal_states()
        assert isinstance(terminal, frozenset)


class TestInvalidPhaseTransition:
    """Test the InvalidPhaseTransition exception."""

    def test_basic_creation(self):
        exc = InvalidPhaseTransition(PhaseState.COMPLETED, PhaseState.PENDING)
        assert "completed" in str(exc)
        assert "pending" in str(exc)
        assert exc.from_state == "completed"
        assert exc.to_state == "pending"

    def test_with_context(self):
        exc = InvalidPhaseTransition(
            PhaseState.COMPLETED,
            PhaseState.PENDING,
            phase_name="hm_approval",
            run_id="run-123",
        )
        assert "hm_approval" in str(exc)
        assert "run-123" in str(exc)
        assert exc.phase_name == "hm_approval"
        assert exc.run_id == "run-123"

    def test_string_inputs(self):
        exc = InvalidPhaseTransition("completed", "pending")
        assert exc.from_state == "completed"
        assert exc.to_state == "pending"

    def test_to_dict(self):
        exc = InvalidPhaseTransition(
            PhaseState.IN_PROGRESS,
            PhaseState.PENDING,
            phase_name="review",
            run_id="abc",
        )
        d = exc.to_dict()
        assert d["error"] == "InvalidPhaseTransition"
        assert d["from_state"] == "in_progress"
        assert d["to_state"] == "pending"
        assert d["phase_name"] == "review"
        assert d["run_id"] == "abc"

    def test_to_dict_without_context(self):
        exc = InvalidPhaseTransition(PhaseState.COMPLETED, PhaseState.PENDING)
        d = exc.to_dict()
        assert d["phase_name"] is None
        assert d["run_id"] is None

    def test_is_exception(self):
        exc = InvalidPhaseTransition(PhaseState.COMPLETED, PhaseState.PENDING)
        assert isinstance(exc, Exception)
        with pytest.raises(InvalidPhaseTransition):
            raise exc
