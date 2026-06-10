"""Test fixtures for consent feature tests."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    return ctx
