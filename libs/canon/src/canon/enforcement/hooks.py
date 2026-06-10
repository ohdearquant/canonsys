"""Evidence hooks for iModel integration.

These hooks bridge lionpride SDK and CanonSys compliance.
Every iModel.invoke() automatically records to Evidence.

Usage:
    # Wrap vendor API calls with automatic evidence recording
    model = create_recorded_model(
        config=endpoint_config,
        tenant_id=ctx.tenant_id,
        config_id=vendor_config.id,
        service_name="screening",
        subject_id=application.subject_id,
    )

    # Every invoke() now auto-emits Evidence
    calling = await model.invoke(action="check", payload={...})
"""

from __future__ import annotations

from functools import partial
from typing import Any
from uuid import UUID

from kron.services import APICalling, HookPhase, HookRegistry, iModel
from kron.utils import now_utc

__all__ = [
    "create_evidence_hook",
    "create_recorded_model",
]


async def create_evidence_hook(
    calling: APICalling,
    *,
    tenant_id: UUID,
    config_id: UUID,
    service_name: str,
    workflow_run_id: UUID | None = None,
    subject_id: UUID | None = None,
    step_evidence_id: UUID | None = None,
) -> APICalling:
    """PostInvocation hook - automatically emits Evidence for API calls.

    This is the bridge between lionpride SDK and CanonSys compliance.
    Every iModel.invoke() automatically records to Evidence.

    Args:
        calling: Finished APICalling with execution results
        tenant_id: Tenant context
        config_id: FK to VendorConfig (for same-tool verification)
        service_name: Service that made the call
        workflow_run_id: Groups calls for workflow finalization
        subject_id: Who this call is about
        step_evidence_id: Parent step evidence (for nested tracking)

    Returns:
        calling unchanged (pass-through for hook chain)
    """
    from canon.entities.evidence import Evidence
    from kron.utils import compute_hash

    # Compute content hashes for provenance
    input_hash = compute_hash(calling.payload)
    output_hash = compute_hash(calling.response.raw_response) if calling.response else None

    evidence = Evidence(
        tenant_id=tenant_id,  # type: ignore[arg-type]
        subject_id=subject_id,  # type: ignore[arg-type]
        evidence_type=f"{service_name}.vendor_call",
        title=f"API call: {calling.backend.name if calling.backend else 'unknown'}",
        collected_at=now_utc(),
        data={
            "config_id": str(config_id),
            "workflow_run_id": str(workflow_run_id) if workflow_run_id else None,
            "step_evidence_id": str(step_evidence_id) if step_evidence_id else None,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "duration_ms": (
                int(calling.execution.duration * 1000) if calling.execution.duration else None
            ),
            "status": (calling.execution.status.value if calling.execution.status else None),
            "provider": calling.backend.provider if calling.backend else None,
        },
        source=service_name,
    )
    await evidence.save()

    return calling


def create_recorded_model(
    config: dict[str, Any],
    *,
    tenant_id: UUID,
    config_id: UUID,
    service_name: str,
    workflow_run_id: UUID | None = None,
    subject_id: UUID | None = None,
) -> iModel:
    """Create an iModel with automatic evidence recording.

    Every invoke() on this model will:
    1. Execute the API call via lionpride
    2. Fire PostInvocation hook
    3. Emit Evidence with input/output hashes

    Args:
        config: iModel/Endpoint configuration dict
        tenant_id: Tenant context for evidence
        config_id: VendorConfig ID for same-tool tracking
        service_name: Service name for evidence_type prefix
        workflow_run_id: Optional workflow grouping
        subject_id: Optional subject for evidence

    Returns:
        Configured iModel with evidence hook
    """
    # Bind static params to hook
    hook = partial(
        create_evidence_hook,
        tenant_id=tenant_id,
        config_id=config_id,
        service_name=service_name,
        workflow_run_id=workflow_run_id,
        subject_id=subject_id,
    )
    hook_registry = HookRegistry(hooks={HookPhase.PostInvocation: hook})

    model = iModel(**config, hook_registry=hook_registry)
    model.provider_metadata["config_id"] = config_id
    model.provider_metadata["tenant_id"] = tenant_id

    return model
