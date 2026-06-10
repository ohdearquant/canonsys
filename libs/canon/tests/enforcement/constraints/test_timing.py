"""Tests for timing truth machine constraints.

Tests cover:
- waiting_period_must_be_elapsed: FCRA waiting period validation
- notice_must_precede_action: Notice timing enforcement
- evidence_must_be_fresh: Evidence freshness validation
- deadline_must_not_be_exceeded: Deadline enforcement

Truth Machine Semantics:
    Each constraint returns None on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from canon.enforcement.constraints import (
    deadline_must_not_be_exceeded,
    evidence_must_be_fresh,
    notice_must_precede_action,
    waiting_period_must_be_elapsed,
)
from canon.enforcement.exceptions import (
    EvidenceStaleError,
    NoticePrecedenceError,
    TimingViolation,
    WaitingPeriodNotElapsedError,
)

from .conftest import MockWaitingPeriodState

# =============================================================================
# waiting_period_must_be_elapsed Tests
# =============================================================================


class TestWaitingPeriodMustBeElapsed:
    """Tests for waiting_period_must_be_elapsed constraint."""

    def test_elapsed_period_succeeds(self, elapsed_waiting_period: MockWaitingPeriodState):
        """Test elapsed waiting period passes validation."""
        result = waiting_period_must_be_elapsed(elapsed_waiting_period)
        assert result is None  # Successful execution

    def test_not_elapsed_period_raises(self, not_elapsed_waiting_period: MockWaitingPeriodState):
        """Test non-elapsed waiting period raises WaitingPeriodNotElapsedError."""
        with pytest.raises(WaitingPeriodNotElapsedError) as exc_info:
            waiting_period_must_be_elapsed(not_elapsed_waiting_period)

        exc = exc_info.value
        assert exc.notice_id == not_elapsed_waiting_period.notice_id
        assert exc.required_days == 5
        assert exc.elapsed_days < exc.required_days

    def test_paused_period_raises(self, paused_waiting_period: MockWaitingPeriodState):
        """Test paused waiting period raises WaitingPeriodNotElapsedError."""
        with pytest.raises(WaitingPeriodNotElapsedError) as exc_info:
            waiting_period_must_be_elapsed(paused_waiting_period)

        exc = exc_info.value
        assert exc.notice_id == paused_waiting_period.notice_id

    def test_resumed_elapsed_period_succeeds(self, resumed_waiting_period: MockWaitingPeriodState):
        """Test resumed and elapsed waiting period passes."""
        result = waiting_period_must_be_elapsed(resumed_waiting_period)
        assert result is None

    def test_edge_case_exactly_required_days(self):
        """Test period that has exactly elapsed the required days."""
        notice_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=5, hours=1)
        period = MockWaitingPeriodState(
            notice_id=notice_id,
            required_days=5,
            started_at=started_at,
            elapsed=True,
        )

        result = waiting_period_must_be_elapsed(period)
        assert result is None

    def test_edge_case_one_day_short(self):
        """Test period that is one day short of required."""
        notice_id = uuid4()
        started_at = datetime.now(UTC) - timedelta(days=4)
        period = MockWaitingPeriodState(
            notice_id=notice_id,
            required_days=5,
            started_at=started_at,
            elapsed=False,
        )

        with pytest.raises(WaitingPeriodNotElapsedError) as exc_info:
            waiting_period_must_be_elapsed(period)

        assert exc_info.value.elapsed_days == 4
        assert exc_info.value.required_days == 5

    def test_zero_day_period(self):
        """Test period with zero required days that is marked elapsed."""
        notice_id = uuid4()
        period = MockWaitingPeriodState(
            notice_id=notice_id,
            required_days=0,
            started_at=datetime.now(UTC),
            elapsed=True,
        )

        result = waiting_period_must_be_elapsed(period)
        assert result is None


# =============================================================================
# notice_must_precede_action Tests
# =============================================================================


class TestNoticeMustPrecedeAction:
    """Tests for notice_must_precede_action constraint."""

    def test_notice_before_action_succeeds(self):
        """Test notice sent before action passes validation."""
        notice_sent = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        action_at = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)

        result = notice_must_precede_action(notice_sent, action_at, "pre_adverse_action")
        assert result is None

    def test_no_notice_raises(self):
        """Test missing notice raises NoticePrecedenceError."""
        action_at = datetime(2024, 1, 10, tzinfo=UTC)

        with pytest.raises(NoticePrecedenceError) as exc_info:
            notice_must_precede_action(None, action_at, "pre_adverse_action")

        exc = exc_info.value
        assert exc.notice_status == "not_sent"
        assert exc.notice_required == "pre_adverse_action"

    def test_notice_after_action_raises(self):
        """Test notice sent after action raises NoticePrecedenceError."""
        notice_sent = datetime(2024, 1, 15, tzinfo=UTC)
        action_at = datetime(2024, 1, 10, tzinfo=UTC)

        with pytest.raises(NoticePrecedenceError) as exc_info:
            notice_must_precede_action(notice_sent, action_at, "pre_adverse_action")

        assert exc_info.value.notice_status == "sent_after_action"

    def test_notice_at_exact_action_time_raises(self):
        """Test notice at exact action time raises (must strictly precede)."""
        same_time = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)

        with pytest.raises(NoticePrecedenceError):
            notice_must_precede_action(same_time, same_time, "pre_adverse_action")

    def test_naive_datetime_handled(self):
        """Test naive datetime is handled (assumed UTC)."""
        notice_sent = datetime(2024, 1, 1, 12, 0, 0)  # Naive
        action_at = datetime(2024, 1, 10, 12, 0, 0)  # Naive

        result = notice_must_precede_action(notice_sent, action_at, "warn_act")
        assert result is None

    def test_different_notice_types(self):
        """Test various notice types are accepted."""
        notice_types = [
            "pre_adverse_action",
            "warn_act",
            "california_warn",
            "final_notice",
        ]

        notice_sent = datetime(2024, 1, 1, tzinfo=UTC)
        action_at = datetime(2024, 1, 10, tzinfo=UTC)

        for notice_type in notice_types:
            result = notice_must_precede_action(notice_sent, action_at, notice_type)
            assert result is None

    def test_one_second_before_succeeds(self):
        """Test notice one second before action passes."""
        action_at = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)
        notice_sent = action_at - timedelta(seconds=1)

        result = notice_must_precede_action(notice_sent, action_at, "pre_adverse_action")
        assert result is None


# =============================================================================
# evidence_must_be_fresh Tests
# =============================================================================


class TestEvidenceMustBeFresh:
    """Tests for evidence_must_be_fresh constraint."""

    def test_fresh_evidence_succeeds(self, fresh_evidence_timestamp: datetime):
        """Test fresh evidence passes validation."""
        result = evidence_must_be_fresh(fresh_evidence_timestamp, max_age_hours=24)
        assert result is None

    def test_stale_evidence_raises(self, stale_evidence_timestamp: datetime):
        """Test stale evidence raises EvidenceStaleError."""
        with pytest.raises(EvidenceStaleError) as exc_info:
            evidence_must_be_fresh(stale_evidence_timestamp, max_age_hours=24)

        exc = exc_info.value
        assert exc.max_age_hours == 24
        assert exc.actual_age_hours >= 48

    def test_exactly_at_max_age_succeeds(self):
        """Test evidence exactly at max age passes (not exceeded)."""
        now = datetime.now(UTC)
        evidence_time = now - timedelta(hours=24)

        result = evidence_must_be_fresh(evidence_time, max_age_hours=24, now=now)
        assert result is None

    def test_one_hour_over_max_age_raises(self):
        """Test evidence one hour over max age raises."""
        now = datetime.now(UTC)
        evidence_time = now - timedelta(hours=25)

        with pytest.raises(EvidenceStaleError) as exc_info:
            evidence_must_be_fresh(evidence_time, max_age_hours=24, now=now)

        assert exc_info.value.actual_age_hours == 25

    def test_custom_reference_time(self):
        """Test with custom reference time."""
        evidence_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        reference_time = datetime(2024, 1, 2, 12, 0, 0, tzinfo=UTC)  # 24h later

        # Should pass with 24h max age
        result = evidence_must_be_fresh(evidence_time, max_age_hours=24, now=reference_time)
        assert result is None

        # Should fail with 23h max age
        with pytest.raises(EvidenceStaleError):
            evidence_must_be_fresh(evidence_time, max_age_hours=23, now=reference_time)

    def test_evidence_id_in_error(self):
        """Test evidence_id is included in error when provided."""
        evidence_id = uuid4()
        stale_time = datetime.now(UTC) - timedelta(hours=100)

        with pytest.raises(EvidenceStaleError) as exc_info:
            evidence_must_be_fresh(stale_time, max_age_hours=24, evidence_id=evidence_id)

        assert exc_info.value.evidence_id == evidence_id

    def test_naive_datetime_handled(self):
        """Test naive datetime is handled (assumed UTC)."""
        evidence_time = datetime.utcnow() - timedelta(hours=12)  # Naive
        now = datetime.utcnow()  # Naive

        result = evidence_must_be_fresh(evidence_time, max_age_hours=24, now=now)
        assert result is None

    def test_various_max_age_values(self):
        """Test various max_age_hours values."""
        now = datetime.now(UTC)

        test_cases = [
            (1, timedelta(minutes=30), True),  # 30 min old, 1h max -> pass
            (1, timedelta(hours=2), False),  # 2h old, 1h max -> fail
            (72, timedelta(days=2), True),  # 2 days old, 72h max -> pass
            (72, timedelta(days=4), False),  # 4 days old, 72h max -> fail
            (168, timedelta(days=6), True),  # 6 days old, 168h (1 week) max -> pass
        ]

        for max_age, age_delta, should_pass in test_cases:
            evidence_time = now - age_delta
            if should_pass:
                result = evidence_must_be_fresh(evidence_time, max_age_hours=max_age, now=now)
                assert result is None
            else:
                with pytest.raises(EvidenceStaleError):
                    evidence_must_be_fresh(evidence_time, max_age_hours=max_age, now=now)


# =============================================================================
# deadline_must_not_be_exceeded Tests
# =============================================================================


class TestDeadlineMustNotBeExceeded:
    """Tests for deadline_must_not_be_exceeded constraint."""

    def test_before_deadline_succeeds(self, future_timestamp: datetime):
        """Test time before deadline passes validation."""
        result = deadline_must_not_be_exceeded(future_timestamp)
        assert result is None

    def test_after_deadline_raises(self, past_timestamp: datetime):
        """Test time after deadline raises TimingViolation."""
        with pytest.raises(TimingViolation) as exc_info:
            deadline_must_not_be_exceeded(past_timestamp)

        exc = exc_info.value
        assert "exceeded" in exc.message.lower()
        assert "deadline" in exc.context

    def test_at_exact_deadline_succeeds(self):
        """Test time at exact deadline passes (not exceeded yet)."""
        now = datetime.now(UTC)
        result = deadline_must_not_be_exceeded(now, now=now)
        assert result is None

    def test_one_second_after_deadline_raises(self):
        """Test one second after deadline raises."""
        deadline = datetime(2024, 1, 10, 12, 0, 0, tzinfo=UTC)
        now = deadline + timedelta(seconds=1)

        with pytest.raises(TimingViolation) as exc_info:
            deadline_must_not_be_exceeded(deadline, now=now)

        assert exc_info.value.context["exceeded_by_seconds"] == 1

    def test_custom_reference_time(self):
        """Test with custom reference time."""
        deadline = datetime(2024, 6, 30, 23, 59, 59, tzinfo=UTC)

        # Before deadline
        before = datetime(2024, 6, 15, tzinfo=UTC)
        result = deadline_must_not_be_exceeded(deadline, now=before)
        assert result is None

        # After deadline
        after = datetime(2024, 7, 15, tzinfo=UTC)
        with pytest.raises(TimingViolation):
            deadline_must_not_be_exceeded(deadline, now=after)

    def test_naive_datetime_handled(self):
        """Test naive datetime is handled (assumed UTC)."""
        deadline = datetime(2024, 12, 31, 23, 59, 59)  # Naive
        now = datetime(2024, 6, 15)  # Naive, before deadline

        result = deadline_must_not_be_exceeded(deadline, now=now)
        assert result is None

    def test_context_contains_exceeded_by_seconds(self):
        """Test context contains exceeded_by_seconds calculation."""
        deadline = datetime(2024, 1, 10, tzinfo=UTC)
        now = datetime(2024, 1, 11, tzinfo=UTC)  # 1 day after

        with pytest.raises(TimingViolation) as exc_info:
            deadline_must_not_be_exceeded(deadline, now=now)

        exceeded_by = exc_info.value.context["exceeded_by_seconds"]
        assert exceeded_by == 86400  # 1 day in seconds

    def test_regulatory_context_in_message(self):
        """Test timing violation contains regulatory context."""
        past = datetime.now(UTC) - timedelta(days=1)

        with pytest.raises(TimingViolation) as exc_info:
            deadline_must_not_be_exceeded(past)

        assert exc_info.value.regulation == "Timing Requirement"


# =============================================================================
# Truth Machine Composition Tests
# =============================================================================


class TestTimingComposition:
    """Tests for composing multiple timing constraints."""

    def test_all_timing_checks_pass(
        self,
        elapsed_waiting_period: MockWaitingPeriodState,
        fresh_evidence_timestamp: datetime,
        future_timestamp: datetime,
    ):
        """Test all timing constraints pass in sequence."""
        notice_sent = datetime.now(UTC) - timedelta(days=10)
        action_at = datetime.now(UTC)

        # If all execute without raising, all invariants hold
        waiting_period_must_be_elapsed(elapsed_waiting_period)
        notice_must_precede_action(notice_sent, action_at, "pre_adverse_action")
        evidence_must_be_fresh(fresh_evidence_timestamp, max_age_hours=24)
        deadline_must_not_be_exceeded(future_timestamp)
        # Reaching here means all timing requirements are satisfied

    def test_fails_at_first_violation(
        self,
        not_elapsed_waiting_period: MockWaitingPeriodState,
        fresh_evidence_timestamp: datetime,
    ):
        """Test composition fails at first violation."""
        with pytest.raises(WaitingPeriodNotElapsedError):
            waiting_period_must_be_elapsed(not_elapsed_waiting_period)
            # Remaining constraints never execute
            evidence_must_be_fresh(fresh_evidence_timestamp, max_age_hours=24)
