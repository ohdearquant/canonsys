"""Test fixtures for corporate feature tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

if TYPE_CHECKING:
    from uuid import UUID


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    return ctx


@pytest.fixture
def deal_id() -> UUID:
    """Create a test deal ID."""
    return uuid4()


@pytest.fixture
def finding_ids() -> list[UUID]:
    """Create test finding IDs."""
    return [uuid4() for _ in range(5)]


@pytest.fixture
def condition_ids() -> list[UUID]:
    """Create test condition IDs."""
    return [uuid4() for _ in range(4)]


@pytest.fixture
def carve_out_id() -> UUID:
    """Create a test carve-out ID."""
    return uuid4()


@pytest.fixture
def now() -> datetime:
    """Current UTC datetime for testing."""
    return datetime.now(UTC)
