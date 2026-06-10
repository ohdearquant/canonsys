# 019-Jurisdiction - Code Mapping

## Vocabulary Packages

**Primary Packages**:

| Package           | Path                                                     | Purpose                           |
| ----------------- | -------------------------------------------------------- | --------------------------------- |
| `scope`           | `hub/foundation/packages/scope/`           | Destination/channel validation    |
| `data_protection` | `hub/domains/governance/packages/data_protection/` | Cross-border transfer controls    |
| `legal`           | `hub/domains/governance/packages/legal/`           | Legal review gates                |
| `hr`              | `hub/domains/employee/packages/hr/`              | HR-specific jurisdiction patterns |

**Infrastructure**:

- `libs/canon/src/canon/utils/loader.py` - JurisdictionRegistry, JurisdictionConfig

## Phrases

| Phrase                            | File                                                        | Pattern | Regulatory Basis  |
| --------------------------------- | ----------------------------------------------------------- | ------- | ----------------- |
| `verify_destination_allowed`      | `scope/phrases/verify_destination_allowed.py`               | verify  | GDPR Art. 45-46   |
| `verify_channel_allowed`          | `scope/phrases/verify_channel_allowed.py`                   | verify  | GDPR Art. 5(1)(c) |
| `require_encrypted_transmission`  | `data_protection/phrases/require_encrypted_transmission.py` | require | GDPR Art. 32      |
| `require_classification`          | `data_protection/phrases/require_classification.py`         | require | HIPAA 164.312     |
| `require_legal_review_complete`   | `legal/phrases/require_legal_review_complete.py`            | require | SOX 302/404       |
| `verify_appeal_channel_available` | `legal/phrases/verify_appeal_channel_available.py`          | verify  | APA, FRCP         |

## Infrastructure Components

| Component                      | File                                             | Purpose                                    |
| ------------------------------ | ------------------------------------------------ | ------------------------------------------ |
| `JurisdictionRegistry`         | `libs/canon/src/canon/utils/loader.py`                     | Jurisdiction lookup and normalization      |
| `JurisdictionConfig`           | `libs/canon/src/canon/utils/loader.py`                     | Immutable jurisdiction configuration       |
| `JurisdictionGate`             | `libs/canon/src/canon/enforcement/catalog/jurisdiction.py` | Gate for action permission by jurisdiction |
| `RequestContext.jurisdictions` | `libs/canon/src/canon/enforcement/types.py`                | Jurisdiction tuple in request context      |

## Control Surfaces Using This Pattern

| Surface                    | Charter                                          | Phrases Used                                                                            |
| -------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Cross-Border Data Transfer | `surfaces/data/cross_border_transfer.canon`      | `verify_destination_allowed`, `require_encrypted_transmission`, `verify_ofac_clearance` |
| Tax Jurisdiction Change    | `surfaces/finance/tax_jurisdiction_change.canon` | `require_legal_review_complete`, `verify_approval_chain_complete`, `record_attestation` |

## Jurisdiction Hierarchy

```
                +------------------+
                |   US-FEDERAL     |
                +--------+---------+
                         |
      +------------------+------------------+
      |                  |                  |
+-----+-----+      +-----+-----+      +-----+-----+
|   US-NY   |      |   US-CA   |      |   US-IL   |
+-----+-----+      +-----+-----+      +-----+-----+
      |                  |                  |
+-----+-----+      +-----+-----+      +-----+-----+
|  US-NYC   |      |  US-SFO   |      |  US-CHI   |
+-----------+      +-----------+      +-----------+
```

**Key Property**: `hierarchy("US-NYC")` returns `("US-NYC", "US-NY", "US-FEDERAL")`.

## Package Dependencies

**scope depends on**:

- `core` - Base phrase infrastructure

**data_protection depends on**:

- `core` - Base phrase infrastructure
- `scope` - Destination validation

**legal depends on**:

- `core` - Base phrase infrastructure
- `authorization` - Approval chain verification

**Depended by**:

- Charter DSL workflows reference these phrases
- Control surface charters (Cross-Border Data Transfer, Tax Jurisdiction Change, etc.)

## Key Decisions

1. **Infrastructure vs Vocabulary**: JurisdictionRegistry/JurisdictionGate remain infrastructure;
   phrases consume jurisdiction from RequestContext
2. **Hierarchy-First**: Most-specific-first ordering enables short-circuit evaluation
3. **Set Intersection**: ANY match semantics for permissive routing
4. **Data-Driven Config**: TOML files in policies/ for non-code jurisdiction updates

## Related Documents

- **ADR**: `ADR-019-jurisdiction.md`
- **TDS**: `TDS-019-jurisdiction.md`
- **Related**: ADR-008-policy-gates, ADR-021-privacy-pii
