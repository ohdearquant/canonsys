"""Certification service - thin wrapper over certification phrases.

The service layer provides:
- Evidence emission via hooks
- RequestContext management

All logic lives in phrases/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from canon.enforcement.service import CanonService, CanonServiceConfig, action

from .phrases import (
    AttestationType,
    BuildCertificateSummarySpecs,
    CertifyFcraNoticeSpecs,
    CertifyTerminationSpecs,
    CheckCertificateExistsSpecs,
    EmitCertificateSpecs,
    MintCertificateSpecs,
    RecordAttestationSpecs,
    RequestTimestampAttestationSpecs,
    SignCertificateSpecs,
    SupersedeCertificateSpecs,
    TerminationType,
    build_certificate_summary,
    certify_fcra_notice,
    certify_termination,
    check_certificate_exists,
    emit_certificate,
    mint_certificate,
    record_attestation,
    request_timestamp_attestation,
    sign_certificate,
    supersede_certificate,
)
from .types import CertificateClass

if TYPE_CHECKING:
    from canon.enforcement.service import RequestContext

__all__ = [
    "CertificationService",
]


class CertificationService(CanonService):
    """Certification service - manages decision certificates and attestations.

    Thin wrapper that delegates to phrase functions.
    """

    config: ClassVar[CanonServiceConfig] = CanonServiceConfig(
        provider="canon", name="certification"
    )

    # =========================================================================
    # Certificate Lifecycle
    # =========================================================================

    @action(evidence_type="certification.emit")
    async def emit(self, payload: dict, ctx: RequestContext) -> dict:
        """Emit a provisional decision certificate.

        Creates certificate in PROVISIONAL status.
        Call mint() to finalize after all gates pass.
        """
        options = EmitCertificateSpecs(
            action_type=payload["action_type"],
            subject_id=payload.get("subject_id"),
            case_id=payload.get("case_id"),
            jurisdiction=payload.get("jurisdiction"),
            evidence_ids=payload.get("evidence_ids"),
            gates_passed=payload.get("gates_passed"),
            model_identity=payload.get("model_identity"),
            input_fingerprints=payload.get("input_fingerprints"),
            review_behavior=payload.get("review_behavior"),
            certificate_class=CertificateClass(payload.get("certificate_class", "certified")),
        )
        result = await emit_certificate(options, ctx)
        return {
            "certificate_id": str(result["id"]),
            "status": result["status"].value,
            "created_at": result["created_at"].isoformat(),
        }

    @action(evidence_type="certification.mint")
    async def mint(self, payload: dict, ctx: RequestContext) -> dict:
        """Mint (finalize) a provisional certificate.

        Transitions certificate from PROVISIONAL to MINTED.
        After minting, certificate is immutable (temporal cliff).
        """
        options = MintCertificateSpecs(
            certificate_id=UUID(payload["certificate_id"]),
            attestations=payload.get("attestations"),
            outcome=payload.get("outcome"),
            outcome_rationale=payload.get("outcome_rationale"),
        )
        result = await mint_certificate(options, ctx)
        return {
            "certificate_id": str(result["id"]),
            "status": result["status"].value,
            "minted_at": (result["minted_at"].isoformat() if result.get("minted_at") else None),
            "validation_hash": result.get("validation_hash"),
        }

    @action(evidence_type="certification.sign")
    async def sign(self, payload: dict, ctx: RequestContext) -> dict:
        """Sign a certificate with RSA-4096."""
        options = SignCertificateSpecs(certificate_id=UUID(payload["certificate_id"]))
        result = await sign_certificate(options, ctx)
        return {
            "certificate_id": str(result["certificate_id"]),
            "signing_key_id": result["signing_key_id"],
            "signature": result["signature"],
            "signed_at": result["signed_at"].isoformat(),
        }

    @action(evidence_type="certification.supersede")
    async def supersede(self, payload: dict, ctx: RequestContext) -> dict:
        """Supersede an existing certificate with corrections.

        Creates new certificate linked to original via supersedes_id.
        Original transitions to SUPERSEDED status.
        """
        options = SupersedeCertificateSpecs(
            original_id=UUID(payload["original_id"]),
            action_type=payload.get("action_type"),
            evidence_ids=payload.get("evidence_ids"),
            attestations=payload.get("attestations"),
            reason=payload.get("reason"),
            outcome=payload.get("outcome"),
            outcome_rationale=payload.get("outcome_rationale"),
        )
        result = await supersede_certificate(options, ctx)
        return {
            "certificate_id": str(result["id"]),
            "supersedes_id": str(result["supersedes_id"]),
            "status": result["status"].value,
            "minted_at": (result["minted_at"].isoformat() if result.get("minted_at") else None),
        }

    @action(skip_evidence=True)
    async def check_exists(self, payload: dict, ctx: RequestContext) -> dict:
        """Check if certified certificate exists for a case."""
        options = CheckCertificateExistsSpecs(
            case_id=UUID(payload["case_id"]),
            certificate_type=payload.get("certificate_type"),
        )
        result = await check_certificate_exists(options, ctx)
        return {
            "case_id": str(result["case_id"]),
            "exists": result["exists"],
            "certificate_id": (
                str(result["certificate_id"]) if result.get("certificate_id") else None
            ),
            "certified_at": (
                result["certified_at"].isoformat() if result.get("certified_at") else None
            ),
            "certificate_hash": result.get("certificate_hash"),
            "certificate_type": result.get("certificate_type"),
        }

    @action(skip_evidence=True)
    async def get_summary(self, payload: dict, ctx: RequestContext) -> dict:
        """Build human-readable certificate summary."""
        options = BuildCertificateSummarySpecs(
            case_id=UUID(payload["case_id"]),
            decision_type=payload["decision_type"],
            certified_at=payload.get("certified_at"),
            policy_version=payload.get("policy_version"),
            integrity_score=payload["integrity_score"],
            checkpoints_completed=payload["checkpoints_completed"],
            checkpoints_expected=payload["checkpoints_expected"],
            immutability_hash=payload.get("immutability_hash"),
        )
        # build_certificate_summary is sync
        result = build_certificate_summary(options)
        return result

    # =========================================================================
    # High-Stakes Certifications
    # =========================================================================

    @action(evidence_type="certification.fcra_notice")
    async def certify_fcra(self, payload: dict, ctx: RequestContext) -> dict:
        """Certify FCRA pre-adverse action notice compliance.

        Per FCRA 15 U.S.C. Section 1681b(b)(3):
        1. Pre-adverse action notice was sent
        2. Copy of consumer report included
        3. Reasonable waiting period elapsed (5 business days)
        """
        options = CertifyFcraNoticeSpecs(
            subject_id=UUID(payload["subject_id"]),
            notice_sent_at=payload["notice_sent_at"],
            dispute_window_end=payload["dispute_window_end"],
            cep_ids=[UUID(cid) for cid in payload["cep_ids"]],
            application_id=(
                UUID(payload["application_id"]) if payload.get("application_id") else None
            ),
        )
        result = await certify_fcra_notice(options, ctx)
        return {
            "certificate_id": str(result["id"]),
            "certificate_hash": result["certificate_hash"],
            "certified_at": result["certified_at"].isoformat(),
        }

    @action(evidence_type="certification.termination")
    async def certify_termination(self, payload: dict, ctx: RequestContext) -> dict:
        """Create Termination Decision Certificate (TDC).

        For involuntary terminations, requires:
        - ER clearance verified
        - Parity attested (similar treatment)
        - CEP evidence bound
        """
        options = CertifyTerminationSpecs(
            subject_id=UUID(payload["subject_id"]),
            termination_type=TerminationType(payload["termination_type"]),
            policy_basis=payload["policy_basis"],
            cep_ids=[UUID(cid) for cid in payload["cep_ids"]],
            er_clearance_verified=payload["er_clearance_verified"],
            parity_attested=payload["parity_attested"],
            effective_date=payload.get("effective_date"),
            attestation_id=(
                UUID(payload["attestation_id"]) if payload.get("attestation_id") else None
            ),
            override_id=(UUID(payload["override_id"]) if payload.get("override_id") else None),
        )
        result = await certify_termination(options, ctx)
        return {
            "certificate_id": str(result["id"]),
            "certificate_hash": result["certificate_hash"],
            "certified_at": result["certified_at"].isoformat(),
            "effective_date": (
                result["effective_date"].isoformat() if result.get("effective_date") else None
            ),
        }

    # =========================================================================
    # Attestations
    # =========================================================================

    @action(evidence_type="certification.attestation")
    async def attest(self, payload: dict, ctx: RequestContext) -> dict:
        """Record a typed attestation.

        Attestations are PROCESS attestations, not outcome attestations.
        The signer attests to following procedure, NOT correctness of decision.
        """
        options = RecordAttestationSpecs(
            target_type=payload["target_type"],
            target_id=UUID(payload["target_id"]),
            attestation_type=AttestationType(payload["attestation_type"]),
            attestation_text=payload["attestation_text"],
            attester_role=payload["attester_role"],
            ip_address=payload.get("ip_address"),
            user_agent=payload.get("user_agent"),
        )
        result = await record_attestation(options, ctx)
        return {
            "attestation_id": str(result["id"]),
            "attestation_hash": result["attestation_hash"],
            "attested_at": result["attested_at"].isoformat(),
        }

    @action(evidence_type="certification.timestamp")
    async def timestamp(self, payload: dict, ctx: RequestContext) -> dict:
        """Request RFC 3161 timestamp attestation.

        Provides cryptographic proof of when content existed.
        """
        options = RequestTimestampAttestationSpecs(
            content_hash=payload["content_hash"],
            target_type=payload.get("target_type"),
            target_id=UUID(payload["target_id"]) if payload.get("target_id") else None,
            tsa_name=payload.get("tsa_name", "internal"),
        )
        result = await request_timestamp_attestation(options, ctx)
        return {
            "attestation_id": str(result["id"]),
            "token_hash": result["token_hash"],
            "gen_time": result["gen_time"].isoformat(),
        }
