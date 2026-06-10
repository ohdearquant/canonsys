# Canon Vocab: Certification

Decision certificates, FCRA notices, termination certification, and attestations.

## Import

```python
from canon_vocab_certification import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Action

- `record_attestation`
- `build_certificate_summary`
- `certify_fcra_notice`
- `certify_termination`
- `check_certificate_exists`
- `emit_certificate`
- `mint_certificate`
- `request_timestamp_attestation`
- `sign_certificate`
- `supersede_certificate`


## Types

- `AttestationMethod`
- `AttestationType`
- `CertificateClass`
- `CertificateStatus`
- `DecisionCertificate`
- `DecisionCertificateContent`
- `DefensibilityState`
- `InputFingerprint`
- `IntegrityVerification`
- `ModelIdentity`
- `ProceduralIntegrity`
- `ReviewBehavior`
- `CertificationEvent`
- `SignerRole`
- `TerminationType`
- `WorkflowType`
- `BuildCertificateSummarySpecs`
- `CertifyFcraNoticeSpecs`
- `CertifyTerminationSpecs`
- `CheckCertificateExistsSpecs`
- `EmitCertificateSpecs`
- `MintCertificateSpecs`
- `RecordAttestationSpecs`
- `RequestTimestampAttestationSpecs`
- `SignCertificateSpecs`
- `SupersedeCertificateSpecs`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_certification import record_attestation

# Use in a Canon workflow
result = await record_attestation(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
