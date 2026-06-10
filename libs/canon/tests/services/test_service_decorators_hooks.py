"""Tests for service decorators and hooks modules.

Tests cover:
- CanonActionMeta for action-level metadata (name, evidence_type, skip_evidence)
- @action() decorator for action-level metadata binding
- get_canon_action_meta() extraction from handler methods
- create_evidence_hook() for API call evidence
- create_recorded_model() factory for iModel with evidence hooks

Architecture validation:
- Hooks bridge lionpride SDK and CanonSys compliance substrate
- Evidence is automatically emitted for all API calls
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from canon.enforcement.hooks import create_evidence_hook, create_recorded_model
from canon.enforcement.service import CanonActionMeta, action, get_canon_action_meta

if TYPE_CHECKING:
    from uuid import UUID


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tenant_id() -> UUID:
    """Fixed tenant ID for tests."""
    return uuid4()


@pytest.fixture
def config_id() -> UUID:
    """Fixed VendorConfig ID for tests."""
    return uuid4()


@pytest.fixture
def workflow_run_id() -> UUID:
    """Fixed workflow run ID for tests."""
    return uuid4()


@pytest.fixture
def subject_id() -> UUID:
    """Fixed subject (Person) ID for tests."""
    return uuid4()


@pytest.fixture
def step_evidence_id() -> UUID:
    """Fixed step evidence ID for tests."""
    return uuid4()


@pytest.fixture
def mock_api_calling():
    """Create a mock APICalling with realistic structure."""
    mock = MagicMock()
    mock.payload = {"prompt": "test prompt", "model": "gpt-4"}
    mock.backend = MagicMock()
    mock.backend.name = "openai"
    mock.backend.provider = "openai"
    mock.response = MagicMock()
    mock.response.raw_response = {"choices": [{"message": {"content": "test"}}]}
    mock.execution = MagicMock()
    mock.execution.duration = 0.5
    mock.execution.status = MagicMock()
    mock.execution.status.value = "completed"
    return mock


@pytest.fixture
def mock_api_calling_no_response():
    """Create a mock APICalling with no response (pre-invocation)."""
    mock = MagicMock()
    mock.payload = {"prompt": "test prompt"}
    mock.backend = MagicMock()
    mock.backend.name = "openai"
    mock.backend.provider = "openai"
    mock.response = None
    mock.execution = MagicMock()
    mock.execution.duration = None
    mock.execution.status = None
    return mock


@pytest.fixture
def mock_api_calling_no_backend():
    """Create a mock APICalling with no backend info."""
    mock = MagicMock()
    mock.payload = {"prompt": "test"}
    mock.backend = None
    mock.response = MagicMock()
    mock.response.raw_response = {"result": "test"}
    mock.execution = MagicMock()
    mock.execution.duration = 0.1
    mock.execution.status = MagicMock()
    mock.execution.status.value = "completed"
    return mock


# =============================================================================
# get_action_meta() Tests
# =============================================================================


class TestGetCanonActionMeta:
    """Tests for get_canon_action_meta() extraction function.

    Note: get_canon_action_meta() extracts CanonActionMeta from @action decorator.
    CanonActionMeta contains name, evidence_type, skip_evidence.
    """

    def test_get_canon_action_meta_returns_attached_config(self):
        """get_canon_action_meta() should return CanonActionMeta from @action decorator."""

        @action(evidence_type="consent.check")
        async def handler(self, req, ctx):
            pass

        result = get_canon_action_meta(handler)

        assert result is not None
        assert isinstance(result, CanonActionMeta)
        assert result.evidence_type == "consent.check"

    def test_get_canon_action_meta_returns_none_for_undecorated(self):
        """get_canon_action_meta() should return None for undecorated functions."""

        async def plain_handler(self, req, ctx):
            pass

        result = get_canon_action_meta(plain_handler)

        assert result is None

    def test_get_canon_action_meta_none_for_lambda(self):
        """get_canon_action_meta() should return None for lambda functions."""
        result = get_canon_action_meta(lambda x: x)
        assert result is None

    def test_get_canon_action_meta_from_class_method(self):
        """get_canon_action_meta() should work with class methods."""

        class Service:
            @action(evidence_type="admin.action")
            async def _handle_admin_action(self, req, ctx):
                pass

        result = get_canon_action_meta(Service._handle_admin_action)

        assert result is not None
        assert result.evidence_type == "admin.action"

    def test_get_canon_action_meta_empty_action(self):
        """get_canon_action_meta() should return CanonActionMeta for @action() without params."""

        @action()
        async def empty_handler(self, req, ctx):
            pass

        result = get_canon_action_meta(empty_handler)

        assert result is not None
        assert result.evidence_type is None
        assert result.skip_evidence is False

    def test_get_canon_action_meta_from_action_with_all_metadata(self):
        """get_canon_action_meta() extracts all metadata from @action."""

        @action(
            evidence_type="custom.type",
            skip_evidence=True,
        )
        async def handler(self, req, ctx):
            pass

        result = get_canon_action_meta(handler)

        assert result is not None
        assert result.evidence_type == "custom.type"
        assert result.skip_evidence is True

    def test_get_canon_action_meta_from_builtin(self):
        """get_canon_action_meta() should return None for builtin functions."""
        result = get_canon_action_meta(len)
        assert result is None


# =============================================================================
# create_evidence_hook() Tests
# =============================================================================


class TestCreateEvidenceHook:
    """Tests for create_evidence_hook() function."""

    @pytest.mark.asyncio
    async def test_create_evidence_hook_returns_calling(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should return the calling unchanged."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            result = await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="test_service",
            )

            assert result is mock_api_calling

    @pytest.mark.asyncio
    async def test_create_evidence_hook_creates_evidence(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should create Evidence entity."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            MockEvidence.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_evidence_hook_saves_evidence(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should save the created Evidence."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            mock_evidence_instance.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_evidence_hook_sets_tenant_id(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should set tenant_id on Evidence."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_create_evidence_hook_sets_evidence_type(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should set evidence_type as {service}.vendor_call."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["evidence_type"] == "interview.vendor_call"

    @pytest.mark.asyncio
    async def test_create_evidence_hook_sets_title_with_backend_name(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should set title with backend name."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert "API call:" in call_kwargs["title"]
            assert "openai" in call_kwargs["title"]

    @pytest.mark.asyncio
    async def test_create_evidence_hook_handles_no_backend(
        self, mock_api_calling_no_backend, tenant_id, config_id
    ):
        """create_evidence_hook() should handle missing backend."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling_no_backend,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert "unknown" in call_kwargs["title"]
            assert call_kwargs["data"]["provider"] is None

    @pytest.mark.asyncio
    async def test_create_evidence_hook_computes_input_hash(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should compute input hash from payload."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["input_hash"] is not None
            assert isinstance(call_kwargs["data"]["input_hash"], str)
            assert len(call_kwargs["data"]["input_hash"]) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_create_evidence_hook_computes_output_hash(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should compute output hash from response."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["output_hash"] is not None
            assert len(call_kwargs["data"]["output_hash"]) == 64

    @pytest.mark.asyncio
    async def test_create_evidence_hook_handles_no_response(
        self, mock_api_calling_no_response, tenant_id, config_id
    ):
        """create_evidence_hook() should handle missing response."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling_no_response,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["output_hash"] is None

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_config_id(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should include config_id in data."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["config_id"] == str(config_id)

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_workflow_run_id(
        self, mock_api_calling, tenant_id, config_id, workflow_run_id
    ):
        """create_evidence_hook() should include workflow_run_id in data."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                workflow_run_id=workflow_run_id,
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["workflow_run_id"] == str(workflow_run_id)

    @pytest.mark.asyncio
    async def test_create_evidence_hook_workflow_run_id_none(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should handle None workflow_run_id."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                workflow_run_id=None,
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["workflow_run_id"] is None

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_subject_id(
        self, mock_api_calling, tenant_id, config_id, subject_id
    ):
        """create_evidence_hook() should include subject_id on Evidence."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                subject_id=subject_id,
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["subject_id"] == subject_id

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_step_evidence_id(
        self, mock_api_calling, tenant_id, config_id, step_evidence_id
    ):
        """create_evidence_hook() should include step_evidence_id in data."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                step_evidence_id=step_evidence_id,
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["step_evidence_id"] == str(step_evidence_id)

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_duration_ms(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should include duration in milliseconds."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["duration_ms"] == 500  # 0.5 * 1000

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_status(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should include execution status."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_create_evidence_hook_includes_provider(
        self, mock_api_calling, tenant_id, config_id
    ):
        """create_evidence_hook() should include provider in data."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_create_evidence_hook_sets_source(self, mock_api_calling, tenant_id, config_id):
        """create_evidence_hook() should set source to service_name."""
        with patch("canon.entities.evidence.Evidence", autospec=True) as MockEvidence:
            mock_evidence_instance = MagicMock()
            mock_evidence_instance.save = AsyncMock()
            MockEvidence.return_value = mock_evidence_instance

            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="workflow",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["source"] == "workflow"


# =============================================================================
# create_recorded_model() Tests
# =============================================================================


class TestCreateRecordedModel:
    """Tests for create_recorded_model() factory function."""

    def test_create_recorded_model_returns_imodel(self, tenant_id, config_id):
        """create_recorded_model() should return an iModel instance."""
        with patch("canon.enforcement.hooks.iModel") as MockiModel:
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model

            result = create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            assert result is mock_model

    def test_create_recorded_model_passes_config_to_imodel(self, tenant_id, config_id):
        """create_recorded_model() should pass config to iModel."""
        with patch("canon.enforcement.hooks.iModel") as MockiModel:
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model

            config = {"model": "gpt-4", "temperature": 0.7}
            create_recorded_model(
                config=config,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            call_kwargs = MockiModel.call_args[1]
            assert call_kwargs["model"] == "gpt-4"
            assert call_kwargs["temperature"] == 0.7

    def test_create_recorded_model_creates_hook_registry(self, tenant_id, config_id):
        """create_recorded_model() should create HookRegistry."""
        with (
            patch("canon.enforcement.hooks.iModel") as MockiModel,
            patch("canon.enforcement.hooks.HookRegistry", autospec=True) as MockHookRegistry,
        ):
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model
            MockHookRegistry.return_value = MagicMock()

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            MockHookRegistry.assert_called_once()

    def test_create_recorded_model_registers_post_invocation_hook(self, tenant_id, config_id):
        """create_recorded_model() should register PostInvocation hook."""
        with (
            patch("canon.enforcement.hooks.iModel") as MockiModel,
            patch("canon.enforcement.hooks.HookRegistry", autospec=True) as MockHookRegistry,
            patch("canon.enforcement.hooks.HookPhase") as MockHookPhase,
        ):
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model
            MockHookRegistry.return_value = MagicMock()

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            # Verify HookPhase.PostInvocation was used
            call_kwargs = MockHookRegistry.call_args[1]
            assert MockHookPhase.PostInvocation in call_kwargs["hooks"]

    def test_create_recorded_model_binds_hook_params(self, tenant_id, config_id):
        """create_recorded_model() should bind params to hook via partial."""
        with (
            patch("canon.enforcement.hooks.iModel") as MockiModel,
            patch("canon.enforcement.hooks.HookRegistry", autospec=True) as MockHookRegistry,
        ):
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model
            captured_hook = None

            def capture_registry(hooks):
                nonlocal captured_hook
                from kron.services import HookPhase

                captured_hook = hooks.get(HookPhase.PostInvocation)
                return MagicMock()

            MockHookRegistry.side_effect = capture_registry

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            # The hook should be a partial with bound params
            assert captured_hook is not None
            assert isinstance(captured_hook, partial)
            assert captured_hook.keywords["tenant_id"] == tenant_id
            assert captured_hook.keywords["config_id"] == config_id
            assert captured_hook.keywords["service_name"] == "interview"

    def test_create_recorded_model_sets_config_id_metadata(self, tenant_id, config_id):
        """create_recorded_model() should set config_id in provider_metadata."""
        with patch("canon.enforcement.hooks.iModel") as MockiModel:
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            assert mock_model.provider_metadata["config_id"] == config_id

    def test_create_recorded_model_sets_tenant_id_metadata(self, tenant_id, config_id):
        """create_recorded_model() should set tenant_id in provider_metadata."""
        with patch("canon.enforcement.hooks.iModel") as MockiModel:
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            assert mock_model.provider_metadata["tenant_id"] == tenant_id

    def test_create_recorded_model_with_workflow_run_id(
        self, tenant_id, config_id, workflow_run_id
    ):
        """create_recorded_model() should pass workflow_run_id to hook."""
        with (
            patch("canon.enforcement.hooks.iModel") as MockiModel,
            patch("canon.enforcement.hooks.HookRegistry", autospec=True) as MockHookRegistry,
        ):
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model
            captured_hook = None

            def capture_registry(hooks):
                nonlocal captured_hook
                from kron.services import HookPhase

                captured_hook = hooks.get(HookPhase.PostInvocation)
                return MagicMock()

            MockHookRegistry.side_effect = capture_registry

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                workflow_run_id=workflow_run_id,
            )

            assert captured_hook.keywords["workflow_run_id"] == workflow_run_id

    def test_create_recorded_model_with_subject_id(self, tenant_id, config_id, subject_id):
        """create_recorded_model() should pass subject_id to hook."""
        with (
            patch("canon.enforcement.hooks.iModel") as MockiModel,
            patch("canon.enforcement.hooks.HookRegistry", autospec=True) as MockHookRegistry,
        ):
            mock_model = MagicMock()
            mock_model.provider_metadata = {}
            MockiModel.return_value = mock_model
            captured_hook = None

            def capture_registry(hooks):
                nonlocal captured_hook
                from kron.services import HookPhase

                captured_hook = hooks.get(HookPhase.PostInvocation)
                return MagicMock()

            MockHookRegistry.side_effect = capture_registry

            create_recorded_model(
                config={"model": "gpt-4"},
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
                subject_id=subject_id,
            )

            assert captured_hook.keywords["subject_id"] == subject_id


# =============================================================================
# Integration Tests
# =============================================================================


class TestDecoratorsHooksIntegration:
    """Integration tests for decorators and hooks working together."""

    def test_action_decorator_supports_evidence_binding_pattern(self):
        """@action() should support evidence binding for compliance audit trail.

        Architecture validation: decorators support action-level evidence type
        binding which is essential for the compliance evidence model.
        """

        class WorkflowService:
            @action(evidence_type="workflow.initiate")
            async def _handle_initiate(self, req, ctx):
                pass

            @action(evidence_type="workflow.adverse_action")
            async def _handle_adverse_action(self, req, ctx):
                pass

            @action(skip_evidence=True)
            async def _handle_read_only(self, req, ctx):
                pass

        # Verify metadata is extractable for evidence emission
        initiate_meta = get_canon_action_meta(WorkflowService._handle_initiate)
        adverse_meta = get_canon_action_meta(WorkflowService._handle_adverse_action)
        read_only_meta = get_canon_action_meta(WorkflowService._handle_read_only)

        assert initiate_meta.evidence_type == "workflow.initiate"
        assert adverse_meta.evidence_type == "workflow.adverse_action"
        assert read_only_meta.skip_evidence is True

    def test_decorator_patterns_applied_uniformly(self):
        """Verify decorator patterns are consistent across different handler types."""

        # Pattern: evidence_type only
        @action(evidence_type="consent.grant")
        async def evidence_typed(self, req, ctx):
            pass

        # Pattern: skip_evidence
        @action(skip_evidence=True)
        async def skipped(self, req, ctx):
            pass

        # Pattern: both evidence_type and skip_evidence
        @action(evidence_type="audit.log", skip_evidence=False)
        async def both_params(self, req, ctx):
            pass

        # Pattern: empty (no params)
        @action()
        async def no_params(self, req, ctx):
            pass

        # All should use same attribute mechanism
        for handler in [evidence_typed, skipped, both_params, no_params]:
            meta = get_canon_action_meta(handler)
            assert meta is not None
            assert isinstance(meta, CanonActionMeta)

    @pytest.mark.asyncio
    async def test_hook_evidence_chain_for_api_calls(self, mock_api_calling, tenant_id, config_id):
        """Verify hook creates proper evidence chain for audit trail."""
        evidence_calls = []

        with patch("canon.entities.evidence.Evidence") as MockEvidence:

            def capture_evidence(**kwargs):
                evidence_calls.append(kwargs)
                mock = MagicMock()
                mock.save = AsyncMock()
                return mock

            MockEvidence.side_effect = capture_evidence

            # Simulate multiple API calls
            await create_evidence_hook(
                mock_api_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="interview",
            )

            # Verify evidence was created with audit-grade data
            assert len(evidence_calls) == 1
            evidence_data = evidence_calls[0]

            # Required for audit trail
            assert evidence_data["tenant_id"] == tenant_id
            assert "vendor_call" in evidence_data["evidence_type"]
            assert evidence_data["data"]["input_hash"] is not None
            assert evidence_data["data"]["output_hash"] is not None
            assert evidence_data["source"] == "interview"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Edge case and boundary condition tests."""

    def test_canon_action_meta_with_explicit_defaults(self):
        """@action() with explicit default values should work."""

        @action(evidence_type=None, skip_evidence=False)
        async def explicit_defaults(self, req, ctx):
            pass

        meta = get_canon_action_meta(explicit_defaults)
        assert meta.evidence_type is None
        assert meta.skip_evidence is False

    def test_canon_action_meta_with_custom_name(self):
        """@action() with custom name should override function name."""

        @action("custom.action.name")
        async def handler(self, req, ctx):
            pass

        meta = get_canon_action_meta(handler)
        assert meta.name == "custom.action.name"

    def test_canon_action_meta_name_defaults_to_function_name(self):
        """@action() without name should default to function name."""

        @action()
        async def my_handler(self, req, ctx):
            pass

        meta = get_canon_action_meta(my_handler)
        assert meta.name == "my_handler"

    def test_evidence_type_with_dotted_names(self):
        """Evidence type should support dotted naming convention."""

        @action(evidence_type="consent.background_check.vendor_call")
        async def dotted_name(self, req, ctx):
            pass

        meta = get_canon_action_meta(dotted_name)
        assert meta.evidence_type == "consent.background_check.vendor_call"

    @pytest.mark.asyncio
    async def test_hook_handles_execution_without_duration(self, tenant_id, config_id):
        """Hook should handle execution with None duration."""
        mock_calling = MagicMock()
        mock_calling.payload = {"test": "data"}
        mock_calling.backend = MagicMock()
        mock_calling.backend.name = "test"
        mock_calling.backend.provider = "test"
        mock_calling.response = MagicMock()
        mock_calling.response.raw_response = {"result": "ok"}
        mock_calling.execution = MagicMock()
        mock_calling.execution.duration = None
        mock_calling.execution.status = None

        with patch("canon.entities.evidence.Evidence") as MockEvidence:
            mock_evidence = MagicMock()
            mock_evidence.save = AsyncMock()
            MockEvidence.return_value = mock_evidence

            await create_evidence_hook(
                mock_calling,
                tenant_id=tenant_id,
                config_id=config_id,
                service_name="test",
            )

            call_kwargs = MockEvidence.call_args[1]
            assert call_kwargs["data"]["duration_ms"] is None
            assert call_kwargs["data"]["status"] is None
