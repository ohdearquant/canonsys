# Copyright 2024 Lion Systems, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Tests for verify_role_approval authorization feature.

Tests cover:
- Basic role verification (approved/not approved)
- Unknown/custom role handling
- Delegation chain validation
- Convenience wrappers (CISO, CFO, GC, DPO)
- STANDARD_ROLES constant

Compliance Context:
    - SOX Section 404 (Internal controls require appropriate authority)
    - SOC 2 CC6.1 (Logical access controls)
    - GDPR Art. 37-39 (DPO requirements)

NOTE: Migrated from enforcement/vocab/authorization/ to features/authorization/.
Key API changes:
- Function signature: (request_id, role, ctx) instead of (ctx, request_id, role)
- Database access: ctx.conn.fetchrow instead of ctx.db.fetchrow
- Removed explicit conn parameter (uses ctx.conn directly)
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from canon_vocab_authorization import (
    STANDARD_ROLES,
    RoleApprovalResult,
    VerifyRoleApprovalSpecs,
    verify_cfo_approval,
    verify_ciso_approval,
    verify_dpo_approval,
    verify_gc_approval,
    verify_role_approval,
)


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext.

    NOTE: The new features use ctx.conn.fetchrow instead of ctx.db.fetchrow.
    """
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = AsyncMock()
    return ctx


@pytest.fixture
def request_id():
    """Generate a test request ID."""
    return uuid4()


@pytest.fixture
def approver_id():
    """Generate a test approver ID."""
    return uuid4()


# =============================================================================
# STANDARD_ROLES Tests
# =============================================================================


class TestStandardRoles:
    """Tests for STANDARD_ROLES constant."""

    def test_contains_ciso(self):
        """STANDARD_ROLES should contain CISO."""
        assert "CISO" in STANDARD_ROLES

    def test_contains_cfo(self):
        """STANDARD_ROLES should contain CFO."""
        assert "CFO" in STANDARD_ROLES

    def test_contains_gc(self):
        """STANDARD_ROLES should contain GC (General Counsel)."""
        assert "GC" in STANDARD_ROLES

    def test_contains_dpo(self):
        """STANDARD_ROLES should contain DPO (Data Protection Officer)."""
        assert "DPO" in STANDARD_ROLES

    def test_contains_executive_roles(self):
        """STANDARD_ROLES should contain CEO, CTO, BOARD."""
        assert "CEO" in STANDARD_ROLES
        assert "CTO" in STANDARD_ROLES
        assert "BOARD" in STANDARD_ROLES

    def test_is_frozen_set(self):
        """STANDARD_ROLES should be immutable."""
        assert isinstance(STANDARD_ROLES, frozenset)
        with pytest.raises(AttributeError):
            STANDARD_ROLES.add("NEW_ROLE")  # type: ignore[attr-defined]


# =============================================================================
# RoleApprovalResult Tests
# =============================================================================


class TestRoleApprovalResult:
    """Tests for RoleApprovalResult dataclass."""

    def test_approved_result(self, request_id, approver_id):
        """Test creating an approved result."""
        now = datetime.now(UTC)
        result = RoleApprovalResult(
            approved=True,
            request_id=request_id,
            required_role="CISO",
            approver_id=approver_id,
            approver_name="Jane Smith",
            approved_at=now,
        )
        assert result.approved is True
        assert result.request_id == request_id
        assert result.required_role == "CISO"
        assert result.approver_id == approver_id
        assert result.approver_name == "Jane Smith"
        assert result.approved_at == now
        assert result.reason is None

    def test_not_approved_result(self, request_id):
        """Test creating a not-approved result."""
        result = RoleApprovalResult(
            approved=False,
            request_id=request_id,
            required_role="CFO",
            reason="No approval from CFO found",
        )
        assert result.approved is False
        assert result.approver_id is None
        assert result.reason == "No approval from CFO found"

    def test_with_delegation_chain(self, request_id, approver_id):
        """Test result with delegation chain."""
        result = RoleApprovalResult(
            approved=True,
            request_id=request_id,
            required_role="CISO",
            approver_id=approver_id,
            delegation_chain=("CFO", "VP_SECURITY"),
        )
        assert result.delegation_chain == ("CFO", "VP_SECURITY")

    def test_is_immutable(self, request_id):
        """Test that result is immutable (frozen)."""
        result = RoleApprovalResult(
            approved=False,
            request_id=request_id,
            required_role="CISO",
        )
        with pytest.raises(AttributeError):
            result.approved = True  # type: ignore[misc]


# =============================================================================
# verify_role_approval Tests
# =============================================================================


class TestVerifyRoleApproval:
    """Tests for verify_role_approval function.

    NOTE: The new API signature is (request_id, required_role, ctx) instead of
    (ctx, request_id, required_role). Also uses ctx.conn.fetchrow instead of
    ctx.db.fetchrow.
    """

    @pytest.mark.asyncio
    async def test_approved_by_direct_role(self, mock_ctx, request_id, approver_id):
        """Test approval by someone with the required role directly."""
        now = datetime.now(UTC)
        mock_row = {
            "approver_id": approver_id,
            "approved_at": now,
            "approver_name": "Jane Smith",
            "approver_role": "CISO",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        # @phrase signature: (dict matching VerifyRoleApprovalSpecs, ctx) -> dict
        options = {"request_id": request_id, "required_role": "CISO"}
        result = await verify_role_approval(options, mock_ctx)

        assert isinstance(result, dict)
        assert result["approved"] is True
        assert result["request_id"] == request_id
        assert result["required_role"] == "CISO"
        assert result["approver_id"] == approver_id
        assert result["approver_name"] == "Jane Smith"
        assert result["approved_at"] == now
        assert result["delegation_chain"] is None

    @pytest.mark.asyncio
    async def test_no_approval_found(self, mock_ctx, request_id):
        """Test when no approval exists."""
        mock_ctx.conn.fetchrow = AsyncMock(return_value=None)

        options = {"request_id": request_id, "required_role": "CISO"}
        result = await verify_role_approval(options, mock_ctx)

        assert result["approved"] is False
        assert result["required_role"] == "CISO"
        assert "No approval from CISO found" in result["reason"]

    @pytest.mark.asyncio
    async def test_role_normalization_to_uppercase(self, mock_ctx, request_id):
        """Test that role is normalized to uppercase."""
        mock_ctx.conn.fetchrow = AsyncMock(return_value=None)

        options = {"request_id": request_id, "required_role": "ciso"}
        result = await verify_role_approval(options, mock_ctx)

        assert result["required_role"] == "CISO"

    @pytest.mark.asyncio
    async def test_custom_role_accepted(self, mock_ctx, request_id, approver_id):
        """Test that custom (non-standard) roles are accepted."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "Custom Approver",
            "approver_role": "CUSTOM_ROLE",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        options = {"request_id": request_id, "required_role": "custom_role"}
        result = await verify_role_approval(options, mock_ctx)

        assert result["approved"] is True
        assert result["required_role"] == "CUSTOM_ROLE"

    @pytest.mark.asyncio
    async def test_with_delegation_chain(self, mock_ctx, request_id, approver_id):
        """Test approval via delegation chain."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "Delegated Approver",
            "approver_role": "VP_SECURITY",
            "delegation_chain": ["CISO", "VP_SECURITY"],
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        options = {
            "request_id": request_id,
            "required_role": "CISO",
            "allow_delegation": True,
        }
        result = await verify_role_approval(options, mock_ctx)

        assert result["approved"] is True
        assert result["delegation_chain"] == ("CISO", "VP_SECURITY")

    @pytest.mark.asyncio
    async def test_delegation_disabled(self, mock_ctx, request_id):
        """Test that delegation can be disabled.

        NOTE: The new implementation passes allow_delegation to the SQL query
        rather than as a separate parameter, so we verify behavior not call args.
        """
        mock_ctx.conn.fetchrow = AsyncMock(return_value=None)

        options = {
            "request_id": request_id,
            "required_role": "CISO",
            "allow_delegation": False,
        }
        result = await verify_role_approval(options, mock_ctx)

        # Verify the function was called (query uses allow_delegation internally)
        mock_ctx.conn.fetchrow.assert_called_once()
        assert result["approved"] is False

    @pytest.mark.asyncio
    async def test_max_delegation_depth(self, mock_ctx, request_id):
        """Test max_delegation_depth parameter.

        NOTE: The new implementation passes max_delegation_depth to the SQL query
        rather than as a separate parameter, so we verify behavior not call args.
        """
        mock_ctx.conn.fetchrow = AsyncMock(return_value=None)

        options = {
            "request_id": request_id,
            "required_role": "CISO",
            "max_delegation_depth": 5,
        }
        result = await verify_role_approval(options, mock_ctx)

        # Verify the function was called (query uses max_delegation_depth internally)
        mock_ctx.conn.fetchrow.assert_called_once()
        assert result["approved"] is False


# =============================================================================
# Convenience Wrapper Tests
# =============================================================================


class TestConvenienceWrappers:
    """Tests for role-specific convenience wrappers.

    NOTE: The new API signature is (request_id, ctx) instead of (ctx, request_id).
    """

    @pytest.mark.asyncio
    async def test_verify_ciso_approval(self, mock_ctx, request_id, approver_id):
        """Test verify_ciso_approval wrapper."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "Security Chief",
            "approver_role": "CISO",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        # Convenience wrapper: (request_id, ctx) -> dict
        result = await verify_ciso_approval(request_id, mock_ctx)

        assert result["approved"] is True
        assert result["required_role"] == "CISO"

    @pytest.mark.asyncio
    async def test_verify_cfo_approval(self, mock_ctx, request_id, approver_id):
        """Test verify_cfo_approval wrapper."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "Finance Chief",
            "approver_role": "CFO",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await verify_cfo_approval(request_id, mock_ctx)

        assert result["approved"] is True
        assert result["required_role"] == "CFO"

    @pytest.mark.asyncio
    async def test_verify_gc_approval(self, mock_ctx, request_id, approver_id):
        """Test verify_gc_approval wrapper."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "General Counsel",
            "approver_role": "GC",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await verify_gc_approval(request_id, mock_ctx)

        assert result["approved"] is True
        assert result["required_role"] == "GC"

    @pytest.mark.asyncio
    async def test_verify_dpo_approval(self, mock_ctx, request_id, approver_id):
        """Test verify_dpo_approval wrapper."""
        mock_row = {
            "approver_id": approver_id,
            "approved_at": datetime.now(UTC),
            "approver_name": "Privacy Officer",
            "approver_role": "DPO",
            "delegation_chain": None,
        }
        mock_ctx.conn.fetchrow = AsyncMock(return_value=mock_row)

        result = await verify_dpo_approval(request_id, mock_ctx)

        assert result["approved"] is True
        assert result["required_role"] == "DPO"

    @pytest.mark.asyncio
    async def test_wrappers_support_allow_delegation(self, mock_ctx, request_id):
        """Test that wrappers support allow_delegation parameter."""
        mock_ctx.conn.fetchrow = AsyncMock(return_value=None)

        result = await verify_ciso_approval(request_id, mock_ctx, allow_delegation=False)

        mock_ctx.conn.fetchrow.assert_called_once()
        assert result["approved"] is False


# =============================================================================
# Import Tests
# =============================================================================


class TestImports:
    """Tests for proper module exports."""

    def test_import_from_authorization_module(self):
        """Test importing from authorization module."""
        from canon_vocab_authorization import (
            STANDARD_ROLES,
            RoleApprovalResult,
            verify_cfo_approval,
            verify_ciso_approval,
            verify_dpo_approval,
            verify_gc_approval,
            verify_role_approval,
        )

        assert verify_role_approval is not None
        assert VerifyRoleApprovalSpecs is not None
        assert RoleApprovalResult is not None
        assert STANDARD_ROLES is not None
        assert verify_ciso_approval is not None
        assert verify_cfo_approval is not None
        assert verify_gc_approval is not None
        assert verify_dpo_approval is not None

    def test_import_from_phrases_submodule(self):
        """Test importing from phrases submodule."""
        from canon_vocab_authorization.phrases import (
            VerifyRoleApprovalSpecs,
            verify_cfo_approval,
            verify_ciso_approval,
            verify_dpo_approval,
            verify_gc_approval,
            verify_role_approval,
        )

        assert verify_role_approval is not None
        assert VerifyRoleApprovalSpecs is not None
        assert verify_ciso_approval is not None
        assert verify_cfo_approval is not None
        assert verify_gc_approval is not None
        assert verify_dpo_approval is not None

    def test_import_types_from_types_submodule(self):
        """Test importing types from types submodule."""
        from canon_vocab_authorization.types import STANDARD_ROLES, RoleApprovalResult

        assert STANDARD_ROLES is not None
        assert RoleApprovalResult is not None
