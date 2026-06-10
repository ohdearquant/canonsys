"""Shared fixtures for Charter DSL tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from canon.dsl.catalog import SchemaCatalog

# -----------------------------------------------------------------
# Mock types for schema catalog
# -----------------------------------------------------------------


@dataclass(frozen=True)
class PIPReport:
    pass


@dataclass(frozen=True)
class EligibilityReport:
    pass


@dataclass(frozen=True)
class TerminationCertificate:
    pass


# -----------------------------------------------------------------
# Mock registries
# -----------------------------------------------------------------


class MockFeatureRegistry:
    """Feature registry with configurable known features."""

    def __init__(self, known: set[str] | None = None) -> None:
        self._known = known or set()

    def get_feature(self, name: str) -> object | None:
        if name in self._known:
            return object()  # Truthy sentinel
        return None


class MockPolicyRegistry:
    """Policy registry with configurable known policies."""

    def __init__(self, known: set[str] | None = None) -> None:
        self._known = known or set()

    def has_policy(self, policy_id: str) -> bool:
        return policy_id in self._known


class MockPackageRegistry:
    """Package registry with configurable packages and their phrases."""

    def __init__(self, packages: dict[str, set[str]] | None = None) -> None:
        self._packages = packages or {}

    def has_package(self, name: str) -> bool:
        return name in self._packages

    def get_package_phrases(self, name: str) -> frozenset[str] | None:
        if name not in self._packages:
            return None
        return frozenset(self._packages[name])


# -----------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------


@pytest.fixture()
def mock_catalog() -> SchemaCatalog:
    """Schema catalog with canon.hr@2026.01 types."""
    catalog = SchemaCatalog()
    catalog.register("canon.hr", "2026.01", "PIPReport", PIPReport)
    catalog.register("canon.hr", "2026.01", "EligibilityReport", EligibilityReport)
    catalog.register("canon.hr", "2026.01", "TerminationCertificate", TerminationCertificate)
    return catalog


@pytest.fixture()
def mock_features() -> MockFeatureRegistry:
    """Feature registry with standard PIP workflow features."""
    return MockFeatureRegistry(
        known={
            "verify_consent",
            "check_er_clearance",
            "certify_fcra_notice",
            "check_waiting_period_elapsed",
            "certify_termination",
            "verify_identity",
            "save_evidence",
            "assess_eligibility",
            "evaluate_performance",
            "conduct_review",
            "generate_pip_report",
            "check_employment_status",
        }
    )


@pytest.fixture()
def mock_policies() -> MockPolicyRegistry:
    """Policy registry with standard policies."""
    return MockPolicyRegistry(
        known={
            "employment.termination",
            "employment.pip",
            "compliance.fcra",
        }
    )


@pytest.fixture()
def mock_packages() -> MockPackageRegistry:
    """Package registry with vocabulary packages."""
    return MockPackageRegistry(
        packages={
            "consent": {
                "verify_consent",
                "grant_consent",
                "revoke_consent",
            },
            "evidence": {
                "save_evidence",
                "verify_evidence",
                "bind_evidence",
            },
            "certification": {
                "certify_termination",
                "certify_fcra_notice",
                "certify_decision",
            },
            "identity": {
                "verify_identity",
                "check_mfa",
            },
            "compliance": {
                "check_er_clearance",
                "check_waiting_period_elapsed",
                "assess_eligibility",
                "evaluate_performance",
                "conduct_review",
                "check_employment_status",
                "generate_pip_report",
            },
        }
    )


@pytest.fixture()
def sample_pip_charter() -> str:
    """Complete PIP charter DSL source text."""
    return """\
charter "Performance Improvement Plan" v1.0

schemas: canon.hr@2026.01

policies:
    - employment.pip
    - employment.termination

workflow pip_workflow:
    phase eligibility:
        require verify_consent("background_check")
        action assess_eligibility()
        output EligibilityReport

    phase review:
        require eligibility.passed
        action evaluate_performance()
        action conduct_review()
        output PIPReport

    phase decision:
        require review.passed
        action certify_termination()
        output TerminationCertificate
        certify immutable
        evidence termination_record

situations:
    when jurisdiction == "NYC":
        waiting_period 30..90 days
        require verify_consent("aedt_disclosure")

roles:
    hr_manager:
        actions: [assess_eligibility, evaluate_performance, conduct_review]
        break_glass: false
        requires_mfa: true
    legal_counsel:
        actions: [certify_termination]
        break_glass: true
        requires_mfa: true
"""


@pytest.fixture()
def minimal_charter() -> str:
    """Minimal valid charter source."""
    return """\
charter "Minimal" v0.1

workflow basic:
    phase step_one:
        action verify_consent()
"""
