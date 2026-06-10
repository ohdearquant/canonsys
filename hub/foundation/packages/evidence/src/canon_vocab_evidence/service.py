"""Evidence service - thin wrapper over evidence phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    CEPType,
    ChainEvidenceSpecs,
    CreateCEPSpecs,
    CreateGenesisEntrySpecs,
    GetCaseEvidenceSpecs,
    GetCaseHistorySpecs,
    SealCEPSpecs,
    SupersedeEvidenceSpecs,
    VerifyCaseIntegritySpecs,
    VerifyCEPReferenceSpecs,
    VerifyChainSpecs,
    chain_evidence,
    create_cep,
    create_genesis_entry,
    get_case_evidence,
    get_case_history,
    seal_cep,
    supersede_evidence,
    verify_case_integrity,
    verify_cep_reference,
    verify_chain,
)

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext


__all__ = ["EvidenceService"]


class EvidenceService(CanonService):
    """Evidence service - manages evidence, chains, and CEPs.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(provider="canon", name="evidence")

    # =========================================================================
    # CEP Actions
    # =========================================================================

    @action(evidence_type="cep.create")
    async def create_cep(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Create a draft CEP.

        Args:
            payload: Must contain 'facts' and 'cep_type'
            ctx: Request context

        Returns:
            Created CEP as dict
        """
        facts = payload["facts"]
        cep_type = CEPType(payload["cep_type"])
        custodian_id = payload.get("custodian_id")

        result = await create_cep(
            CreateCEPSpecs(
                facts=facts,
                cep_type=cep_type,
                custodian_id=custodian_id,
            ),
            ctx,
        )
        return {
            "id": str(result["cep_id"]),
            "content_hash": result["content_hash"],
            "status": result["status"].value if result["status"] else None,
        }

    @action(evidence_type="cep.seal")
    async def seal_cep(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Seal a draft CEP with signature and timestamp.

        Args:
            payload: Must contain 'cep_id'
            ctx: Request context

        Returns:
            Sealed CEP as dict
        """
        cep_id = payload["cep_id"]

        result = await seal_cep(
            SealCEPSpecs(cep_id=cep_id),
            ctx,
        )
        return {
            "cep_id": str(cep_id),
            "sealed_at": (result["sealed_at"].isoformat() if result["sealed_at"] else None),
            "signature": result["signature"],
            "signing_key_id": result["signing_key_id"],
        }

    @action(skip_evidence=True)
    async def verify_cep(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Verify a CEP reference (hot path, no evidence emission).

        Args:
            payload: Must contain 'cep_id' and 'expected_hash'
            ctx: Request context

        Returns:
            Verification result as dict
        """
        cep_id = payload["cep_id"]
        expected_hash = payload["expected_hash"]

        result = await verify_cep_reference(
            VerifyCEPReferenceSpecs(
                cep_id=cep_id,
                expected_hash=expected_hash,
            ),
            ctx,
        )
        return {
            "valid": result["valid"],
            "cep_id": str(result["cep_id"]),
            "reason": result["reason"],
            "cep_type": result["cep_type"],
            "sealed_at": (result["sealed_at"].isoformat() if result["sealed_at"] else None),
        }

    # =========================================================================
    # Chain Actions
    # =========================================================================

    @action(evidence_type="chain.genesis")
    async def create_genesis(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Create genesis chain entry for evidence.

        Args:
            payload: Must contain 'evidence' (Evidence object or dict)
            ctx: Request context

        Returns:
            Created ChainEntry as dict
        """
        evidence = payload["evidence"]
        event_type = payload.get("event_type", "evidence_collected")

        result = await create_genesis_entry(
            CreateGenesisEntrySpecs(
                evidence=evidence,
                event_type=event_type,
            ),
            ctx,
        )
        return {
            "id": str(result["entry_id"]),
            "chain_hash": result["chain_hash"],
            "sequence": 0,
            "event_type": event_type,
        }

    @action(evidence_type="chain.link")
    async def chain(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Link evidence in chain.

        Args:
            payload: Must contain 'parent' and 'child' Evidence objects
            ctx: Request context

        Returns:
            Created ChainEntry as dict
        """
        parent = payload["parent"]
        child = payload["child"]
        event_type = payload.get("event_type", "evidence_linked")

        result = await chain_evidence(
            ChainEvidenceSpecs(
                parent=parent,
                child=child,
                event_type=event_type,
            ),
            ctx,
        )
        return {
            "id": str(result["entry_id"]),
            "chain_hash": result["chain_hash"],
            "sequence": result["sequence"],
            "event_type": event_type,
        }

    @action(skip_evidence=True)
    async def verify_chain(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Verify chain integrity (hot path).

        Args:
            payload: Must contain 'resource_id', optionally 'resource_type'
            ctx: Request context

        Returns:
            Verification result as dict
        """
        resource_id = payload["resource_id"]
        resource_type = payload.get("resource_type", "evidence")

        result = await verify_chain(
            VerifyChainSpecs(
                resource_id=resource_id,
                resource_type=resource_type,
            ),
            ctx,
        )
        return {
            "valid": result["valid"],
            "chain_length": result["chain_length"],
            "broken_at": result["broken_at"],
            "expected_hash": result["expected_hash"],
            "actual_hash": result["actual_hash"],
            "message": result["message"],
        }

    # =========================================================================
    # Case Evidence Actions
    # =========================================================================

    @action(skip_evidence=True)
    async def get_case_evidence(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Get all evidence for a case (hot path).

        Args:
            payload: Must contain 'case_id'
            ctx: Request context

        Returns:
            Case evidence result as dict
        """
        case_id = payload["case_id"]
        evidence_type = payload.get("evidence_type")

        result = await get_case_evidence(
            GetCaseEvidenceSpecs(
                case_id=case_id,
                tenant_id=ctx.tenant_id,
                evidence_type=evidence_type,
            ),
            ctx,
        )
        return {
            "case_id": str(result["case_id"]),
            "tenant_id": str(result["tenant_id"]),
            "evidence_ids": [str(eid) for eid in result["evidence_ids"]],
            "count": result["count"],
            "earliest": result["earliest"].isoformat() if result["earliest"] else None,
            "latest": result["latest"].isoformat() if result["latest"] else None,
        }

    @action(skip_evidence=True)
    async def get_case_history(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Get complete audit timeline for a case (hot path).

        Args:
            payload: Must contain 'case_id'
            ctx: Request context

        Returns:
            Case history with timeline as dict
        """
        case_id = payload["case_id"]
        workflow_type = payload.get("workflow_type")

        result = await get_case_history(
            GetCaseHistorySpecs(
                case_id=case_id,
                tenant_id=ctx.tenant_id,
                workflow_type=workflow_type,
            ),
            ctx,
        )
        timeline = [
            {
                "evidence_id": str(entry.evidence_id),
                "collected_at": (entry.collected_at.isoformat() if entry.collected_at else None),
                "evidence_type": entry.evidence_type,
                "title": entry.title,
                "operation": entry.operation,
                "content_hash": entry.content_hash,
                "chain_hash": entry.chain_hash,
            }
            for entry in result["timeline"]
        ]
        return {
            "case_id": str(result["case_id"]),
            "workflow_type": result["workflow_type"],
            "evidence_count": result["evidence_count"],
            "timeline": timeline,
            "earliest": result["earliest"].isoformat() if result["earliest"] else None,
            "latest": result["latest"].isoformat() if result["latest"] else None,
        }

    @action(skip_evidence=True)
    async def verify_case_integrity(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Verify content integrity for all case evidence (hot path).

        Args:
            payload: Must contain 'case_id'
            ctx: Request context

        Returns:
            Integrity verification result as dict
        """
        case_id = payload["case_id"]

        result = await verify_case_integrity(
            VerifyCaseIntegritySpecs(
                case_id=case_id,
                tenant_id=ctx.tenant_id,
            ),
            ctx,
        )
        return {
            "case_id": str(result["case_id"]),
            "valid": result["valid"],
            "evidence_count": result["evidence_count"],
            "verified_count": result["verified_count"],
            "integrity_score": result["integrity_score"],
            "issues": list(result["issues"]),
        }

    # =========================================================================
    # Supersession Actions
    # =========================================================================

    @action(evidence_type="evidence.supersede")
    async def supersede(
        self,
        payload: dict[str, Any],
        ctx: RequestContext,
    ) -> dict[str, Any]:
        """Supersede evidence with correction.

        Args:
            payload: Must contain 'original_id' and 'correction' (EvidenceContent)
            ctx: Request context

        Returns:
            New superseding evidence as dict
        """
        original_id = payload["original_id"]
        correction = payload["correction"]
        reason = payload.get("reason")

        result = await supersede_evidence(
            SupersedeEvidenceSpecs(
                original_id=original_id,
                correction=correction,
                reason=reason,
            ),
            ctx,
        )
        return {
            "id": str(result["new_evidence_id"]),
            "content_hash": result["content_hash"],
            "supersedes_id": str(original_id),
        }
