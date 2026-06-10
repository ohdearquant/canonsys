"""Verify same-tool gate for AEDT compliance.

Complete vertical slice:
- Fetches registered VendorConfig by ID
- Compares stored config_hash against actual_config_hash
- Creates immutable Evidence recording the verification result

AEDT compliance requires proving the exact same tool configuration
was used as was audited for bias.

Regulatory:
- NYC LL144: AEDT must be same tool as audited
- EU AI Act Article 9: Change management for high-risk AI
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from canon_vocab_evidence import save_evidence
from pydantic import BaseModel

from canon.db import TenantScope, select_one
from canon.enforcement.executor import canon_phrase
from canon.entities import Evidence, EvidenceContent
from kron.specs import Operable

if TYPE_CHECKING:
    from canon.enforcement import RequestContext

__all__ = ["VerifySameToolSpecs", "verify_same_tool"]


class VerifySameToolSpecs(BaseModel):
    """Specs for verify same tool phrase."""

    # inputs
    workflow_run_id: UUID
    config_id: UUID
    actual_config_hash: str
    subject_id: UUID | None = None
    # outputs
    passed: bool | None = None
    vendor_id: UUID | None = None
    service_name: str | None = None
    expected_hash: str | None = None
    evidence_id: UUID | None = None


verify_same_tool_operable = Operable.from_structure(VerifySameToolSpecs)


@canon_phrase(
    verify_same_tool_operable,
    inputs={"workflow_run_id", "config_id", "actual_config_hash", "subject_id"},
    outputs={
        "passed",
        "config_id",
        "vendor_id",
        "service_name",
        "expected_hash",
        "actual_config_hash",
        "evidence_id",
    },
)
async def verify_same_tool(
    options: VerifySameToolSpecs,
    ctx: RequestContext,
) -> dict:
    """Verify same-tool gate.

    AEDT compliance requires proving the exact same tool configuration
    was used as was audited for bias. This function:
    1. Fetches the registered VendorConfig by ID
    2. Compares the stored config_hash against actual_config_hash
    3. Creates immutable Evidence recording the verification result

    Args:
        options: Options containing workflow_run_id, config_id, actual_config_hash,
                 and optional subject_id
        ctx: Request context (tenant, actor, tracing)

    Returns:
        Dict with pass/fail status and evidence ID.
        Returns passed=False if VendorConfig not found.
    """
    workflow_run_id = options.workflow_run_id
    config_id = options.config_id
    actual_config_hash = options.actual_config_hash
    subject_id = options.subject_id

    # 1. Fetch VendorConfig by config_id
    row = await select_one(
        "vendor_configs",
        where={"id": config_id, "tenant_id": ctx.tenant_id},
        conn=ctx.conn,
        tenant_scope=TenantScope.REQUIRED,
    )

    if not row:
        # verify_* must return structured result, never raise
        return {
            "passed": False,
            "config_id": config_id,
            "vendor_id": None,
            "service_name": None,
            "expected_hash": None,
            "actual_config_hash": actual_config_hash,
            "evidence_id": None,
        }

    # Extract fields from config
    expected_hash = row["config_hash"]
    vendor_id = row.get("vendor_id")
    service_name = row.get("service_name")

    # 2. Compare config.config_hash == actual_config_hash
    passed = expected_hash == actual_config_hash

    # 3. Create evidence with verification result
    evidence_data = {
        "workflow_run_id": str(workflow_run_id),
        "config_id": str(config_id),
        "vendor_id": str(vendor_id) if vendor_id else None,
        "service_name": service_name,
        "expected_hash": expected_hash,
        "actual_hash": actual_config_hash,
        "passed": passed,
        "verification_type": "same_tool",
    }

    evidence_content = EvidenceContent(
        tenant_id=ctx.tenant_id,
        subject_id=subject_id,
        evidence_type="aedt.same_tool_verification",
        title=f"Same-tool verification: {'PASS' if passed else 'FAIL'}",
        data=evidence_data,
        source="canon_vocab_ai_governance",
        source_id=str(workflow_run_id),
    )

    evidence = Evidence(content=evidence_content)
    saved_result = await save_evidence(
        save_evidence.options_type(evidence=evidence),
        ctx,
    )

    return {
        "passed": passed,
        "config_id": config_id,
        "vendor_id": vendor_id,
        "service_name": service_name,
        "expected_hash": expected_hash,
        "actual_config_hash": actual_config_hash,
        "evidence_id": saved_result["saved_id"],
    }


# Export auto-generated types from the Phrase object
VerifySameToolOptions = verify_same_tool.options_type
VerifySameToolResult = verify_same_tool.result_type
