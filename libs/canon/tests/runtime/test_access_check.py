"""Tests for check_document_access and record_document_access."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from canon.runtime.grants import (
    AccessCheckResult,
    check_document_access,
    record_document_access,
)

USER_ID = UUID("00000000-0000-0000-0000-000000001000")
SUBJECT_ID = UUID("00000000-0000-0000-0000-000000010000")
TOKEN_ID = UUID("00000000-0000-0000-0000-000000099999")


class TestAccessCheckResult:
    def test_allowed(self):
        r = AccessCheckResult(
            allowed=True,
            token_id=TOKEN_ID,
            reason="Valid",
            document_type="resume",
            subject_id=SUBJECT_ID,
        )
        assert r.allowed is True
        assert r.token_id == TOKEN_ID

    def test_denied(self):
        r = AccessCheckResult(
            allowed=False,
            token_id=None,
            reason="No grant",
        )
        assert r.allowed is False
        assert r.token_id is None

    def test_to_dict(self):
        r = AccessCheckResult(
            allowed=True,
            token_id=TOKEN_ID,
            reason="Valid",
            document_type="resume",
            subject_id=SUBJECT_ID,
        )
        d = r.to_dict()
        assert d["allowed"] is True
        assert d["token_id"] == str(TOKEN_ID)
        assert d["document_type"] == "resume"

    def test_to_dict_none_fields(self):
        r = AccessCheckResult(allowed=False, token_id=None, reason="No grant")
        d = r.to_dict()
        assert d["token_id"] is None
        assert d["subject_id"] is None

    def test_frozen(self):
        r = AccessCheckResult(allowed=True, token_id=TOKEN_ID, reason="ok")
        with pytest.raises(AttributeError):
            r.allowed = False


class TestCheckDocumentAccess:
    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_valid_grant_returns_allowed(self, mock_fetch):
        mock_fetch.return_value = [
            {
                "id": TOKEN_ID,
                "status": "active",
                "expires_at": None,
                "workflow_instance_id": uuid4(),
            }
        ]

        result = await check_document_access(
            user_id=USER_ID,
            subject_id=SUBJECT_ID,
            document_type="resume",
            conn=AsyncMock(),
        )

        assert result.allowed is True
        assert result.token_id == TOKEN_ID
        assert result.document_type == "resume"

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_no_grant_returns_denied(self, mock_fetch):
        mock_fetch.return_value = []

        result = await check_document_access(
            user_id=USER_ID,
            subject_id=SUBJECT_ID,
            document_type="resume",
            conn=AsyncMock(),
        )

        assert result.allowed is False
        assert result.token_id is None
        assert "No valid grant" in result.reason

    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_query_parameters(self, mock_fetch):
        mock_fetch.return_value = []
        conn = AsyncMock()

        await check_document_access(
            user_id=USER_ID,
            subject_id=SUBJECT_ID,
            document_type="offer_letter",
            conn=conn,
        )

        # Verify fetch was called with correct params
        args = mock_fetch.call_args
        query = args[0][0]
        assert "grantee_id = $1" in query
        assert "subject_id = $2" in query
        assert "document_type = $3" in query
        assert args[0][1] == USER_ID
        assert args[0][2] == SUBJECT_ID
        assert args[0][3] == "offer_letter"


class TestRecordDocumentAccess:
    @pytest.mark.anyio
    @patch("canon.runtime.grants.fetch", new_callable=AsyncMock)
    async def test_updates_token(self, mock_fetch):
        mock_fetch.return_value = [{"id": TOKEN_ID}]
        conn = AsyncMock()

        await record_document_access(token_id=TOKEN_ID, conn=conn)

        args = mock_fetch.call_args
        query = args[0][0]
        assert "status = 'used'" in query
        assert "access_count = access_count + 1" in query
        assert args[0][2] == TOKEN_ID
