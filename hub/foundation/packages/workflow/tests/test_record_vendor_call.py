"""Tests for record_vendor_call workflow phrase.

Tests cover:
- Basic vendor call recording with success status
- Vendor call recording with failure status
- Input/output hash computation
- Evidence creation with correct metadata
- Optional subject_id handling
- Specs type validation

Compliance Context:
    - NYC LL144 (AEDT audit requirements)
    - ISO 27001 (Vendor management)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from canon_vocab_workflow.phrases.record_vendor_call import (
    RecordVendorCallSpecs,
    record_vendor_call,
)

from kron.utils import compute_hash


@pytest.fixture
def mock_ctx():
    """Create mock RequestContext."""
    ctx = AsyncMock()
    ctx.tenant_id = uuid4()
    ctx.actor_id = uuid4()
    ctx.conn = None
    return ctx


@pytest.fixture
def workflow_run_id():
    """Generate a test workflow run ID."""
    return uuid4()


@pytest.fixture
def step_evidence_id():
    """Generate a test step evidence ID."""
    return uuid4()


@pytest.fixture
def saved_evidence_id():
    """Generate a test saved evidence ID."""
    return uuid4()


# =============================================================================
# RecordVendorCallSpecs Tests
# =============================================================================


class TestRecordVendorCallSpecs:
    """Tests for RecordVendorCallSpecs Pydantic model."""

    def test_success_specs(self, saved_evidence_id, workflow_run_id, step_evidence_id):
        """Test creating specs for a successful vendor call."""
        specs = RecordVendorCallSpecs(
            workflow_run_id=workflow_run_id,
            step_evidence_id=step_evidence_id,
            vendor_code="checkr",
            config_hash="cfg123",
            input_data={"a": 1},
            output_data={"b": 2},
            duration_ms=1500,
            status="success",
            evidence_id=saved_evidence_id,
            input_hash="abc123",
            output_hash="def456",
            error_message=None,
        )
        assert specs.vendor_code == "checkr"
        assert specs.status == "success"
        assert specs.evidence_id == saved_evidence_id
        assert specs.input_hash == "abc123"
        assert specs.output_hash == "def456"
        assert specs.error_message is None

    def test_failure_specs(self, saved_evidence_id, workflow_run_id, step_evidence_id):
        """Test creating specs for a failed vendor call."""
        specs = RecordVendorCallSpecs(
            workflow_run_id=workflow_run_id,
            step_evidence_id=step_evidence_id,
            vendor_code="hireright",
            config_hash="cfg456",
            input_data={},
            output_data={},
            duration_ms=30000,
            status="failure",
            error_message="API timeout",
            evidence_id=saved_evidence_id,
            input_hash="abc123",
            output_hash="def456",
        )
        assert specs.status == "failure"
        assert specs.error_message == "API timeout"


# =============================================================================
# record_vendor_call Tests
# =============================================================================


class TestRecordVendorCall:
    """Tests for record_vendor_call phrase function.

    Note: We mock EvidenceContent and Evidence classes to avoid Pydantic
    model rebuilding issues with forward references in test environments.
    """

    @pytest.mark.asyncio
    async def test_records_successful_vendor_call(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test recording a successful vendor call."""
        input_data = {"candidate_id": "123", "check_type": "criminal"}
        output_data = {"status": "clear", "report_id": "rpt-456"}

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        mock_evidence_content = MagicMock()
        mock_evidence = MagicMock()

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-hash-123",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 1500,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                return_value=mock_evidence_content,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=mock_evidence,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ) as mock_save,
        ):
            result = await record_vendor_call(payload, mock_ctx)

        assert isinstance(result, dict)
        assert result["evidence_id"] == saved_evidence_id
        assert result["vendor_code"] == "checkr"
        assert result["status"] == "success"
        assert result["error_message"] is None
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_records_failed_vendor_call(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test recording a failed vendor call with error message."""
        input_data = {"candidate_id": "123"}
        output_data = {"error": "timeout"}

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "hireright",
            "config_hash": "cfg-hash-456",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 30000,
            "status": "failure",
            "error_message": "Vendor API timeout after 30s",
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result = await record_vendor_call(payload, mock_ctx)

        assert result["status"] == "failure"
        assert result["error_message"] == "Vendor API timeout after 30s"

    @pytest.mark.asyncio
    async def test_computes_input_and_output_hashes(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test that input and output data are hashed correctly."""
        input_data = {"key": "value1"}
        output_data = {"key": "value2"}

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-123",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 500,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.compute_hash",
                side_effect=["input-hash-abc", "output-hash-def"],
            ) as mock_hash,
        ):
            result = await record_vendor_call(payload, mock_ctx)

        assert result["input_hash"] == "input-hash-abc"
        assert result["output_hash"] == "output-hash-def"
        assert mock_hash.call_count == 2
        mock_hash.assert_any_call(input_data)
        mock_hash.assert_any_call(output_data)

    @pytest.mark.asyncio
    async def test_creates_evidence_with_correct_metadata(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test that evidence is created with correct vendor call metadata."""
        input_data = {"candidate": "abc"}
        output_data = {"result": "pass"}

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        captured_content_kwargs = None

        def capture_content(**kwargs):
            nonlocal captured_content_kwargs
            captured_content_kwargs = kwargs
            return MagicMock(**kwargs)

        captured_evidence_kwargs = None

        def capture_evidence(**kwargs):
            nonlocal captured_evidence_kwargs
            captured_evidence_kwargs = kwargs
            return MagicMock()

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "sterling",
            "config_hash": "cfg-789",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 2000,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                side_effect=capture_content,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                side_effect=capture_evidence,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            await record_vendor_call(payload, mock_ctx)

        # Verify EvidenceContent was called with correct kwargs
        assert captured_content_kwargs is not None
        assert captured_content_kwargs["tenant_id"] == mock_ctx.tenant_id
        assert captured_content_kwargs["evidence_type"] == "vendor.call.sterling"
        assert captured_content_kwargs["title"] == "Vendor call: sterling"
        assert captured_content_kwargs["source"] == "sterling"
        assert captured_content_kwargs["collected_by_id"] == mock_ctx.actor_id

        # Verify data payload
        data = captured_content_kwargs["data"]
        assert data["workflow_run_id"] == str(workflow_run_id)
        assert data["step_evidence_id"] == str(step_evidence_id)
        assert data["vendor_code"] == "sterling"
        assert data["config_hash"] == "cfg-789"
        assert data["duration_ms"] == 2000
        assert data["status"] == "success"
        assert data["error_message"] is None

    @pytest.mark.asyncio
    async def test_with_optional_subject_id(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test recording vendor call with subject_id."""
        subject_id = uuid4()

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        captured_content_kwargs = None

        def capture_content(**kwargs):
            nonlocal captured_content_kwargs
            captured_content_kwargs = kwargs
            return MagicMock()

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-123",
            "input_data": {},
            "output_data": {},
            "duration_ms": 100,
            "subject_id": subject_id,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                side_effect=capture_content,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            await record_vendor_call(payload, mock_ctx)

        assert captured_content_kwargs["subject_id"] == subject_id

    @pytest.mark.asyncio
    async def test_without_subject_id(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test recording vendor call without subject_id (None)."""
        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        captured_content_kwargs = None

        def capture_content(**kwargs):
            nonlocal captured_content_kwargs
            captured_content_kwargs = kwargs
            return MagicMock()

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-123",
            "input_data": {},
            "output_data": {},
            "duration_ms": 100,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                side_effect=capture_content,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            await record_vendor_call(payload, mock_ctx)

        assert captured_content_kwargs["subject_id"] is None

    @pytest.mark.asyncio
    async def test_evidence_data_contains_hashes(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test that evidence data contains computed input/output hashes."""
        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        input_data = {"test": "input"}
        output_data = {"test": "output"}
        expected_input_hash = compute_hash(input_data)
        expected_output_hash = compute_hash(output_data)

        captured_content_kwargs = None

        def capture_content(**kwargs):
            nonlocal captured_content_kwargs
            captured_content_kwargs = kwargs
            return MagicMock()

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-123",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 100,
        }

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                side_effect=capture_content,
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            await record_vendor_call(payload, mock_ctx)

        data = captured_content_kwargs["data"]
        assert data["input_hash"] == expected_input_hash
        assert data["output_hash"] == expected_output_hash

    @pytest.mark.asyncio
    async def test_hash_determinism(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test that hashes are deterministic for same input."""
        input_data = {"key": "value", "number": 42}
        output_data = {"result": True}

        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_evidence_id": step_evidence_id,
            "vendor_code": "checkr",
            "config_hash": "cfg-123",
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": 100,
        }

        results = []
        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            for _ in range(3):
                result = await record_vendor_call(payload, mock_ctx)
                results.append(result)

        # All hashes should be identical
        assert all(r["input_hash"] == results[0]["input_hash"] for r in results)
        assert all(r["output_hash"] == results[0]["output_hash"] for r in results)

    @pytest.mark.asyncio
    async def test_different_inputs_produce_different_hashes(
        self, mock_ctx, workflow_run_id, step_evidence_id, saved_evidence_id
    ):
        """Test that different inputs produce different hashes."""
        mock_saved_evidence = MagicMock()
        mock_saved_evidence.id = saved_evidence_id

        with (
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.EvidenceContent",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.Evidence",
                return_value=MagicMock(),
            ),
            patch(
                "canon_vocab_workflow.phrases.record_vendor_call.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result1 = await record_vendor_call(
                {
                    "workflow_run_id": workflow_run_id,
                    "step_evidence_id": step_evidence_id,
                    "vendor_code": "checkr",
                    "config_hash": "cfg-123",
                    "input_data": {"x": 1},
                    "output_data": {"y": 1},
                    "duration_ms": 100,
                },
                mock_ctx,
            )
            result2 = await record_vendor_call(
                {
                    "workflow_run_id": workflow_run_id,
                    "step_evidence_id": step_evidence_id,
                    "vendor_code": "checkr",
                    "config_hash": "cfg-123",
                    "input_data": {"x": 2},
                    "output_data": {"y": 2},
                    "duration_ms": 100,
                },
                mock_ctx,
            )

        assert result1["input_hash"] != result2["input_hash"]
        assert result1["output_hash"] != result2["output_hash"]


# =============================================================================
# Import Tests
# =============================================================================


class TestImports:
    """Tests for proper module exports."""

    def test_import_from_phrases_module(self):
        """Test importing from phrases module."""
        from canon_vocab_workflow.phrases.record_vendor_call import (
            RecordVendorCallSpecs,
            record_vendor_call,
        )

        assert record_vendor_call is not None
        assert RecordVendorCallSpecs is not None

    def test_specs_in_all_exports(self):
        """Test that exports are in __all__."""
        # Use importlib to get the actual module (not the function)
        import importlib

        module = importlib.import_module("canon_vocab_workflow.phrases.record_vendor_call")

        assert hasattr(module, "__all__")
        assert "record_vendor_call" in module.__all__
        assert "RecordVendorCallSpecs" in module.__all__
