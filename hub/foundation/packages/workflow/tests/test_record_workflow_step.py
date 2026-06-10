"""Tests for record_workflow_step phrase.

Tests cover:
- Recording workflow steps with input/output data
- Hash computation for data provenance
- Evidence creation with correct structure
- Optional duration_ms and subject_id parameters

Compliance Context:
    - NYC LL144 (Automated decision tool transparency)
    - ISO 27001 (Information security management)
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from canon_vocab_workflow.phrases.record_workflow_step import (
    RecordWorkflowStepSpecs,
    record_workflow_step,
)

from kron.utils import compute_hash

# =============================================================================
# Mock Classes for Evidence Model (avoids pydantic model_rebuild requirement)
# =============================================================================


class MockEvidenceContent:
    """Mock EvidenceContent that captures constructor kwargs as attributes."""

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class MockEvidence:
    """Mock Evidence that wraps content."""

    def __init__(self, content):
        self.content = content


@contextmanager
def mock_evidence_models():
    """Context manager to patch Evidence and EvidenceContent classes."""
    with (
        patch(
            "canon_vocab_workflow.phrases.record_workflow_step.EvidenceContent",
            MockEvidenceContent,
        ),
        patch(
            "canon_vocab_workflow.phrases.record_workflow_step.Evidence",
            MockEvidence,
        ),
    ):
        yield


# =============================================================================
# Fixtures
# =============================================================================


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
def saved_evidence_id():
    """Generate an evidence ID for the saved evidence."""
    return uuid4()


@pytest.fixture
def mock_saved_evidence(saved_evidence_id):
    """Create a mock saved evidence with the saved_evidence_id."""
    mock = AsyncMock()
    mock.id = saved_evidence_id
    return mock


# =============================================================================
# Specs Class Tests
# =============================================================================


class TestRecordWorkflowStepSpecs:
    """Tests for RecordWorkflowStepSpecs Pydantic model."""

    def test_specs_with_all_fields(self, saved_evidence_id, workflow_run_id):
        """Test creating specs with all fields."""
        specs = RecordWorkflowStepSpecs(
            workflow_run_id=workflow_run_id,
            step_name="process_candidate",
            input_data={"a": 1},
            output_data={"b": 2},
            duration_ms=150,
            subject_id=uuid4(),
            evidence_id=saved_evidence_id,
            input_hash="abc123",
            output_hash="def456",
        )
        assert specs.workflow_run_id == workflow_run_id
        assert specs.step_name == "process_candidate"
        assert specs.duration_ms == 150
        assert specs.evidence_id == saved_evidence_id
        assert specs.input_hash == "abc123"
        assert specs.output_hash == "def456"

    def test_specs_with_minimal_fields(self, workflow_run_id):
        """Test creating specs with minimal required fields."""
        specs = RecordWorkflowStepSpecs(
            workflow_run_id=workflow_run_id,
            step_name="validate_input",
            input_data={},
            output_data={},
        )
        assert specs.duration_ms is None
        assert specs.subject_id is None
        assert specs.evidence_id is None
        assert specs.input_hash is None
        assert specs.output_hash is None


# =============================================================================
# Function Behavior Tests
# =============================================================================


class TestRecordWorkflowStep:
    """Tests for record_workflow_step phrase function."""

    @pytest.mark.asyncio
    async def test_records_step_with_correct_hashes(
        self, mock_ctx, workflow_run_id, mock_saved_evidence
    ):
        """Test that input and output data are hashed correctly."""
        input_data = {"candidate_id": "12345", "score": 85}
        output_data = {"decision": "approved", "confidence": 0.95}

        expected_input_hash = compute_hash(input_data)
        expected_output_hash = compute_hash(output_data)

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "scoring",
            "input_data": input_data,
            "output_data": output_data,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ) as mock_save,
        ):
            result = await record_workflow_step(payload, mock_ctx)

        assert isinstance(result, dict)
        assert result["input_hash"] == expected_input_hash
        assert result["output_hash"] == expected_output_hash
        assert result["evidence_id"] == mock_saved_evidence.id
        assert result["step_name"] == "scoring"
        assert result["duration_ms"] is None

        # Verify save_evidence was called
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_evidence_with_correct_structure(
        self, mock_ctx, workflow_run_id, mock_saved_evidence
    ):
        """Test that evidence content is structured correctly."""
        input_data = {"field": "value"}
        output_data = {"result": "success"}
        step_name = "validate"
        duration_ms = 250

        captured_evidence = None

        async def capture_evidence(evidence, ctx, **kwargs):
            nonlocal captured_evidence
            captured_evidence = evidence
            return mock_saved_evidence

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": step_name,
            "input_data": input_data,
            "output_data": output_data,
            "duration_ms": duration_ms,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                side_effect=capture_evidence,
            ),
        ):
            await record_workflow_step(payload, mock_ctx)

        assert captured_evidence is not None
        content = captured_evidence.content

        assert content.tenant_id == mock_ctx.tenant_id
        assert content.evidence_type == f"workflow.step.{step_name}"
        assert content.title == f"Workflow step: {step_name}"
        assert content.source == "canon"
        assert content.collected_by_id == mock_ctx.actor_id
        assert content.subject_id is None

        # Verify data structure
        assert content.data["workflow_run_id"] == str(workflow_run_id)
        assert content.data["step_name"] == step_name
        assert content.data["input_hash"] == compute_hash(input_data)
        assert content.data["output_hash"] == compute_hash(output_data)
        assert content.data["duration_ms"] == duration_ms

    @pytest.mark.asyncio
    async def test_with_duration_ms(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test recording step with duration measurement."""
        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "long_running",
            "input_data": {"x": 1},
            "output_data": {"y": 2},
            "duration_ms": 5000,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result = await record_workflow_step(payload, mock_ctx)

        assert result["duration_ms"] == 5000

    @pytest.mark.asyncio
    async def test_with_subject_id(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test recording step with subject ID for person-specific workflows."""
        subject_id = uuid4()

        captured_evidence = None

        async def capture_evidence(evidence, ctx, **kwargs):
            nonlocal captured_evidence
            captured_evidence = evidence
            return mock_saved_evidence

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "person_step",
            "input_data": {"a": 1},
            "output_data": {"b": 2},
            "subject_id": subject_id,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                side_effect=capture_evidence,
            ),
        ):
            await record_workflow_step(payload, mock_ctx)

        assert captured_evidence is not None
        assert captured_evidence.content.subject_id == subject_id

    @pytest.mark.asyncio
    async def test_with_empty_input_data(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test recording step with empty input data."""
        input_data = {}
        output_data = {"status": "ok"}

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "empty_input",
            "input_data": input_data,
            "output_data": output_data,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result = await record_workflow_step(payload, mock_ctx)

        assert result["input_hash"] == compute_hash({})
        assert result["output_hash"] == compute_hash(output_data)

    @pytest.mark.asyncio
    async def test_with_empty_output_data(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test recording step with empty output data."""
        input_data = {"trigger": "manual"}
        output_data = {}

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "empty_output",
            "input_data": input_data,
            "output_data": output_data,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result = await record_workflow_step(payload, mock_ctx)

        assert result["input_hash"] == compute_hash(input_data)
        assert result["output_hash"] == compute_hash({})

    @pytest.mark.asyncio
    async def test_with_nested_data(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test recording step with deeply nested data structures."""
        input_data = {
            "config": {
                "model": "gpt-4",
                "params": {
                    "temperature": 0.7,
                    "max_tokens": 1000,
                },
            },
            "inputs": ["a", "b", "c"],
        }
        output_data = {
            "results": [
                {"id": 1, "value": "x"},
                {"id": 2, "value": "y"},
            ],
            "metadata": {"version": "1.0"},
        }

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "complex_step",
            "input_data": input_data,
            "output_data": output_data,
        }

        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result = await record_workflow_step(payload, mock_ctx)

        assert result["input_hash"] == compute_hash(input_data)
        assert result["output_hash"] == compute_hash(output_data)

    @pytest.mark.asyncio
    async def test_hash_determinism(self, mock_ctx, workflow_run_id, mock_saved_evidence):
        """Test that hashes are deterministic for same input."""
        input_data = {"key": "value", "number": 42}
        output_data = {"result": True}

        payload = {
            "workflow_run_id": workflow_run_id,
            "step_name": "determinism_test",
            "input_data": input_data,
            "output_data": output_data,
        }

        results = []
        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            for _ in range(3):
                result = await record_workflow_step(payload, mock_ctx)
                results.append(result)

        # All hashes should be identical
        assert all(r["input_hash"] == results[0]["input_hash"] for r in results)
        assert all(r["output_hash"] == results[0]["output_hash"] for r in results)

    @pytest.mark.asyncio
    async def test_different_inputs_produce_different_hashes(
        self, mock_ctx, workflow_run_id, mock_saved_evidence
    ):
        """Test that different inputs produce different hashes."""
        with (
            mock_evidence_models(),
            patch(
                "canon_vocab_workflow.phrases.record_workflow_step.save_evidence",
                new_callable=AsyncMock,
                return_value=mock_saved_evidence,
            ),
        ):
            result1 = await record_workflow_step(
                {
                    "workflow_run_id": workflow_run_id,
                    "step_name": "test",
                    "input_data": {"x": 1},
                    "output_data": {"y": 1},
                },
                mock_ctx,
            )
            result2 = await record_workflow_step(
                {
                    "workflow_run_id": workflow_run_id,
                    "step_name": "test",
                    "input_data": {"x": 2},
                    "output_data": {"y": 2},
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
        from canon_vocab_workflow.phrases.record_workflow_step import (
            RecordWorkflowStepSpecs,
            record_workflow_step,
        )

        assert record_workflow_step is not None
        assert RecordWorkflowStepSpecs is not None

    def test_specs_in_all(self):
        """Test that specs type is in __all__."""
        from importlib import import_module

        module = import_module("canon_vocab_workflow.phrases.record_workflow_step")

        assert "RecordWorkflowStepSpecs" in module.__all__
        assert "record_workflow_step" in module.__all__
