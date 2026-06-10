"""Tests for canon.kron.core.event - Event with async lifecycle."""

import pytest

from kron.core.event import EventStatus, Execution
from kron.types import is_unset

from .conftest import SimpleTestEvent, SlowTestEvent


class TestEventCreation:
    """Test Event instantiation."""

    def test_event_initial_status(self, simple_event):
        """Event should start with PENDING status."""
        assert simple_event.execution.status == EventStatus.PENDING

    def test_event_has_execution(self, simple_event):
        """Event should have Execution instance."""
        assert hasattr(simple_event, "execution")
        assert isinstance(simple_event.execution, Execution)

    def test_event_timeout_optional(self, simple_event):
        """Event timeout should be optional (Unset by default)."""
        assert is_unset(simple_event.timeout)

    def test_event_with_timeout(self):
        """Event should accept timeout parameter."""
        event = SimpleTestEvent(timeout=5.0, return_value="test")
        assert event.timeout == 5.0

    def test_event_invalid_timeout_negative(self):
        """Event should reject negative timeout."""
        with pytest.raises(ValueError):
            SimpleTestEvent(timeout=-1.0, return_value="test")

    def test_event_invalid_timeout_zero(self):
        """Event should reject zero timeout."""
        with pytest.raises(ValueError):
            SimpleTestEvent(timeout=0, return_value="test")


class TestEventInvocation:
    """Test Event.invoke() lifecycle."""

    @pytest.mark.anyio
    async def test_invoke_success(self, simple_event):
        """Successful invoke should set COMPLETED status."""
        await simple_event.invoke()

        assert simple_event.execution.status == EventStatus.COMPLETED
        assert simple_event.execution.response == "test_result"
        assert simple_event.execution.error is None

    @pytest.mark.anyio
    async def test_invoke_failure(self, failing_event):
        """Failed invoke should set FAILED status and capture error."""
        await failing_event.invoke()

        assert failing_event.execution.status == EventStatus.FAILED
        assert failing_event.execution.error is not None
        assert "Test error" in str(failing_event.execution.error)

    @pytest.mark.anyio
    async def test_invoke_idempotent(self, simple_event):
        """Multiple invoke() calls should be no-op after first."""
        await simple_event.invoke()
        first_response = simple_event.execution.response
        first_duration = simple_event.execution.duration

        # Second invoke should be no-op
        await simple_event.invoke()

        assert simple_event.execution.response == first_response
        assert simple_event.execution.duration == first_duration

    @pytest.mark.anyio
    async def test_invoke_timeout(self):
        """Event should respect timeout setting."""
        event = SlowTestEvent(delay=1.0, timeout=0.01)
        await event.invoke()

        assert event.execution.status == EventStatus.CANCELLED
        assert event.execution.retryable is True

    @pytest.mark.anyio
    async def test_invoke_tracks_duration(self, simple_event):
        """Event.invoke() should track execution duration."""
        await simple_event.invoke()

        assert simple_event.execution.duration is not None
        assert simple_event.execution.duration >= 0


class TestExecution:
    """Test Execution dataclass."""

    def test_execution_default_pending(self):
        """Execution should default to PENDING."""
        execution = Execution()
        assert execution.status == EventStatus.PENDING

    def test_execution_to_dict(self, simple_event):
        """Execution.to_dict() should serialize properly."""
        data = simple_event.execution.to_dict()

        assert "status" in data
        assert data["status"] == "pending"
        assert "duration" in data
        assert "response" in data
        assert "error" in data

    @pytest.mark.anyio
    async def test_execution_after_success(self, simple_event):
        """Execution should track success state."""
        await simple_event.invoke()
        data = simple_event.execution.to_dict()

        assert data["status"] == "completed"
        assert data["error"] is None
        assert data["duration"] is not None

    @pytest.mark.anyio
    async def test_execution_after_failure(self, failing_event):
        """Execution should track failure state."""
        await failing_event.invoke()
        data = failing_event.execution.to_dict()

        assert data["status"] == "failed"
        assert data["error"] is not None
        assert "Test error" in data["error"]["message"]

    def test_execution_add_error(self):
        """Execution.add_error() should accumulate errors."""
        execution = Execution()
        execution.add_error(ValueError("first error"))

        assert execution.error is not None
        assert "first error" in str(execution.error)

    def test_execution_add_multiple_errors(self):
        """Execution.add_error() should create ExceptionGroup for multiple errors."""
        execution = Execution()
        execution.add_error(ValueError("error 1"))
        execution.add_error(TypeError("error 2"))

        assert isinstance(execution.error, ExceptionGroup)
        assert len(execution.error.exceptions) == 2


class TestEventFreshCopy:
    """Test Event.as_fresh_event() cloning."""

    @pytest.mark.anyio
    async def test_as_fresh_event(self, simple_event):
        """Event.as_fresh_event() should create fresh copy."""
        await simple_event.invoke()
        assert simple_event.execution.status == EventStatus.COMPLETED

        fresh = simple_event.as_fresh_event()

        assert fresh.id != simple_event.id
        assert fresh.execution.status == EventStatus.PENDING
        assert "original" in fresh.metadata
        assert str(simple_event.id) == fresh.metadata["original"]["id"]

    @pytest.mark.anyio
    async def test_as_fresh_event_copy_meta(self, simple_event):
        """Event.as_fresh_event(copy_meta=True) should copy metadata."""
        simple_event.metadata["custom"] = "value"
        await simple_event.invoke()

        fresh = simple_event.as_fresh_event(copy_meta=True)

        assert fresh.metadata.get("custom") == "value"
