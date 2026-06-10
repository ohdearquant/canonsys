# Canon Vocab: Core

Core compliance primitives: audit verification, charter management, break glass, and SOX review.

## Import

```python
from canon_vocab_core import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_alternative_reviewed`
- `require_fraud_screening_pass`
- `require_provenance_documented`
- `require_sox_compliance_review`
- `require_value_within_limit`

### Verify

- `verify_audit_complete`
- `verify_audit_current`
- `verify_evidence_freshness`
- `verify_signer_identity`
- `verify_values_match`

### Derive

- `derive_amount_band`

### Action

- `activate_charter`
- `get_charter_by_id`
- `get_charter_history`
- `invoke_break_glass`
- `invoke_executive_override`
- `ratify_charter`
- `resolve_charter`


## Types

- `AlternativeReviewStatus`
- `AmountBandConfig`
- `AmountBandResult`
- `AuditStatus`
- `BreakGlassCertificate`
- `BreakGlassReason`
- `ExecutiveOverride`
- `FraudScreeningResult`
- `FreshnessResult`
- `OverrideAuthority`
- `RequireAlternativeReviewedResult`
- `RequireFraudScreeningPassResult`
- `RequireProvenanceDocumentedResult`
- `RequireSOXComplianceReviewResult`
- `SOXReviewStatus`
- `Signatory`
- `SignerIdentityResult`
- `ValueWithinLimitResult`
- `ValuesMatchResult`
- `VerifyAuditCompleteResult`
- `VerifyAuditCurrentResult`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_core import verify_audit_complete

# Use in a Canon workflow
result = await verify_audit_complete(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
