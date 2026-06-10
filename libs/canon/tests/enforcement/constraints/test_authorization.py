"""Tests for authorization constraint functions.

Tests cover:
- preparer_must_not_be_approver: Segregation of Duties validation
- dual_approval_must_be_present: Dual approval requirement
- clearance_must_be_sufficient: Clearance level validation
- approvers_must_be_distinct: Distinct approver validation

Constraint Semantics:
    Each constraint returns None on success (invariant holds) or raises
    a typed exception on failure (invariant violated).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from canon.enforcement.constraints import (
    approvers_must_be_distinct,
    clearance_must_be_sufficient,
    dual_approval_must_be_present,
    preparer_must_not_be_approver,
)
from canon.enforcement.exceptions import (
    ClearanceInsufficientError,
    DualApprovalMissingError,
    SoDViolationError,
)

from .conftest import MockApproval

# =============================================================================
# preparer_must_not_be_approver Tests
# =============================================================================


class TestPreparerMustNotBeApprover:
    """Tests for preparer_must_not_be_approver constraint (SoD)."""

    def test_different_identities_succeeds(self, preparer_id, approver_id):
        """Test different preparer and approver passes SoD check."""
        result = preparer_must_not_be_approver(preparer_id, approver_id)
        assert result is None

    def test_same_identity_raises(self, preparer_id):
        """Test same person as preparer and approver raises SoDViolationError."""
        with pytest.raises(SoDViolationError) as exc_info:
            preparer_must_not_be_approver(preparer_id, preparer_id)

        exc = exc_info.value
        assert exc.identity_id == preparer_id
        assert exc.role_a == "preparer"
        assert exc.role_b == "approver"
        assert "SOX Section 404" in exc.regulation

    def test_multiple_unique_pairs(self):
        """Test multiple unique preparer/approver pairs all pass."""
        for _ in range(10):
            preparer = uuid4()
            approver = uuid4()
            result = preparer_must_not_be_approver(preparer, approver)
            assert result is None

    def test_swapped_roles_same_people_succeeds(self, preparer_id, approver_id):
        """Test swapping roles between different people still passes."""
        # A prepares, B approves
        result1 = preparer_must_not_be_approver(preparer_id, approver_id)
        assert result1 is None

        # B prepares, A approves (swapped)
        result2 = preparer_must_not_be_approver(approver_id, preparer_id)
        assert result2 is None


# =============================================================================
# dual_approval_must_be_present Tests
# =============================================================================


class TestDualApprovalMustBePresent:
    """Tests for dual_approval_must_be_present constraint."""

    def test_two_approvals_succeeds(self, approvals_list):
        """Test two or more approvals passes dual approval check."""
        result = dual_approval_must_be_present(approvals_list[:2], min_required=2)
        assert result is None

    def test_more_than_required_succeeds(self, approvals_list):
        """Test more than minimum approvals still passes."""
        result = dual_approval_must_be_present(approvals_list, min_required=2)
        assert result is None

    def test_one_approval_raises(self, approvals_list):
        """Test single approval raises DualApprovalMissingError."""
        with pytest.raises(DualApprovalMissingError) as exc_info:
            dual_approval_must_be_present(approvals_list[:1], min_required=2)

        exc = exc_info.value
        assert exc.approvals_present == 1
        assert exc.approvals_required == 2
        assert "SOX Section 302" in exc.regulation

    def test_zero_approvals_raises(self):
        """Test no approvals raises DualApprovalMissingError."""
        with pytest.raises(DualApprovalMissingError) as exc_info:
            dual_approval_must_be_present([], min_required=2)

        assert exc_info.value.approvals_present == 0

    def test_default_min_required_is_two(self, approvals_list):
        """Test default min_required is 2."""
        # Should pass with 2 approvals using default
        result = dual_approval_must_be_present(approvals_list[:2])
        assert result is None

        # Should fail with 1 approval using default
        with pytest.raises(DualApprovalMissingError) as exc_info:
            dual_approval_must_be_present(approvals_list[:1])

        assert exc_info.value.approvals_required == 2

    def test_custom_min_required(self, approvals_list):
        """Test custom min_required value."""
        # Need 3 approvals
        result = dual_approval_must_be_present(approvals_list, min_required=3)
        assert result is None

        # Only have 2 but need 3
        with pytest.raises(DualApprovalMissingError) as exc_info:
            dual_approval_must_be_present(approvals_list[:2], min_required=3)

        assert exc_info.value.approvals_required == 3

    def test_single_approval_min_one(self):
        """Test min_required=1 passes with single approval."""
        single_approval = [MockApproval(approver_id=uuid4())]
        result = dual_approval_must_be_present(single_approval, min_required=1)
        assert result is None

    def test_action_type_in_error(self, approvals_list):
        """Test error contains action type context."""
        with pytest.raises(DualApprovalMissingError) as exc_info:
            dual_approval_must_be_present(approvals_list[:1])

        assert exc_info.value.action_type == "operation_requiring_approval"


# =============================================================================
# clearance_must_be_sufficient Tests
# =============================================================================


class TestClearanceMustBeSufficient:
    """Tests for clearance_must_be_sufficient constraint."""

    def test_equal_clearance_succeeds(self, clearance_levels):
        """Test equal clearance level passes."""
        result = clearance_must_be_sufficient("confidential", "confidential", clearance_levels)
        assert result is None

    def test_higher_clearance_succeeds(self, clearance_levels):
        """Test higher clearance than required passes."""
        result = clearance_must_be_sufficient("restricted", "internal", clearance_levels)
        assert result is None

    def test_lower_clearance_raises(self, clearance_levels):
        """Test lower clearance than required raises ClearanceInsufficientError."""
        with pytest.raises(ClearanceInsufficientError) as exc_info:
            clearance_must_be_sufficient("internal", "confidential", clearance_levels)

        exc = exc_info.value
        assert exc.required_level == "confidential"
        assert exc.actual_level == "internal"
        assert "PCI DSS 7.1" in exc.regulation

    def test_lowest_clearance_for_public(self, clearance_levels):
        """Test lowest clearance (public) can access public resources."""
        result = clearance_must_be_sufficient("public", "public", clearance_levels)
        assert result is None

    def test_highest_clearance_can_access_all(self, clearance_levels):
        """Test highest clearance can access all levels."""
        for level in clearance_levels:
            result = clearance_must_be_sufficient("restricted", level, clearance_levels)
            assert result is None

    def test_public_cannot_access_restricted(self, clearance_levels):
        """Test public clearance cannot access any restricted level."""
        for level in ["internal", "confidential", "restricted"]:
            with pytest.raises(ClearanceInsufficientError):
                clearance_must_be_sufficient("public", level, clearance_levels)

    def test_invalid_actor_level_raises_value_error(self, clearance_levels):
        """Test invalid actor level raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            clearance_must_be_sufficient("super_admin", "internal", clearance_levels)

        assert "super_admin" in str(exc_info.value)
        assert "not in level_order" in str(exc_info.value)

    def test_invalid_required_level_raises_value_error(self, clearance_levels):
        """Test invalid required level raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            clearance_must_be_sufficient("internal", "top_secret", clearance_levels)

        assert "top_secret" in str(exc_info.value)

    def test_custom_level_order(self):
        """Test custom clearance level ordering."""
        custom_levels = ["bronze", "silver", "gold", "platinum"]

        # Gold can access silver
        result = clearance_must_be_sufficient("gold", "silver", custom_levels)
        assert result is None

        # Silver cannot access gold
        with pytest.raises(ClearanceInsufficientError):
            clearance_must_be_sufficient("silver", "gold", custom_levels)

    def test_single_level_system(self):
        """Test clearance with single level."""
        single_level = ["standard"]
        result = clearance_must_be_sufficient("standard", "standard", single_level)
        assert result is None


# =============================================================================
# approvers_must_be_distinct Tests
# =============================================================================


class TestApproversMustBeDistinct:
    """Tests for approvers_must_be_distinct constraint."""

    def test_all_distinct_succeeds(self):
        """Test all distinct approvers passes."""
        approvers = [uuid4(), uuid4(), uuid4()]
        result = approvers_must_be_distinct(approvers)
        assert result is None

    def test_duplicate_raises(self):
        """Test duplicate approver raises SoDViolationError."""
        same_id = uuid4()
        approvers = [uuid4(), same_id, uuid4(), same_id]

        with pytest.raises(SoDViolationError) as exc_info:
            approvers_must_be_distinct(approvers)

        exc = exc_info.value
        assert exc.identity_id == same_id
        assert exc.role_a == "approver"
        assert exc.role_b == "approver"

    def test_empty_list_succeeds(self):
        """Test empty approver list passes (trivially distinct)."""
        result = approvers_must_be_distinct([])
        assert result is None

    def test_single_approver_succeeds(self):
        """Test single approver passes (trivially distinct)."""
        result = approvers_must_be_distinct([uuid4()])
        assert result is None

    def test_two_identical_raises(self):
        """Test two identical approvers raises."""
        same_id = uuid4()
        with pytest.raises(SoDViolationError):
            approvers_must_be_distinct([same_id, same_id])

    def test_first_duplicate_is_caught(self):
        """Test the first duplicate in sequence is the one reported."""
        id1 = uuid4()
        id2 = uuid4()
        # id1 appears at index 0 and 2
        approvers = [id1, id2, id1]

        with pytest.raises(SoDViolationError) as exc_info:
            approvers_must_be_distinct(approvers)

        assert exc_info.value.identity_id == id1

    def test_many_approvers(self):
        """Test with many distinct approvers."""
        approvers = [uuid4() for _ in range(100)]
        result = approvers_must_be_distinct(approvers)
        assert result is None


# =============================================================================
# Constraint Composition Tests
# =============================================================================


class TestAuthorizationComposition:
    """Tests for composing multiple authorization constraints."""

    def test_all_authorization_checks_pass(self, preparer_id, approver_id, clearance_levels):
        """Test all authorization constraints pass in sequence."""
        # Create approvals from different people
        approvals = [
            MockApproval(approver_id=approver_id),
            MockApproval(approver_id=uuid4()),
        ]

        # If all execute without raising, all invariants hold
        preparer_must_not_be_approver(preparer_id, approver_id)
        dual_approval_must_be_present(approvals, min_required=2)
        clearance_must_be_sufficient("confidential", "internal", clearance_levels)
        approvers_must_be_distinct([a.approver_id for a in approvals])
        # Reaching here means all authorization requirements are satisfied

    def test_fails_at_first_violation(self, preparer_id, clearance_levels):
        """Test composition fails at first violation."""
        with pytest.raises(SoDViolationError):
            preparer_must_not_be_approver(preparer_id, preparer_id)
            # Remaining constraints never execute
            clearance_must_be_sufficient("internal", "public", clearance_levels)

    def test_sod_with_dual_approval(self, preparer_id):
        """Test SoD combined with dual approval - realistic scenario."""
        # Preparer cannot be one of the approvers
        approver1 = uuid4()
        approver2 = uuid4()
        approvals = [
            MockApproval(approver_id=approver1),
            MockApproval(approver_id=approver2),
        ]

        # Check preparer is not either approver
        preparer_must_not_be_approver(preparer_id, approver1)
        preparer_must_not_be_approver(preparer_id, approver2)

        # Check dual approval
        dual_approval_must_be_present(approvals)

        # Check approvers are distinct
        approvers_must_be_distinct([approver1, approver2])

    def test_sod_with_dual_approval_violation(self, preparer_id):
        """Test preparer is also an approver - violation."""
        approver1 = preparer_id  # SoD violation - preparer is approver
        approver2 = uuid4()
        approvals = [
            MockApproval(approver_id=approver1),
            MockApproval(approver_id=approver2),
        ]

        # Dual approval passes (2 approvals)
        dual_approval_must_be_present(approvals)

        # But SoD fails
        with pytest.raises(SoDViolationError):
            preparer_must_not_be_approver(preparer_id, approver1)
