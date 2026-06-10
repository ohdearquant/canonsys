---
doc_type: mapping
title: "ADR-021 Privacy/PII - Code Mapping"
version: "2.0.0"
updated: "2026-01-29"
adr: ADR-021-privacy-pii
tds: TDS-021-privacy-pii
---

# 021-privacy-pii - Code Mapping

## Vocabulary Package Reference

**Primary Package**: `hub/domains/governance/packages/data_protection/`

### Vocabulary Phrases

| Phrase                           | Pattern | Location           | Regulatory Basis    |
| -------------------------------- | ------- | ------------------ | ------------------- |
| `require_pii_classification`     | require | `data_protection/` | GDPR Art. 32, SOC2  |
| `require_encrypted_transmission` | require | `data_protection/` | GDPR Art. 32, HIPAA |
| `verify_data_minimization`       | verify  | `data_protection/` | GDPR Art. 5(1)(c)   |

### Control Surface Bindings

| Surface                  | Phrase Integration                           |
| ------------------------ | -------------------------------------------- |
| PII Export Authorization | `require_pii_classification` validates facts |
| Cross-Border Transfer    | PII scanning determines data sensitivity     |
| Anonymization Exemption  | PII detection identifies anonymization needs |

---

## Primary Code Paths

- `libs/canon/src/canon/utils/pii.py` - PII detection utilities
- `libs/canon/src/canon/enforcement/catalog/pii.py` - PIISafeGate implementation

## Key Classes/Functions

### Detection Layer (utils/pii.py)

- **PIIPattern** (`pii.py:L21-L52`) - StrEnum defining PII patterns:
  - **Blocking** (MUST NOT persist): SSN, CREDIT_CARD, PASSPORT
  - **Confidential** (validate/redact): EMAIL, PHONE, IP_ADDRESS
  - Properties: `regex`, `is_blocking`, `blocking()`, `all_patterns()`

- **PIIMatch** (`pii.py:L74-L80`) - Frozen dataclass storing pattern type and position (start, end).
  Never stores matched value.

- **PIIScanResult** (`pii.py:L83-L110`) - Scan result with:
  - `matches`: List of PIIMatch
  - `blocking_count`: Count of blocking patterns found
  - `safe_to_persist`: True if no blocking PII
  - `block_reason()`: Human-readable reason

- **scan_for_pii()** (`pii.py:L113-L126`) - Full scan returning PIIScanResult. Optional
  `blocking_only` flag for fast path.

- **has_blocking_pii()** (`pii.py:L129-L133`) - Quick boolean check using regex.search() on blocking
  patterns only.

### Enforcement Layer (enforcement/catalog/pii.py)

- **PIISafeGate** (`pii.py:L1-L85`) - Static gate (gate_id="pii.safe_to_persist") that blocks
  persistence of highly sensitive PII.
  - Scans ctx.metadata for keys: "data", "text", "content", "payload"
  - Handles string, dict (JSON serialized), and list values
  - Fast path: uses `has_blocking_pii()` first, then `scan_for_pii()` for details

## Architectural Patterns

- **Two-Layer Design**: Detection (utils) is separate from enforcement (gate). Detection is
  reusable; gate is the compliance boundary.

- **Position-Only Storage**: PIIMatch stores position, never the matched value. This prevents PII
  leakage in scan results.

- **Blocking vs Confidential**: Clear separation of patterns that MUST block persistence vs patterns
  that need validation/redaction.

- **Fast Path Optimization**: `has_blocking_pii()` short-circuits before full scan. Only compute
  full result when blocking detected.

- **Static Gate ID**: PIISafeGate uses fixed gate_id for infrastructure-level enforcement. Not
  parameterized like other gates.

- **Last Line of Defense**: Gate description explicitly states "LAST LINE OF DEFENSE before data
  persistence".

## Dependencies

- **Depends on**:
  - `canon.enforcement.vocabulary` - Vocabulary-based enforcement (verify_*/require_* phrases)
  - `canon.enforcement.types.RequestContext` - Context with metadata
  - `re` - Standard library regex

- **Depended by**:
  - Evidence persistence - Should use PIISafeGate as hard gate
  - Any service persisting user-provided text

## Key Decisions (for ADR candidates)

1. **Regex-based detection**: Simple, fast, deterministic. Trade-off: may have false
   positives/negatives vs ML-based detection.

2. **SSN/CC/Passport are blocking**: These MUST NOT be stored. No override, no soft enforcement.
   This is non-negotiable compliance.

3. **Email/Phone/IP are confidential**: These can be stored but should be validated/redacted.
   Different compliance treatment.

4. **Metadata key scanning**: Gate scans specific keys in ctx.metadata. Configurable but defaults to
   common patterns.

5. **JSON serialization for dicts**: When scanning dict values, serializes to JSON. This catches
   nested PII.

## Open Questions

- Should redaction be implemented alongside detection? Current code only detects, doesn't redact.
- How to handle false positives (e.g., phone numbers that look like SSNs)?
- Extend to international formats (EU VAT numbers, UK NI numbers)?
- Should there be a "confirmed PII" vs "potential PII" distinction?
