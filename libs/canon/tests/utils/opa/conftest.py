"""Shared fixtures for OPA tests.

Provides common fixtures for policy testing including:
- Mock implementations (EvidenceStore)
- Sample data factories
- Common utilities
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from canon.enforcement.types import EnforcementLevel
from canon.utils.opa.orchestrator import EvidenceStore
from canon.utils.opa.resolver import PolicyIndex, PolicyIndexEntry

# =============================================================================
# Mock Implementations
# =============================================================================


class MockEvidenceStore(EvidenceStore):
    """Mock evidence store for testing."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    def add_evidence(
        self,
        evidence_type: str,
        selector_key: str,
        data: dict[str, Any],
    ) -> None:
        """Add mock evidence."""
        key = f"{evidence_type}:{selector_key}"
        self._data[key] = data

    async def get_latest(
        self,
        evidence_type: str,
        selector: dict[str, Any],
        project: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Get mock evidence."""
        for sel_key, sel_val in selector.items():
            key = f"{evidence_type}:{sel_val}"
            if key in self._data:
                data = self._data[key]
                if project:
                    return {k: v for k, v in data.items() if k in project}
                return data
        return None


# =============================================================================
# Common Fixtures
# =============================================================================


@pytest.fixture
def fixed_now() -> datetime:
    """Fixed timestamp for deterministic testing."""
    from datetime import UTC

    return datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_tenant_id():
    """Return a sample tenant UUID."""
    return uuid4()


@pytest.fixture
def mock_evidence_store() -> MockEvidenceStore:
    """Create a mock evidence store."""
    return MockEvidenceStore()


# =============================================================================
# Policy Fixtures
# =============================================================================


@pytest.fixture
def sample_policy_entry():
    """Factory for creating PolicyIndexEntry instances."""

    def _create(
        policy_id: str = "test_policy",
        rego_package: str = "canon.test.policy",
        enforcement: EnforcementLevel = EnforcementLevel.HARD_MANDATORY,
        authority: str = "STATUTORY",
        jurisdictions: tuple[str, ...] = ("US-NYC",),
        actions: tuple[str, ...] = ("adverse_action",),
        effective_from: datetime | None = None,
        effective_until: datetime | None = None,
        legal_citation: str | None = "Test Citation",
        priority: int = 0,
        prerequisites: tuple[str, ...] = (),
        excludes: tuple[str, ...] = (),
        parameters: dict[str, Any] | None = None,
    ) -> PolicyIndexEntry:
        return PolicyIndexEntry(
            policy_id=policy_id,
            rego_package=rego_package,
            enforcement=enforcement,
            authority=authority,
            jurisdictions=jurisdictions,
            actions=actions,
            effective_from=effective_from,
            effective_until=effective_until,
            legal_citation=legal_citation,
            priority=priority,
            prerequisites=prerequisites,
            excludes=excludes,
            parameters=parameters or {},
        )

    return _create


@pytest.fixture
def sample_index(sample_policy_entry):
    """Create a sample PolicyIndex with test policies."""
    index = PolicyIndex()

    # NYC Fair Chance - adverse action
    index.add(
        sample_policy_entry(
            policy_id="nyc_fair_chance_waiting",
            rego_package="canon.statutory.us_nyc.fair_chance.waiting_period",
            jurisdictions=("US-NYC",),
            actions=("adverse_action", "rescind_offer"),
            legal_citation="NYC Admin Code §8-107(11-a)(2)(c)",
            parameters={"required_waiting_days": 5},
        )
    )

    # NYC LL144 - bias audit
    index.add(
        sample_policy_entry(
            policy_id="nyc_ll144_bias_audit",
            rego_package="canon.statutory.us_nyc.ll144.bias_audit",
            jurisdictions=("US-NYC",),
            actions=("use_aedt", "screen_with_ai"),
            legal_citation="NYC Admin Code §20-871(b)(1)",
            parameters={"max_audit_age_days": 365},
        )
    )

    # Federal FCRA
    index.add(
        sample_policy_entry(
            policy_id="fcra_disclosure",
            rego_package="canon.statutory.us_federal.fcra.disclosure",
            jurisdictions=("US",),
            actions=("background_check",),
            legal_citation="15 USC §1681b(b)(2)(A)",
        )
    )

    return index


@pytest.fixture
def sample_charter(sample_tenant_id):
    """Create a mock Charter for testing.

    Uses MagicMock to avoid pydantic FK resolution issues in tests.
    """
    charter = MagicMock()
    charter.tenant_id = sample_tenant_id
    charter.version = "1.0.0"
    charter.policy_ids = ["nyc_fair_chance_waiting", "nyc_ll144_bias_audit"]
    charter.constraints = []

    def is_effective(at=None):
        return True

    charter.is_effective = is_effective
    return charter
