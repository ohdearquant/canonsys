"""Shared fixtures for enforcement catalog gate tests.

Provides common fixtures for testing parameterized gates:
- RequestContext fixtures with various configurations
- Tenant, actor, subject IDs
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from canon.enforcement import RequestContext


@pytest.fixture
def tenant_id():
    """Standard tenant ID for tests."""
    return uuid4()


@pytest.fixture
def actor_id():
    """Standard actor ID for tests."""
    return uuid4()


@pytest.fixture
def subject_id():
    """Standard subject ID for tests."""
    return uuid4()


@pytest.fixture
def base_context(tenant_id, actor_id, subject_id):
    """Base RequestContext with all IDs populated."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        subject_id=subject_id,
    )


@pytest.fixture
def context_no_subject(tenant_id, actor_id):
    """Context without subject_id for testing consent edge cases."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        subject_id=None,
    )


@pytest.fixture
def context_no_actor(tenant_id, subject_id):
    """Context without actor_id for testing authorization edge cases."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=None,
        subject_id=subject_id,
    )


@pytest.fixture
def context_with_jurisdictions(tenant_id, actor_id, subject_id):
    """Context with jurisdiction scope."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        subject_id=subject_id,
        jurisdictions=("US-NYC", "US-NY", "US-FEDERAL"),
    )


@pytest.fixture
def context_no_jurisdictions(tenant_id, actor_id, subject_id):
    """Context without jurisdiction scope."""
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        subject_id=subject_id,
        jurisdictions=(),
    )
