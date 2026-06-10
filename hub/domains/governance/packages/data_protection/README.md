# Canon Vocab: Data Protection

Data classification, encryption, minimization, purpose limitation, and retention compliance.

## Import

```python
from canon_vocab_data_protection import ...
```

## Regulatory Basis

Part of the Canon vocabulary system for regulatory compliance.

## Phrases

### Require

- `require_encrypted_transmission`
- `require_internal_publication`
- `require_limited_audience`
- `require_pci_classification`
- `require_phi_classification`
- `require_pii_classification`
- `require_processor_terms_verified`
- `require_retention_compliance`

### Verify

- `verify_data_minimization`
- `verify_purpose_limitation`


## Types

- `AudienceScope`
- `ClassificationLevel`
- `ConfidentialityLevel`
- `EncryptionStandard`
- `EncryptionStatus`
- `ProcessorTermsStatus`
- `PublicationRestriction`
- `RetentionStatus`

## Installation

This package is part of the `canon-hub` workspace. Install from the hub root:

```bash
cd hub
uv sync
```

## Usage

```python
from canon_vocab_data_protection import verify_data_minimization

# Use in a Canon workflow
result = await verify_data_minimization(options, ctx)
```

## License

Apache-2.0 — see repository LICENSE.
