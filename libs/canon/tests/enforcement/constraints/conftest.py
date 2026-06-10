"""Shared fixtures for truth machine constraint tests.

Provides mock objects and fixtures that simulate the domain types
used by constraint functions without requiring actual database connections.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

# =============================================================================
# Mock Types for Timing Constraints
# =============================================================================


@dataclass
class MockWaitingPeriodState:
    """Mock WaitingPeriodState for testing."""

    notice_id: UUID
    required_days: int
    started_at: datetime
    elapsed: bool = False
    paused_at: datetime | None = None
    resumed_at: datetime | None = None


# =============================================================================
# Mock Types for Authorization Constraints
# =============================================================================


@dataclass
class MockApproval:
    """Mock approval record with approver_id."""

    approver_id: UUID


# =============================================================================
# Waiting Period Fixtures
# =============================================================================


@pytest.fixture
def elapsed_waiting_period() -> MockWaitingPeriodState:
    """Create an elapsed waiting period."""
    notice_id = uuid4()
    return MockWaitingPeriodState(
        notice_id=notice_id,
        required_days=5,
        started_at=datetime.now(UTC) - timedelta(days=10),
        elapsed=True,
    )


@pytest.fixture
def not_elapsed_waiting_period() -> MockWaitingPeriodState:
    """Create a waiting period that has not elapsed."""
    notice_id = uuid4()
    return MockWaitingPeriodState(
        notice_id=notice_id,
        required_days=5,
        started_at=datetime.now(UTC) - timedelta(days=2),
        elapsed=False,
    )


@pytest.fixture
def paused_waiting_period() -> MockWaitingPeriodState:
    """Create a paused waiting period (dispute in progress)."""
    notice_id = uuid4()
    started = datetime.now(UTC) - timedelta(days=3)
    return MockWaitingPeriodState(
        notice_id=notice_id,
        required_days=5,
        started_at=started,
        elapsed=False,
        paused_at=datetime.now(UTC) - timedelta(days=1),
        resumed_at=None,
    )


@pytest.fixture
def resumed_waiting_period() -> MockWaitingPeriodState:
    """Create a resumed waiting period."""
    notice_id = uuid4()
    started = datetime.now(UTC) - timedelta(days=10)
    return MockWaitingPeriodState(
        notice_id=notice_id,
        required_days=5,
        started_at=started,
        elapsed=True,
        paused_at=datetime.now(UTC) - timedelta(days=5),
        resumed_at=datetime.now(UTC) - timedelta(days=4),
    )


# =============================================================================
# Authorization Fixtures
# =============================================================================


@pytest.fixture
def preparer_id() -> UUID:
    """Fixed preparer ID for SoD tests."""
    return uuid4()


@pytest.fixture
def approver_id() -> UUID:
    """Fixed approver ID for SoD tests."""
    return uuid4()


@pytest.fixture
def approvals_list() -> list[MockApproval]:
    """List of distinct approvals."""
    return [MockApproval(approver_id=uuid4()) for _ in range(3)]


@pytest.fixture
def clearance_levels() -> list[str]:
    """Standard clearance level ordering."""
    return ["public", "internal", "confidential", "restricted"]


# =============================================================================
# Timestamp Fixtures
# =============================================================================


@pytest.fixture
def utc_now() -> datetime:
    """Current UTC time."""
    return datetime.now(UTC)


@pytest.fixture
def past_timestamp() -> datetime:
    """Timestamp in the past (1 hour ago)."""
    return datetime.now(UTC) - timedelta(hours=1)


@pytest.fixture
def future_timestamp() -> datetime:
    """Timestamp in the future (1 hour ahead)."""
    return datetime.now(UTC) + timedelta(hours=1)


@pytest.fixture
def fresh_evidence_timestamp() -> datetime:
    """Timestamp for fresh evidence (12 hours ago)."""
    return datetime.now(UTC) - timedelta(hours=12)


@pytest.fixture
def stale_evidence_timestamp() -> datetime:
    """Timestamp for stale evidence (48 hours ago)."""
    return datetime.now(UTC) - timedelta(hours=48)
